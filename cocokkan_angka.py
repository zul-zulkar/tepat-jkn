"""
Cocokkan keluaran pipeline dengan angka kanonik (seed 2026) yang sudah tertulis di proposal.

Urutan:
    python generate_data.py --n 20000 --seed 2026 --out data
    python cek_sinyal.py    --data data --out hasil_cek
    python early_warning.py --data data --out hasil_cek
    python cocokkan_angka.py --data data --hasil hasil_cek

Dua lapis pemeriksaan:
1. Angka kanonik, pada pembulatan yang sama dengan yang tertulis di proposal.
2. Pembanding ketat: isi file di hasil_cek/ harus sama persis dengan hasil/ yang di-commit
   (--referensi hasil). Lapis ini menangkap pergeseran kecil yang tertutup pembulatan.

Kode keluar 1 bila ada yang tidak cocok. Jalankan sebelum commit yang menyentuh
generate_data.py, cek_sinyal.py, early_warning.py, atau requirements.txt.
Keluarkan ke hasil_cek/, bukan hasil/, supaya file yang di-commit tetap jadi pembanding.

Angka yang sengaja diubah (misalnya setelah perubahan parameter) harus diperbarui di
KANONIK di bawah DAN di proposal/naskah video dalam commit yang sama.
"""

import argparse
import os
import re
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# Angka kanonik. (nilai, jumlah desimal). Persentase ditulis dalam persen.
# ---------------------------------------------------------------------------
KANONIK_DATA = {
    "peserta": 23_000,
    "pembayaran": 546_345,
    "riwayat_status": 116_920,
    "klaim": 78_675,
    "dtsen_flag": 21_173,
    "wilayah": 40,
    "label_ground_truth": 23_000,
}
SIDIK_DATA = {  # sidik jari isi, tidak bergantung pada akhir baris CRLF/LF
    "total nominal pembayaran (Rp)": 51_152_426_000,
    "total biaya klaim (Rp)": 147_828_848_000,
    "total denda pelayanan (Rp)": 3_691_222_550,
}
KANONIK_RUTE = {
    "verifikasi_pola_reaktivasi": 909,
    "rujuk_cek_kelayakan_PBI": 2_133,
    "pengingat_autodebet_REHAB": 5_059,
    "nonaktif_lama_tanpa_sinyal": 224,
    "tanpa_tindakan": 11_675,
}
TARGET_RUTE = {  # rute -> (segmen target, presisi %, recall %)
    "verifikasi_pola_reaktivasi": ("reaktivasi_saat_butuh", 98.0, 44.3),
    "rujuk_cek_kelayakan_PBI": ("tidak_mampu", 86.3, 70.5),
    "pengingat_autodebet_REHAB": ("lalai", 86.8, 88.7),
}
KOMPOSISI_VERIFIKASI = {"reaktivasi_saat_butuh": 891, "tidak_mampu": 18, "lalai": 0, "patuh": 0}
PBI_JEDA_DTSEN = 603
BUNCHING = {"lebih": 169, "lebih_ik": (131, 213), "lompat": 227, "lompat_ik": (185, 274),
            "denda_juta": 745}
PLASEBO_IGD = {"lompat": 4, "lompat_ik": (-24, 31)}
EW = {  # metrik di early_warning_metrik.csv: (populasi, metrik) -> (nilai, desimal)
    ("semua_aktif", "auc_model"): (0.854, 3),
    ("semua_aktif", "auc_aturan"): (0.822, 3),
    ("semua_aktif", "brier_model"): (0.113, 3),
    ("semua_aktif", "brier_tanpa_model"): (0.167, 3),
    ("belum_pernah_nonaktif", "auc_model"): (0.708, 3),
    ("belum_pernah_nonaktif", "base_rate"): (6.0, 0),  # "±6%"
}
EW_PRESISI_SUBSET_K1 = 52.2  # presisi 1% teratas, subset belum pernah nonaktif, persen
EW_DAFTAR = {"bulan": "2025-12", "n": 712, "saran": {
    "pengingat_H-5_dan_tawaran_autodebet": 452,
    "cek_kelayakan_PBI": 173,
    "pengingat_saldo_autodebet": 87,
}}

# ---------------------------------------------------------------------------
hasil_cek = []


def catat(kelompok, metrik, kanonik, aktual, desimal=0):
    if isinstance(kanonik, (int, float)) and isinstance(aktual, (int, float)):
        k, a = f"{kanonik:,.{desimal}f}", f"{aktual:,.{desimal}f}"
    else:
        k, a = str(kanonik), str(aktual)
    hasil_cek.append((k == a, kelompok, metrik, k, a))


def cek_data(folder):
    for tabel, n in KANONIK_DATA.items():
        path = os.path.join(folder, f"{tabel}.csv")
        catat("data", f"baris {tabel}", n, len(pd.read_csv(path, usecols=[0])) if os.path.exists(path) else "file tidak ada")
    bayar = pd.read_csv(os.path.join(folder, "pembayaran.csv"), usecols=["nominal"])
    klaim = pd.read_csv(os.path.join(folder, "klaim.csv"), usecols=["biaya_klaim", "denda_pelayanan"])
    aktual = [bayar.nominal.sum(), klaim.biaya_klaim.sum(), klaim.denda_pelayanan.sum()]
    for (nama, nilai), a in zip(SIDIK_DATA.items(), aktual):
        catat("data", nama, nilai, round(float(a)))


