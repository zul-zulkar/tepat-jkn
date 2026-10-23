#!/usr/bin/env python3
"""
siapkan_app.py - hitung sekali semua yang dibaca aplikasi, lalu simpan ke app_data/*.parquet.

Aplikasi hanya membaca app_data/. Fitur, model, dan bootstrap tidak dihitung ulang saat
aplikasi dibuka.

Pemakaian:
    python generate_data.py --n 20000 --seed 2026 --out data   # bila data/ belum ada
    python siapkan_app.py --data data --out app_data            # ±20 detik

Isi app_data/ (hanya peserta PBPU/BP mandiri, data sintetis):
    peserta.parquet              atribut peserta, indeks kemiskinan wilayah, rentang desil DTSEN
    daftar_kerja.parquet         triase per 31 Des 2025 untuk SEMUA 20.000 peserta (termasuk
                                 tanpa_tindakan, supaya halaman profil selalu punya rute):
                                 rute, alasan, fitur perilaku
    ew_daftar.parquet            peringatan dini bulan 2025-12 untuk SEMUA peserta aktif yang
                                 dinilai, berperingkat, supaya kapasitas k bisa diubah di
                                 aplikasi. masuk_daftar = k 5% (daftar kanonik). Kolom
                                 kontribusi_* = kontribusi log-odds tiap fitur.
    linimasa_bayar.parquet       riwayat pembayaran
    linimasa_status.parquet      riwayat status aktif / nonaktif / masa tunggu
    linimasa_klaim.parquet       riwayat klaim
    linimasa_reaktivasi.parquet  tanggal aktif kembali dan bulan tertunggak yang dilunasi
    bunching_harian.parquet      uji lonjakan hari-45: kasus aktual vs kontrafaktual per hari,
                                 rawat inap terjadwal dan plasebo IGD
    bunching_ringkasan.parquet   massa berlebih, kekurangan, lompatan, IK95%, denda terhindar
    evaluasi_label.parquet       label sintetis. HANYA untuk halaman Evaluasi.
    manifest.json                jumlah baris, kolom, ukuran, versi paket, hasil pemeriksaan

Sebelum menulis, skrip memeriksa:
  1. Angka kunci = angka kanonik seed 2026 (konstanta dari cocokkan_angka.py). Lewati dengan
     --tanpa_cek_kanonik untuk data selain seed 2026.
  2. Aturan yang tidak boleh dilanggar (selalu diperiksa): DTSEN 1-5 tidak ada di rute
     verifikasi; peringatan dini hanya memicu bantuan; kolom label hanya ada di
     evaluasi_label.parquet.
  3. Total ukuran app_data/ <= 20 MB.
Bila salah satu gagal, app_data/ lama tidak disentuh.
"""
import argparse
import importlib.metadata as md
import json
import os
import shutil
import sys
import time

import numpy as np
import pandas as pd

import cek_sinyal as cs
import cocokkan_angka as ka
import early_warning as ew

BATAS_MB = 20
SEED = 7       # = --seed bawaan cek_sinyal.py (bootstrap bunching)
K_DAFTAR = 5   # = --k_daftar bawaan early_warning.py, % peserta aktif
N_BOOT = 300   # = n_boot bawaan analisis_bunching
SARAN_BANTUAN = {"cek_kelayakan_PBI", "pengingat_H-5_dan_tawaran_autodebet",
                 "pengingat_saldo_autodebet"}
KOLOM_LABEL = {"segmen", "pengakal_45", "peserta_baru", "tgl_guncangan"}