def cek_triase(folder_data, folder_hasil):
    p = pd.read_csv(os.path.join(folder_hasil, "triase_peserta.csv"))
    lab = pd.read_csv(os.path.join(folder_data, "label_ground_truth.csv"), usecols=["id_peserta", "segmen"])
    p = p.merge(lab, on="id_peserta", how="left")
    catat("triase", "peserta dianalisis", 20_000, len(p))
    n_rute = p.rute.value_counts()
    for rute, n in KANONIK_RUTE.items():
        catat("triase", f"n {rute}", n, int(n_rute.get(rute, 0)))
    n_seg = p.segmen.value_counts()
    for rute, (seg, presisi, recall) in TARGET_RUTE.items():
        g = p[p.rute == rute]
        tp = int((g.segmen == seg).sum())
        catat("triase", f"presisi {rute} (%)", presisi, 100 * tp / max(len(g), 1), 1)
        catat("triase", f"recall {rute} (%)", recall, 100 * tp / n_seg.get(seg, 1), 1)
    v = p[p.rute == "verifikasi_pola_reaktivasi"].segmen.value_counts()
    for seg, n in KOMPOSISI_VERIFIKASI.items():
        catat("triase", f"verifikasi berisi {seg}", n, int(v.get(seg, 0)))
    pbi = p[p.rute == "rujuk_cek_kelayakan_PBI"]
    catat("triase", "PBI tertangkap meski DTSEN 6-10", PBI_JEDA_DTSEN, int(pbi.jeda_dtsen.astype(str).str.lower().eq("true").sum()))
    catat("aturan", "DTSEN 1-5 di rute verifikasi (harus 0)", 0,
          int(((p.rute == "verifikasi_pola_reaktivasi") & (p.rentang_desil.astype(str) == "1-5")).sum()))


def _ambil(teks, pola, label):
    m = re.search(pola, teks)
    if not m:
        raise ValueError(f"pola '{label}' tidak ditemukan di ringkasan.txt (format keluaran berubah?)")
    return [int(x) for x in m.groups()]


def cek_bunching(folder_hasil):
    with open(os.path.join(folder_hasil, "ringkasan.txt"), encoding="utf-8", errors="replace") as f:
        teks = f.read()
    terjadwal, _, igd = teks.partition("== 1b.")
    ik = r"\(IK95%[^\d-]*(-?\d+)-(-?\d+)\)"
    lebih, lo, hi = _ambil(terjadwal, r"massa berlebih hari 46-60\s*:\s*(-?\d+) kasus " + ik, "massa berlebih")
    catat("bunching", "massa berlebih hari 46-60", BUNCHING["lebih"], lebih)
    catat("bunching", "IK massa berlebih", "%d s.d. %d" % BUNCHING["lebih_ik"], f"{lo} s.d. {hi}")
    lompat, lo, hi = _ambil(terjadwal, r"lompatan \(berlebih \+ kekurangan\) (-?\d+) " + ik, "lompatan")
    catat("bunching", "lompatan", BUNCHING["lompat"], lompat)
    catat("bunching", "IK lompatan", "%d s.d. %d" % BUNCHING["lompat_ik"], f"{lo} s.d. {hi}")
    (denda,) = _ambil(terjadwal, r"denda terhindar\s*:\s*Rp(\d+) juta", "denda terhindar")
    catat("bunching", "denda terhindar (Rp juta)", BUNCHING["denda_juta"], denda)
    lompat, lo, hi = _ambil(igd, r"lompatan\s*:\s*(-?\d+) " + ik, "lompatan IGD")
    catat("plasebo IGD", "lompatan", PLASEBO_IGD["lompat"], lompat)
    catat("plasebo IGD", "IK lompatan", "%d s.d. %d" % PLASEBO_IGD["lompat_ik"], f"{lo} s.d. {hi}")


def cek_early_warning(folder_hasil):
    m = pd.read_csv(os.path.join(folder_hasil, "early_warning_metrik.csv")).set_index(["populasi", "metrik"]).nilai
    for (pop, met), (nilai, des) in EW.items():
        a = float(m.get((pop, met), float("nan")))
        if met == "base_rate":
            a *= 100
        catat("early warning", f"{met} [{pop}]", nilai, a, des)
    k = pd.read_csv(os.path.join(folder_hasil, "early_warning_presisi_k.csv"))
    baris = k[(k.populasi == "belum_pernah_nonaktif") & (k.k_persen == 1.0)]
    catat("early warning", "presisi 1% teratas [belum_pernah_nonaktif] (%)", EW_PRESISI_SUBSET_K1,
          100 * float(baris.presisi_model.iloc[0]) if len(baris) else float("nan"), 1)
    d = pd.read_csv(os.path.join(folder_hasil, "early_warning_daftar.csv"))
    catat("daftar EW", "bulan operasional", EW_DAFTAR["bulan"], ",".join(sorted(d.bulan.astype(str).unique())))
    catat("daftar EW", "peserta di daftar (k 5%)", EW_DAFTAR["n"], len(d))
    s = d.saran_intervensi.value_counts()
    for saran, n in EW_DAFTAR["saran"].items():
        catat("daftar EW", saran, n, int(s.get(saran, 0)))


def cek_kesegaran(folder_data, folder_hasil):
    """Hasil harus lebih baru dari data. Ini celah #9: triase_peserta.csv lebih tua dari data/."""
    t_data = max(os.path.getmtime(os.path.join(folder_data, f"{t}.csv")) for t in KANONIK_DATA)
    for f in ["triase_peserta.csv", "ringkasan.txt", "early_warning_daftar.csv", "early_warning_metrik.csv"]:
        path = os.path.join(folder_hasil, f)
        if not os.path.exists(path):
            catat("kesegaran", f, "ada", "file tidak ada")
        else:
            catat("kesegaran", f"{f} lebih baru dari data", "ya", "ya" if os.path.getmtime(path) >= t_data else "TIDAK")


FILE_REFERENSI = ["ringkasan.txt", "early_warning_ringkasan.txt", "early_warning_metrik.csv",
                  "early_warning_presisi_k.csv", "early_warning_koefisien.csv",
                  "early_warning_kalibrasi.csv", "early_warning_daftar.csv"]


def cek_identik(folder_hasil, folder_ref):
    """Pembanding ketat: isi file sama persis dengan hasil/ yang di-commit (akhir baris diabaikan).
    Pembulatan proposal bisa menutupi pergeseran kecil, misalnya scikit-learn 1.3 vs 1.4."""
    if os.path.abspath(folder_hasil) == os.path.abspath(folder_ref):
        catat("identik", "hasil dibandingkan dengan dirinya sendiri", "folder lain", "folder sama")
        return
    for f in FILE_REFERENSI:
        p_ref, p_baru = os.path.join(folder_ref, f), os.path.join(folder_hasil, f)
        if not (os.path.exists(p_ref) and os.path.exists(p_baru)):
            catat("identik", f, "ada", "file tidak ada")
            continue
        with open(p_ref, encoding="utf-8", errors="replace", newline="") as fr, \
             open(p_baru, encoding="utf-8", errors="replace", newline="") as fb:
            sama = fr.read().replace("\r\n", "\n") == fb.read().replace("\r\n", "\n")
        catat("identik", f"{f} = {os.path.basename(os.path.normpath(folder_ref))}/{f}", "sama", "sama" if sama else "BERUBAH")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--hasil", default="hasil_cek")
    ap.add_argument("--referensi", default="hasil",
                    help="folder hasil yang di-commit untuk pembanding ketat; '' untuk melewati")
    a = ap.parse_args()

    langkah = [("kesegaran", lambda: cek_kesegaran(a.data, a.hasil)),
               ("data", lambda: cek_data(a.data)),
               ("triase", lambda: cek_triase(a.data, a.hasil)),
               ("bunching", lambda: cek_bunching(a.hasil)),
               ("early warning", lambda: cek_early_warning(a.hasil))]
    if a.referensi:
        langkah.append(("identik", lambda: cek_identik(a.hasil, a.referensi)))
    for nama, fn in langkah:
        try:
            fn()
        except Exception as e:  # satu bagian gagal dibaca tidak menghentikan bagian lain
            hasil_cek.append((False, nama, "gagal dibaca", "-", f"{type(e).__name__}: {e}"))

    import importlib.metadata as md
    versi = []
    for pkg in ["pandas", "numpy", "scipy", "scikit-learn", "matplotlib"]:
        try:
            versi.append(f"{pkg} {md.version(pkg)}")
        except md.PackageNotFoundError:
            versi.append(f"{pkg} -")
    print(f"python {sys.version.split()[0]} | " + " | ".join(versi))
    print(f"data: {os.path.abspath(a.data)}\nhasil: {os.path.abspath(a.hasil)}\n")

    lebar = max(len(r[2]) for r in hasil_cek)
    print(f"{'':4s} {'kelompok':14s} {'metrik':{lebar}s}  {'kanonik':>16s}  {'hasil':>16s}")
    for ok, kel, met, k, h in hasil_cek:
        print(f"{'OK' if ok else 'BEDA':4s} {kel:14s} {met:{lebar}s}  {k:>16s}  {h:>16s}")
    n_beda = sum(not r[0] for r in hasil_cek)
    print(f"\n{len(hasil_cek) - n_beda}/{len(hasil_cek)} cocok.", end=" ")
    if n_beda:
        print(f"{n_beda} BEDA. Jangan pakai hasil ini di aplikasi/video sebelum penyebabnya jelas.")
        print("Cek dulu: versi scikit-learn (>=1.4), seed, dan apakah data/ dibuat ulang setelah kode berubah.")
        sys.exit(1)
    print("Semua angka kanonik tereproduksi.")


if __name__ == "__main__":
    main()