# ---------------------------------------------------------------- hitung
def hitung_triase(D, re):
    p = cs.triase(cs.fitur_peserta(D, re))
    kol = ["id_peserta", "rute", "alasan", "jeda_dtsen", "rentang_desil", "tunggakan_bulan",
           "tunggakan_rp", "n_reaktivasi", "n_reakt_terkait_klaim", "porsi_reakt_terkait",
           "rasio_hari_aktif", "rasio_klaim_iuran", "klaim_rp", "iuran_rp", "skor_patah",
           "pola_rutin_lalu_berhenti", "bulan_berhenti", "baru_klaim_lalu_berhenti"]
    # urutan sama dengan triase_peserta.csv (rute, tunggakan terbesar dulu); id_peserta
    # sebagai pemecah seri supaya urutan baris selalu sama
    return p[kol].sort_values(["rute", "tunggakan_rp", "id_peserta"],
                              ascending=[True, False, True]).reset_index(drop=True)


def hitung_bunching(D, re):
    # RNG sama persis dengan cek_sinyal.py, jadi IK sama dengan proposal
    h = cs.analisis_bunching(D["klaim"], re, np.random.default_rng(SEED), n_boot=N_BOOT)
    h_pl = cs.analisis_bunching(D["klaim"], re, np.random.default_rng([SEED, 45]),
                                n_boot=N_BOOT, cara_masuk="IGD")
    hari = np.arange(cs.MAKS_HARI + 1)
    (ka_, kb), (la, lb) = cs.JENDELA_KURANG, cs.JENDELA_LEBIH
    jendela = np.select([hari == 0, (hari >= ka_) & (hari <= kb), (hari >= la) & (hari <= lb)],
                        ["hari_0", f"kurang_{ka_}_{kb}", f"lebih_{la}_{lb}"], default="luar")
    harian, ringkas = [], []
    for cara, hh in [("terjadwal", h), ("IGD", h_pl)]:
        harian.append(pd.DataFrame({
            "cara_masuk": cara, "hari": hari, "hitung": hh["hitung"].astype(int), "cf": hh["cf"],
            "jendela": jendela,
            # hari yang dipakai untuk mencocokkan kurva kontrafaktual (lihat cek_sinyal._cf)
            "dipakai_fit": ((hari >= 1) & (hari < ka_)) | (hari > lb)}))
        ringkas.append(dict(
            cara_masuk=cara, n_kasus=hh["n"], n_hari0=hh["hari0"],
            lebih=hh["lebih"], lebih_ik_bawah=hh["ci"][0], lebih_ik_atas=hh["ci"][1],
            kurang=hh["kurang"], lompat=hh["lompat"],
            lompat_ik_bawah=hh["ci_lompat"][0], lompat_ik_atas=hh["ci_lompat"][1],
            ik_lompat_mencakup_0=bool(hh["ci_lompat"][0] <= 0 <= hh["ci_lompat"][1]),
            # denda terhindar tidak bermakna untuk plasebo (IGD tidak bisa ditunda)
            denda_terhindar_rp=hh["denda_terhindar"] if cara == "terjadwal" else np.nan,
            batas_hari=cs.BATAS, n_bootstrap=N_BOOT))
    return pd.concat(harian, ignore_index=True), pd.DataFrame(ringkas), h, h_pl


def hitung_early_warning(D):
    """Sama dengan bagian 'daftar operasional' early_warning.py, tetapi semua peserta aktif
    disimpan dengan peringkat, bukan hanya k teratas."""
    P = ew.bangun_panel(D)
    berlabel = P[P["y"].notna() & (P["bulan"] >= ew.LATIH[0])]
    final = ew.Model().fit(berlabel)
    akhir = P[P["bulan"] == P["bulan"].max()].copy()
    akhir["skor"] = final.prob(akhir)
    k = max(1, int(round(len(akhir) * K_DAFTAR / 100)))

    urut = akhir.nlargest(len(akhir), "skor")
    if urut["id_peserta"].head(k).tolist() != akhir.nlargest(k, "skor")["id_peserta"].tolist():
        raise RuntimeError("peringkat penuh tidak sama dengan daftar k teratas early_warning.py")
    urut = urut.merge(D["dtsen"][["id_peserta", "rentang_desil"]], on="id_peserta", how="left")
    urut["rentang_desil"] = urut["rentang_desil"].fillna("tidak_padan")
    urut["alasan"] = ew.alasan(final, urut)
    urut["saran_intervensi"] = urut.apply(ew.saran_intervensi, axis=1)
    urut["peringkat"] = np.arange(1, len(urut) + 1)
    urut["masuk_daftar"] = urut["peringkat"] <= k

    kol = (["peringkat", "id_peserta", "bulan", "skor", "masuk_daftar", "alasan",
            "saran_intervensi", "rentang_desil", "autodebet", "kelas", "bulan_teramati_12"]
           + [f for f in ew.FITUR if f not in ("autodebet",)])
    kon = final.kontribusi(urut).add_prefix("kontribusi_").reset_index(drop=True)
    tabel = pd.concat([urut[kol].reset_index(drop=True), kon], axis=1)
    info = dict(bulan=str(akhir["bulan"].iloc[0]), n_dinilai=len(akhir), k_orang=k,
                k_persen=K_DAFTAR, n_peserta_bulan_latih=len(berlabel))
    return tabel, info


def tabel_peserta(D, folder_data):
    ps = D["peserta"].copy()
    ps["tgl_daftar"] = pd.to_datetime(ps["tgl_daftar"])
    wil = pd.read_csv(os.path.join(folder_data, "wilayah.csv"))
    ps = ps.merge(wil, on="kode_wilayah", how="left")
    ps = ps.merge(D["dtsen"][["id_peserta", "rentang_desil"]], on="id_peserta", how="left")
    ps["rentang_desil"] = ps["rentang_desil"].fillna("tidak_padan")
    return ps.sort_values("id_peserta").reset_index(drop=True)


def tabel_linimasa(D, re):
    return {
        "linimasa_bayar": D["bayar"].drop(columns="id_bayar")
        .sort_values(["id_peserta", "tgl_bayar", "periode_awal"]),
        "linimasa_status": D["status"].sort_values(["id_peserta", "tgl_mulai"]),
        "linimasa_klaim": D["klaim"].sort_values(["id_peserta", "tgl_masuk", "id_klaim"]),
        "linimasa_reaktivasi": re.sort_values(["id_peserta", "tgl_reakt"]),
    }


def tabel_label(D):
    lab = D["label"].copy()
    lab["tgl_guncangan"] = pd.to_datetime(lab["tgl_guncangan"])
    return lab.sort_values("id_peserta").reset_index(drop=True)


# ---------------------------------------------------------------- pemeriksaan
def cek_aturan(tabel):
    salah = []
    dk = tabel["daftar_kerja"]
    n = int(((dk["rute"] == "verifikasi_pola_reaktivasi") & (dk["rentang_desil"] == "1-5")).sum())
    if n:
        salah.append(f"{n} peserta DTSEN 1-5 masuk rute verifikasi")
    lain = set(tabel["ew_daftar"]["saran_intervensi"]) - SARAN_BANTUAN
    if lain:
        salah.append(f"peringatan dini memberi saran di luar bantuan: {sorted(lain)}")
    for nama, df in tabel.items():
        bocor = KOLOM_LABEL & set(df.columns)
        if nama != "evaluasi_label" and bocor:
            salah.append(f"kolom label {sorted(bocor)} ada di {nama}")
    return salah


def cek_kanonik(tabel, h, h_pl, info):
    beda = []

    def sama(nama, kanonik, hasil):
        if str(kanonik) != str(hasil):
            beda.append(f"{nama}: kanonik {kanonik}, hasil {hasil}")

    dk = tabel["daftar_kerja"]
    sama("peserta dianalisis", 20_000, len(dk))
    n_rute = dk["rute"].value_counts()
    for rute, n in ka.KANONIK_RUTE.items():
        sama(f"n {rute}", n, int(n_rute.get(rute, 0)))
    v = dk.merge(tabel["evaluasi_label"][["id_peserta", "segmen"]], on="id_peserta")
    n_seg = v["segmen"].value_counts()
    for rute, (seg, presisi, recall) in ka.TARGET_RUTE.items():
        g = v[v["rute"] == rute]
        tp = int((g["segmen"] == seg).sum())
        sama(f"presisi {rute}", f"{presisi:.1f}", f"{100 * tp / max(len(g), 1):.1f}")
        sama(f"recall {rute}", f"{recall:.1f}", f"{100 * tp / n_seg.get(seg, 1):.1f}")
    komp = v.loc[v["rute"] == "verifikasi_pola_reaktivasi", "segmen"].value_counts()
    for seg, n in ka.KOMPOSISI_VERIFIKASI.items():
        sama(f"verifikasi berisi {seg}", n, int(komp.get(seg, 0)))
    sama("PBI meski DTSEN 6-10", ka.PBI_JEDA_DTSEN, int(dk["jeda_dtsen"].sum()))

    B, PL = ka.BUNCHING, ka.PLASEBO_IGD
    sama("bunching massa berlebih", B["lebih"], f"{h['lebih']:.0f}")
    sama("bunching IK berlebih", "%d-%d" % B["lebih_ik"], f"{h['ci'][0]:.0f}-{h['ci'][1]:.0f}")
    sama("bunching lompatan", B["lompat"], f"{h['lompat']:.0f}")
    sama("bunching IK lompatan", "%d-%d" % B["lompat_ik"],
         f"{h['ci_lompat'][0]:.0f}-{h['ci_lompat'][1]:.0f}")
    sama("denda terhindar (Rp juta)", B["denda_juta"], f"{h['denda_terhindar'] / 1e6:.0f}")
    sama("plasebo IGD lompatan", PL["lompat"], f"{h_pl['lompat']:.0f}")
    sama("plasebo IGD IK lompatan", "%d-%d" % PL["lompat_ik"],
         f"{h_pl['ci_lompat'][0]:.0f}-{h_pl['ci_lompat'][1]:.0f}")

    E = ka.EW_DAFTAR
    ewd = tabel["ew_daftar"]
    sama("EW bulan operasional", E["bulan"], info["bulan"])
    sama("EW peserta di daftar k 5%", E["n"], int(ewd["masuk_daftar"].sum()))
    saran = ewd.loc[ewd["masuk_daftar"], "saran_intervensi"].value_counts()
    for s, n in E["saran"].items():
        sama(f"EW {s}", n, int(saran.get(s, 0)))
    return beda


# ---------------------------------------------------------------- tulis
def _hemat(df):
    """Kecilkan tipe bilangan bulat. Teks dibiarkan: parquet sudah memakai kamus."""
    df = df.reset_index(drop=True).copy()
    for c in df.columns:
        if pd.api.types.is_integer_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            df[c] = pd.to_numeric(df[c], downcast="integer")
    return df


def _versi():
    v = {"python": sys.version.split()[0]}
    for pkg in ["pandas", "numpy", "scikit-learn", "pyarrow"]:
        try:
            v[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            v[pkg] = None
    return v


def tulis(tabel, folder, meta):
    os.makedirs(folder, exist_ok=True)
    file = {}
    for nama, df in tabel.items():
        path = os.path.join(folder, f"{nama}.parquet")
        df.to_parquet(path, index=False, compression="zstd")
        file[f"{nama}.parquet"] = dict(baris=len(df), byte=os.path.getsize(path),
                                       kolom=list(map(str, df.columns)))
    total = sum(f["byte"] for f in file.values())
    manifest = dict(meta, total_mb=round(total / 1e6, 2), batas_mb=BATAS_MB, file=file)
    # newline="\n": isi sama persis di Windows dan Linux, jadi tidak ada diff palsu di git
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return total + os.path.getsize(os.path.join(folder, "manifest.json")), file


def ganti_isi(baru, tujuan):
    """Pindahkan file baru ke tujuan. Yang dihapus hanya *.parquet dan manifest.json lama,
    jadi --out yang salah ketik tidak akan menghapus folder lain."""
    os.makedirs(tujuan, exist_ok=True)
    for f in os.listdir(tujuan):
        if f.endswith(".parquet") or f == "manifest.json":
            os.remove(os.path.join(tujuan, f))
    for f in os.listdir(baru):
        os.replace(os.path.join(baru, f), os.path.join(tujuan, f))
    os.rmdir(baru)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="app_data")
    ap.add_argument("--tanpa_cek_kanonik", action="store_true",
                    help="lewati pencocokan dengan angka kanonik seed 2026")
    a = ap.parse_args()

    if not os.path.exists(os.path.join(a.data, "peserta.csv")):
        sys.exit(f"folder data '{a.data}' tidak ada atau kosong. Jalankan dulu:\n"
                 f"    python generate_data.py --n 20000 --seed 2026 --out {a.data}")

    t0 = time.time()

    def log(teks):
        print(f"[{time.time() - t0:5.1f} dtk] {teks}", flush=True)

    D, _ = cs.saring_cakupan(cs.muat(a.data))
    re = cs.tabel_reaktivasi(D["status"], D["bayar"])
    log(f"data dimuat: {len(D['peserta']):,} peserta PBPU/BP mandiri")
    daftar_kerja = hitung_triase(D, re)
    log("triase selesai")
    b_harian, b_ringkas, h, h_pl = hitung_bunching(D, re)
    log("uji lonjakan hari-45 + plasebo IGD selesai")
    ew_daftar, info = hitung_early_warning(D)
    log(f"peringatan dini {info['bulan']} selesai: {info['n_dinilai']:,} peserta dinilai")

    tabel = {"peserta": tabel_peserta(D, a.data), "daftar_kerja": daftar_kerja,
             "ew_daftar": ew_daftar, **tabel_linimasa(D, re),
             "bunching_harian": b_harian, "bunching_ringkasan": b_ringkas,
             "evaluasi_label": tabel_label(D)}
    tabel = {nama: _hemat(df) for nama, df in tabel.items()}

    gagal = cek_aturan(tabel)
    if a.tanpa_cek_kanonik:
        status_kanonik = "dilewati"
    else:
        beda = cek_kanonik(tabel, h, h_pl, info)
        status_kanonik = "lolos (seed 2026)" if not beda else "GAGAL"
        gagal += beda
    if gagal:
        print("\nTIDAK DITULIS. app_data/ lama tidak disentuh.", file=sys.stderr)
        for g in gagal:
            print(f"  - {g}", file=sys.stderr)
        sys.exit(1)
    log(f"pemeriksaan aturan lolos; angka kanonik {status_kanonik}")

    meta = dict(
        keterangan="Data sintetis, dibuat oleh siapkan_app.py. Jangan diedit tangan.",
        cek_kanonik=status_kanonik,
        triase_per_tanggal=str(cs.AKHIR.date()),
        ew_bulan_operasional=info["bulan"],
        ew_k_persen_daftar=info["k_persen"],
        ew_k_orang_daftar=info["k_orang"],
        ew_n_dinilai=info["n_dinilai"],
        ew_n_peserta_bulan_latih=info["n_peserta_bulan_latih"],
        versi=_versi(),
    )
    baru = a.out.rstrip("/\\") + "_baru"
    if os.path.isdir(baru):
        shutil.rmtree(baru)
    total, file = tulis(tabel, baru, meta)
    if total > BATAS_MB * 1e6:
        print(f"\nTIDAK DITULIS: total {total / 1e6:.1f} MB melebihi batas {BATAS_MB} MB. "
              f"Hasil sementara ada di {baru}/.", file=sys.stderr)
        sys.exit(1)
    ganti_isi(baru, a.out)
    log(f"ditulis ke {a.out}/")

    print(f"\n{'file':32s} {'baris':>9s} {'MB':>7s}")
    for nama, f in file.items():
        print(f"{nama:32s} {f['baris']:>9,} {f['byte'] / 1e6:>7.2f}")
    print(f"{'total (termasuk manifest.json)':32s} {'':>9s} {total / 1e6:>7.2f}  (batas {BATAS_MB} MB)")


if __name__ == "__main__":
    main()
