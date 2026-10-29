#!/usr/bin/env python3
"""
kalibrasi_sampel.py - TEPAT: target kalibrasi generator dari Data Sampel BPJS Kesehatan
Edisi 2025 (data layanan 2024).

Membaca file .dta mentah dari folder di LUAR repo, lalu menulis HANYA angka agregat ke
kalibrasi/target_sampel_bpjs_2024.csv. Angka itu dipakai profil `sampel2024` di
generate_data.py dan dibandingkan oleh cek_realisme.py.

Aturan data (pakta integritas BPJS dan jawaban panitia 28 Okt 2026): angka agregat boleh
tampil di repo publik selama tidak mengidentifikasi individu, fasilitas kesehatan, atau
badan usaha, dan tidak bisa dipakai merekonstruksi data asli. Data mentah dan salinannya
tidak boleh diunggah. Karena itu skrip ini:
  - hanya menulis persentase, rasio, median, dan rata-rata dari kelompok besar;
  - mengosongkan angka dari kelompok berisi kurang dari 100 orang atau 100 klaim;
  - membulatkan jumlah orang dan klaim ke ratusan terdekat;
  - tidak menulis wilayah, faskes, ID, atau tanggal;
  - menyimpan cache baris-per-baris (--cache) di luar repo. Jangan arahkan ke dalam repo.

Batas yang tidak bisa diatasi: data sampel tidak berisi pembayaran iuran, status bulanan,
atau tanggal aktif kembali. Status kepesertaan berupa satu potret di akhir periode
(diasumsikan 31 Des 2024: layanan dan tahun meninggal berakhir di 2024). Angka di sini
mengkalibrasi komposisi dan besar efek. Angka ini TIDAK memvalidasi model peringatan dini
atau aturan triase.

Semua persentase memakai bobot sampel (PSTV15). "PBPU" = peserta yang di potret akhir
berstatus PBPU, masih hidup, dan berusia >= 18 tahun (generator hanya membuat orang dewasa),
kecuali disebut lain.

Pemakaian (dari folder utama repo, perlu RAM sekitar 3 GB):
    python kalibrasi_sampel.py --sampel ../02-full-project/data_sample
Pembacaan pertama 5-10 menit. Berikutnya memakai cache.
"""
import argparse
import os

import numpy as np
import pandas as pd

REG = "Data Sampel Reguler Edisi 2025/data/"
KIA = "Data Sampel Kontekstual KIA Edisi 2025 - Subset Ibu/data/"
TABEL = {  # nama: (file relatif ke --sampel, kolom yang dibaca)
    "pst": (REG + "2015202401_kepesertaan.dta",
            ["PSTV01", "PSTV02", "PSTV03", "PSTV07", "PSTV08", "PSTV15", "PSTV16", "PSTV17", "PSTV18"]),
    "fkrtl": (REG + "202403_fkrtl.dta",
              ["PSTV01", "PSTV15", "FKL02", "FKL03", "FKL04", "FKL10", "FKL12", "FKL13", "FKL17A",
               "FKL48"]),
    "fktp": (REG + "202402_fktpkapitasi.dta", ["PSTV01", "FKP03", "FKP12", "FKP14A"]),
    "dx2": (REG + "202405_diagnosissekunder.dta", ["FKL02", "FKL24A"]),
    "kia_pst": (KIA + "KIA2024ibu_kepesertaan.dta", ["PSTV01", "PSTV08", "PSTV15", "PSTV17", "PSTV18"]),
    "kia_fkrtl": (KIA + "KIA2024ibu_fkrtl.dta", ["PSTV01", "FKL04", "FKL12", "FKL17A", "FKL19"]),
    "kia_fktp": (KIA + "KIA2024ibu_fktpkapitasi.dta", ["PSTV01", "FKP03", "FKP14A"]),
}
BERLABEL = {"PSTV07", "PSTV08", "PSTV17", "FKL10", "FKL12", "FKL13", "FKP12"}

POTRET = pd.Timestamp("2024-12-31")
AWAL = pd.Timestamp("2024-01-01")
KLAIM_BESAR = 1_000_000          # sama dengan cek_sinyal.py: RITL atau klaim >= Rp1 juta
JEDA_PASCA = 90                  # hari: aktivitas terakhir <= 90 hari setelah klaim besar
MIN_N = 100
NONAKTIF = "NON AKTIF KARNA PREMI"
KRONIS = r"^(E1[0-4]|I1[0-5]|I2[05]|I50|N18|J44|Z49)"   # DM, HT, jantung, gagal jantung, CKD, PPOK, HD
PERSALINAN = r"^O8[0-4]"
ANC = r"^Z3[4-6]"
PITA_USIA = [(18, 30), (30, 45), (45, 60), (60, 200)]   # sama dengan A11-A14
KODE_USIA_RI = ["B16", "B17", "B18", "B19"]


# ---------------------------------------------------------------- baca
def kamus_label(path, kolom):
    """{kolom: {kode: label}}. Pemetaan kolom ke kamus label dibaca dari header file sebelum
    kolom dipilih: di file sampel BPJS nama kamus tidak selalu sama dengan nama kolom, dan
    pandas menggeser daftar label begitu kolom dipilih."""
    with pd.read_stata(path, convert_categoricals=False, iterator=True) as r:
        r.variable_labels()                          # memaksa header terbaca
        nama = dict(zip(r._varlist, r._lbllist))
        vl = r.value_labels()
    out = {}
    for c in kolom:
        if c in BERLABEL:
            peta = vl.get(nama.get(c, ""), {})
            if not peta:
                raise SystemExit(f"kamus label untuk {c} tidak ditemukan di {os.path.basename(path)}")
            out[c] = peta
    return out


def baca(path, kolom, chunk=500_000):
    """Kode mentah. Label dipasang terpisah oleh beri_label()."""
    bagian = []
    with pd.read_stata(path, columns=kolom, convert_categoricals=False, chunksize=chunk) as r:
        for ch in r:
            bagian.append(ch)
    df = pd.concat(bagian, ignore_index=True)
    for c in kolom:
        if c not in BERLABEL and df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().astype("category")
    return df


def baca_cepat(path, kolom):
    """Seperti baca() (kode mentah), lewat pyreadstat bila terpasang: jauh lebih cepat pada berkas besar."""
    try:
        import pyreadstat
    except ImportError:
        return baca(path, kolom)
    df, _ = pyreadstat.read_dta(path, usecols=kolom, apply_value_formats=False, dates_as_pandas_datetime=True)
    for c in kolom:
        if c not in BERLABEL and df[c].dtype == object:
            angka = pd.to_numeric(df[c], errors="coerce")
            if angka.notna().sum() == df[c].notna().sum():   # kolom angka berisi kosong (mis. tahun meninggal)
                df[c] = angka.astype(float)                  # sama dengan pandas: NaN bila kosong
            else:
                df[c] = df[c].astype(str).str.strip().astype("category")
    return df


def beri_label(df, kamus):
    for c, peta in kamus.items():
        teks = df[c].map(peta)
        teks = teks.astype(object).where(teks.notna(), df[c].astype(str))
        df[c] = teks.astype(str).str.strip().str.upper().astype("category")
    return df


_MEMO = {}


def muat(nama, sampel, cache):
    if nama in _MEMO:
        return _MEMO[nama].copy()
    path, kolom = TABEL[nama]
    path = os.path.join(sampel, path)
    f = os.path.join(cache, nama + ".pkl")
    df = pd.read_pickle(f) if os.path.exists(f) else None
    if df is not None and not all(pd.api.types.is_numeric_dtype(df[c]) for c in kolom if c in BERLABEL):
        df = None                                    # cache lama berisi label, bukan kode mentah
    if df is None:
        df = baca(path, kolom)
        tmp = f + ".tmp"
        df.to_pickle(tmp)
        os.replace(tmp, f)
        print(f"  dibaca: {nama} ({len(df):,} baris)")
    _MEMO[nama] = beri_label(df, kamus_label(path, kolom))
    return _MEMO[nama].copy()


# ---------------------------------------------------------------- bantu
BARIS = []


def catat(bagian, kode, uraian, nilai, satuan, n, dipakai, catatan="", des=1):
    """n = jumlah orang/klaim di belakang angka (tak berbobot), untuk aturan sel kecil."""
    kecil = n is not None and n < MIN_N
    ok = not kecil and nilai is not None and np.isfinite(nilai)
    BARIS.append(dict(
        bagian=bagian, kode=kode, uraian=uraian,
        nilai=round(float(nilai), des) if ok else None,
        satuan=satuan,
        n_sampel=("<100" if kecil else (None if n is None else int(round(n, -2)))),
        dipakai_generator=dipakai, catatan=catatan))


def pw(mask, w):
    """persen berbobot"""
    w = np.asarray(w, float)
    return 100.0 * float((np.asarray(mask, bool) * w).sum() / w.sum()) if w.sum() > 0 else np.nan


def qw(x, w, q):
    """kuantil berbobot"""
    x, w = np.asarray(x, float), np.asarray(w, float)
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][min(np.searchsorted(cw, q * cw[-1]), len(x) - 1)])


def jendela(bulan):
    return np.select([bulan <= 6, bulan <= 9], ["jan_jun", "jul_sep"], "okt_des")


def uji_pasca_klaim(pop, ev):
    """pop: peserta (index PSTV01; kolom np, w). ev: kejadian (PSTV01, t, besar).
    Kembalikan {(jendela, kelompok): (persen nonaktif, n)}"""
    ev = ev[ev.PSTV01.isin(pop.index) & (ev.t >= AWAL) & (ev.t <= POTRET)]
    akhir = ev.groupby("PSTV01").t.max()
    akhir_besar = ev[ev.besar].groupby("PSTV01").t.max()
    d = pd.DataFrame({"akhir": akhir})
    d["jeda"] = (d["akhir"] - akhir_besar.reindex(d.index)).dt.days
    d["kel"] = np.where(d.jeda.isna(), "tanpa", np.where(d.jeda <= JEDA_PASCA, "pasca", "lain"))
    d["jen"] = jendela(d["akhir"].dt.month.values)
    d = d.join(pop[["np", "w"]])
    out = {}
    for (j, k), g in d.groupby(["jen", "kel"]):
        out[(j, k)] = (pw(g.np, g.w), len(g))
    return out


def catat_ri_per_usia(bagian, lama, ada_ri):
    """B16-B20: porsi PBPU dewasa lama (tahun sampel <= 2022) dengan >= 1 rawat inap 2024, per kelompok
    usia (usia di potret 31 Des 2024; kelompok sama dengan A11-A14), dan rasio kelompok tertua / termuda.
    lama: index PSTV01, kolom usia dan w. ada_ri: PSTV01 yang punya rawat inap sebagai PBPU.
    Dipakai hitung() dan hitung_tambahan(): satu definisi."""
    p, n = [], []
    for (a, b), kode in zip(PITA_USIA, KODE_USIA_RI):
        g = lama[(lama.usia >= a) & (lama.usia < b)]
        lab = f"{a}-{b - 1}" if b < 200 else f"{a}+"
        p.append(pw(g.index.isin(ada_ri), g.w))
        n.append(len(g))
        catat(bagian, kode, f"PBPU dewasa lama usia {lab}: punya >= 1 rawat inap 2024", p[-1], "%", n[-1], "tidak",
              "cek realisme usia; generator mengalikan kebutuhan layanan dengan faktor usia (asumsi)")
    catat(bagian, "B20", "rasio rawat inap usia 60+ / 18-29 (PBPU dewasa lama)", p[3] / p[0] if p[0] else np.nan,
          "x", min(n[0], n[3]), "tidak", des=2)


def hitung_tambahan(sampel):
    """Hanya B16-B20, untuk mesin ber-RAM kecil: dua tabel dengan kolom seperlunya, tanpa cache.
    Populasi dan definisi rawat inap sama dengan hitung(). Mengembalikan (tabel B16-B20, cek silang),
    cek silang = A15, A16, B01, B02 yang dihitung ulang dari bacaan ini."""
    BARIS.clear()
    kol_p = ["PSTV01", "PSTV03", "PSTV08", "PSTV15", "PSTV16", "PSTV18"]
    pth = os.path.join(sampel, TABEL["pst"][0])
    P = beri_label(baca_cepat(pth, kol_p), kamus_label(pth, kol_p))
    P["w"] = P.PSTV15.astype(float)
    P["hidup"] = P.PSTV18.isna()
    P["usia"] = (POTRET - P.PSTV03).dt.days / 365.25
    pb = P[P.PSTV08.astype(str).eq("PBPU") & P.hidup & (P.usia >= 18)].set_index("PSTV01")
    pb.index = pb.index.astype(str)
    kol_f = ["PSTV01", "FKL10", "FKL12"]
    pth = os.path.join(sampel, TABEL["fkrtl"][0])
    F = beri_label(baca_cepat(pth, kol_f), kamus_label(pth, kol_f))
    F = F[F.FKL12.astype(str).eq("PBPU") & F.FKL10.astype(str).eq("RITL")]
    ada_ri = pd.Index(F.PSTV01.astype(str).unique())
    lama, baru = pb[pb.PSTV16 <= 2022], pb[pb.PSTV16 == 2024]
    sd = np.sqrt(np.average((pb.usia - np.average(pb.usia, weights=pb.w)) ** 2, weights=pb.w))
    cek = {"A15": np.average(pb.usia, weights=pb.w), "A16": sd,
           "B01": pw(lama.index.isin(ada_ri), lama.w), "B02": pw(baru.index.isin(ada_ri), baru.w)}
    catat_ri_per_usia("B_layanan", lama, ada_ri)
    return pd.DataFrame(BARIS), cek


def sisipkan_tambahan(a):
    """Jalankan hitung_tambahan, cek silang ke CSV yang ada, lalu sisipkan baris B16-B20 setelah B15
    (baris lain tidak disentuh, format sama)."""
    f = os.path.join(a.out, "target_sampel_bpjs_2024.csv")
    ada = pd.read_csv(f)
    baru, cek = hitung_tambahan(a.sampel)
    print("cek silang (hitung ulang vs CSV yang ada):")
    for k, v in cek.items():
        acuan = float(ada.loc[ada.kode.eq(k), "nilai"].iloc[0])
        print(f"  {k}: {v:.2f} vs {acuan:.2f}")
        if abs(round(v, 1) - acuan) > 0.051:
            raise SystemExit(f"cek silang {k} gagal: bacaan ini tidak sama dengan CSV yang ada. Tidak ditulis.")
    with pd.option_context("display.width", 200, "display.max_colwidth", 80):
        print(baru[["kode", "uraian", "nilai", "satuan", "n_sampel"]].to_string(index=False))
    teks = open(f, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in teks else "\n"
    baris = teks.split(nl)
    akhir_kosong = baris[-1] == ""
    baris = [b for b in baris if b != ""] if akhir_kosong else baris
    baris = [b for b in baris if not any(b.startswith(f"B_layanan,{k},") for k in baru.kode)]
    i = next(j for j, b in enumerate(baris) if b.startswith("B_layanan,B15,")) + 1
    tambah = baru.to_csv(index=False, header=False, lineterminator="\n").rstrip("\n").split("\n")
    baris = baris[:i] + tambah + baris[i:]
    with open(f, "w", encoding="utf-8", newline="") as h:
        h.write(nl.join(baris) + (nl if akhir_kosong else ""))
    print(f"\nditulis: {f} (+{len(tambah)} baris agregat, setelah B15)")


# ---------------------------------------------------------------- hitung
def hitung(sampel, cache):
    m = lambda nama: muat(nama, sampel, cache)  # noqa: E731

    # ---------- A. status dan komposisi
    P = m("pst")
    P["w"] = P.PSTV15.astype(float)
    P["hidup"] = P.PSTV18.isna()
    P["np"] = P.PSTV17.astype(str).eq(NONAKTIF)
    P["usia"] = (POTRET - P.PSTV03).dt.days / 365.25
    seg = P.PSTV08.astype(str)
    pb = P[seg.eq("PBPU") & P.hidup & (P.usia >= 18)].set_index("PSTV01")
    pb_semua = P[seg.eq("PBPU") & P.hidup]
    bp = P[seg.eq("BUKAN PEKERJA") & P.hidup & (P.usia >= 18)]
    A = "A_status"
    catat(A, "A01", "PBPU dewasa: nonaktif karena premi", pw(pb.np, pb.w), "%", len(pb), "ya",
          "target tingkat dasar nonaktif di potret akhir 2024")
    catat(A, "A02", "PBPU semua usia: nonaktif karena premi", pw(pb_semua.np, pb_semua.w), "%",
          len(pb_semua), "tidak")
    catat(A, "A03", "BP (bukan pekerja) dewasa: nonaktif karena premi", pw(bp.np, bp.w), "%", len(bp), "ya",
          "BP hampir tidak pernah nonaktif karena premi")
    catat(A, "A04", "porsi BP di antara PBPU+BP dewasa (bobot)",
          100 * bp.w.sum() / (bp.w.sum() + pb.w.sum()), "%", len(bp) + len(pb), "tidak",
          "sebagian besar BP adalah penerima pensiun; iurannya bukan pola bayar mandiri")
    kls = pb.PSTV07.astype(str)
    for i, (k, kode) in enumerate([("KELAS I", "A05"), ("KELAS II", "A06"), ("KELAS III", "A07")]):
        catat(A, kode, f"PBPU dewasa: porsi {k.lower()}", pw(kls.eq(k), pb.w), "%", len(pb), "ya")
    for k, kode in [("KELAS I", "A08"), ("KELAS II", "A09"), ("KELAS III", "A10")]:
        g = pb[kls.eq(k)]
        catat(A, kode, f"PBPU dewasa {k.lower()}: nonaktif karena premi", pw(g.np, g.w), "%", len(g), "ya")
    for (a, b), kode in zip([(18, 30), (30, 45), (45, 60), (60, 200)], ["A11", "A12", "A13", "A14"]):
        g = pb[(pb.usia >= a) & (pb.usia < b)]
        lab = f"{a}-{b - 1}" if b < 200 else f"{a}+"
        catat(A, kode, f"PBPU usia {lab}: nonaktif karena premi", pw(g.np, g.w), "%", len(g), "tidak",
              "model tidak memakai usia; untuk cek realisme")
    catat(A, "A15", "PBPU dewasa: rata-rata usia", np.average(pb.usia, weights=pb.w), "tahun", len(pb), "ya")
    sd = np.sqrt(np.average((pb.usia - np.average(pb.usia, weights=pb.w)) ** 2, weights=pb.w))
    catat(A, "A16", "PBPU dewasa: simpangan baku usia", sd, "tahun", len(pb), "ya")
    th = pb.PSTV16
    for (a, b), kode, lab in [((0, 2016), "A17", "terdaftar s.d. 2016"), ((2017, 2021), "A18", "masuk 2017-2021"),
                              ((2022, 2023), "A19", "masuk 2022-2023"), ((2024, 2024), "A20", "masuk 2024")]:
        g = pb[(th >= a) & (th <= b)]
        catat(A, kode, f"PBPU dewasa {lab} (tahun sampel): nonaktif karena premi", pw(g.np, g.w), "%",
              len(g), "tidak")
    k = pb_semua.groupby("PSTV02").np.agg(["size", "sum"])
    k = k[k["size"] >= 2]
    catat(A, "A21", "KK PBPU (>= 2 anggota di sampel): semua anggota status premi sama",
          100 * ((k["sum"] == 0) | (k["sum"] == k["size"])).mean(), "% KK", len(k), "tidak",
          "dukungan untuk satu tindakan per KK; tak berbobot")

    # ---------- B. layanan rumah sakit saat berstatus PBPU
    F = m("fkrtl")
    F = F[F.FKL12.astype(str).eq("PBPU")].copy()
    F["ritl"] = F.FKL10.astype(str).eq("RITL")
    F["biaya"] = pd.to_numeric(F.FKL48, errors="coerce").astype(float)
    F["w"] = F.PSTV15.astype(float)
    F["besar"] = F.ritl | (F.biaya >= KLAIM_BESAR)
    B = "B_layanan"
    ri_n = F[F.ritl].groupby("PSTV01").size()
    rj_n = F[~F.ritl].groupby("PSTV01").size()
    lama = pb[pb.PSTV16 <= 2022]
    baru = pb[pb.PSTV16 == 2024]
    b1 = pw(lama.index.isin(ri_n.index), lama.w)
    b2 = pw(baru.index.isin(ri_n.index), baru.w)
    catat(B, "B01", "PBPU dewasa lama (tahun sampel <= 2022): punya >= 1 rawat inap 2024", b1, "%", len(lama), "ya")
    catat(B, "B02", "PBPU dewasa baru (tahun sampel 2024): punya >= 1 rawat inap 2024", b2, "%", len(baru), "ya")
    catat(B, "B03", "rasio rawat inap peserta baru / lama", b2 / b1, "x", len(baru), "ya", des=2)
    catat(B, "B04", "PBPU dewasa lama: klaim rawat inap per 100 orang per tahun",
          100 * np.average(ri_n.reindex(lama.index).fillna(0), weights=lama.w), "per 100", len(lama), "ya")
    catat(B, "B05", "PBPU dewasa lama: punya >= 1 rawat jalan RS 2024", pw(lama.index.isin(rj_n.index), lama.w),
          "%", len(lama), "ya")
    catat(B, "B06", "PBPU dewasa lama: kunjungan rawat jalan RS per orang per tahun",
          np.average(rj_n.reindex(lama.index).fillna(0), weights=lama.w), "kunjungan", len(lama), "ya", des=2)
    ri = F[F.ritl & F.biaya.notna()]
    rj = F[~F.ritl & F.biaya.notna()]
    catat(B, "B07", "biaya rawat inap: median", qw(ri.biaya, ri.w, .5), "Rp", len(ri), "ya", des=-3)
    catat(B, "B08", "biaya rawat inap: persentil 90", qw(ri.biaya, ri.w, .9), "Rp", len(ri), "ya", des=-3)
    catat(B, "B09", "biaya rawat inap: rata-rata", np.average(ri.biaya, weights=ri.w), "Rp", len(ri), "ya", des=-3)
    catat(B, "B10", "biaya rawat jalan RS: median", qw(rj.biaya, rj.w, .5), "Rp", len(rj), "ya", des=-3)
    catat(B, "B11", "biaya rawat jalan RS: persentil 90", qw(rj.biaya, rj.w, .9), "Rp", len(rj), "ya", des=-3)
    catat(B, "B12", "rawat jalan RS dengan biaya >= Rp1 juta", pw(rj.biaya >= KLAIM_BESAR, rj.w), "% klaim",
          len(rj), "ya")
    los = (F.FKL04 - F.FKL03).dt.days
    catat(B, "B13", "lama rawat inap (tgl pulang - tgl datang): rata-rata", np.average(los[F.ritl], weights=F.w[F.ritl]),
          "hari", int(F.ritl.sum()), "ya", des=2)
    kr = ri.FKL13.astype(str)
    m1, m3 = ri[kr.eq("KELAS 1")], ri[kr.eq("KELAS 3")]
    catat(B, "B14", "rasio median biaya rawat inap kelas 1 / kelas 3", qw(m1.biaya, m1.w, .5) / qw(m3.biaya, m3.w, .5),
          "x", min(len(m1), len(m3)), "ya", des=2)
    catat(B, "B15", "porsi rawat inap di antara semua klaim RS", pw(F.ritl, F.w), "% klaim", len(F), "ya")
    catat_ri_per_usia(B, lama, ri_n.index)

    # ---------- C. uji bayar saat butuh (potong-lintang)
    T = m("fktp")
    T = T[T.FKP12.astype(str).eq("PBPU")]
    ev_rs = pd.DataFrame({"PSTV01": F.PSTV01.values, "t": F.FKL04.values, "besar": F.besar.values})
    ev_tp = pd.DataFrame({"PSTV01": T.PSTV01.values, "t": T.FKP03.values, "besar": False})
    C = "C_bayar_saat_butuh"
    for nama_ev, ev, kode0, dipakai in [("klaim RS saja", ev_rs, 1, "ya"),
                                        ("FKTP + RS", pd.concat([ev_rs, ev_tp]), 11, "tidak")]:
        u = uji_pasca_klaim(pb, ev)
        kode = kode0
        for j, lab in [("jan_jun", "Jan-Jun"), ("jul_sep", "Jul-Sep"), ("okt_des", "Okt-Des")]:
            for kel, lk in [("tanpa", "tanpa klaim besar 2024"), ("pasca", f"<= {JEDA_PASCA} hari setelah klaim besar")]:
                p, n = u.get((j, kel), (np.nan, 0))
                catat(C, f"C{kode:02d}", f"aktivitas ({nama_ev}) terakhir {lab}, {lk}: nonaktif", p, "%", n, dipakai,
                      "aktivitas = tanggal pulang klaim RS" if kode0 == 1 else "aktivitas = kunjungan FKTP atau klaim RS")
                kode += 1
            p_t, n_t = u.get((j, "tanpa"), (np.nan, 0))
            p_p, n_p = u.get((j, "pasca"), (np.nan, 0))
            catat(C, f"C{kode:02d}", f"aktivitas ({nama_ev}) terakhir {lab}: rasio pasca / tanpa klaim besar",
                  p_p / p_t if p_t else np.nan, "x", min(n_t, n_p), dipakai, des=2)
            kode += 1

    # ---------- D. sinyal tambahan (belum ada di generator)
    D = "D_sinyal_tambahan"
    ev_seg = pd.concat([
        pd.DataFrame({"PSTV01": m("fkrtl").PSTV01.values, "t": m("fkrtl").FKL03.values,
                      "seg": m("fkrtl").FKL12.astype(str).values}),
        pd.DataFrame({"PSTV01": m("fktp").PSTV01.values, "t": m("fktp").FKP03.values,
                      "seg": m("fktp").FKP12.astype(str).values})])
    seg0 = ev_seg.sort_values("t").groupby("PSTV01").seg.first()
    dw = P[P.hidup & (P.usia >= 18)].set_index("PSTV01")
    dw = dw.assign(seg0=seg0.reindex(dw.index), seg1=dw.PSTV08.astype(str))
    for kode, (a, b) in zip(["D01", "D02", "D03", "D04"],
                            [("PBI APBD", "PBPU"), ("PBI APBN", "PBPU"), ("PPU", "PBPU"), ("PBPU", "PBPU")]):
        g = dw[dw.seg0.eq(a) & dw.seg1.eq(b)]
        catat(D, kode, f"segmen saat layanan pertama 2024 {a} -> potret akhir {b}: nonaktif", pw(g.np, g.w), "%",
              len(g), "tidak", "hanya pengguna layanan 2024")
    d2 = m("dx2")
    kron_rs = set(F.loc[F.FKL17A.astype(str).str.match(KRONIS), "PSTV01"])
    kron_rs |= set(m("fkrtl").loc[m("fkrtl").FKL02.isin(d2.loc[d2.FKL24A.astype(str).str.match(KRONIS), "FKL02"]),
                                  "PSTV01"])
    kron = kron_rs | set(T.loc[T.FKP14A.astype(str).str.match(KRONIS), "PSTV01"])
    ev = pd.concat([ev_rs, ev_tp])
    ev = ev[ev.PSTV01.isin(pb.index) & (ev.t >= AWAL) & (ev.t <= POTRET)]
    akhir = ev.groupby("PSTV01").t.max()
    jeda = (akhir - ev[ev.besar].groupby("PSTV01").t.max().reindex(akhir.index)).dt.days
    pasca = pb.loc[jeda[jeda <= JEDA_PASCA].index]
    for kode, nm, g in [("D05", "penyakit kronis", pasca[pasca.index.isin(kron)]),
                        ("D06", "bukan kronis", pasca[~pasca.index.isin(kron)])]:
        catat(D, kode, f"aktivitas terakhir <= {JEDA_PASCA} hari setelah klaim besar, {nm}: nonaktif",
              pw(g.np, g.w), "%", len(g), "tidak", "kronis = DM, hipertensi, jantung, CKD, PPOK, cuci darah")
    kmap = {"KELAS 1": 1, "KELAS 2": 2, "KELAS 3": 3}
    smap = {"KELAS I": 1, "KELAS II": 2, "KELAS III": 3}
    k_ri = F[F.ritl].sort_values("FKL04").groupby("PSTV01").FKL13.last().astype(str).map(kmap)
    g = pb.loc[pb.index.intersection(k_ri.index)]
    turun = g.PSTV07.astype(str).map(smap) > k_ri.reindex(g.index)
    sama = g.PSTV07.astype(str).map(smap) == k_ri.reindex(g.index)
    catat(D, "D07", "punya rawat inap; kelas potret lebih rendah dari kelas rawat inap terakhir: nonaktif",
          pw(g.np[turun], g.w[turun]), "%", int(turun.sum()), "tidak", "proxy turun kelas; lemah")
    catat(D, "D08", "punya rawat inap; kelas sama: nonaktif", pw(g.np[sama], g.w[sama]), "%", int(sama.sum()), "tidak")

    kp = m("kia_pst")
    kp = kp[kp.PSTV08.astype(str).eq("PBPU") & kp.PSTV18.isna()].set_index("PSTV01")
    kp = kp.assign(np=kp.PSTV17.astype(str).eq(NONAKTIF), w=kp.PSTV15.astype(float))
    kf = m("kia_fkrtl")
    kf = kf[kf.FKL12.astype(str).eq("PBPU")]
    sal = kf[kf.FKL17A.astype(str).str.match(PERSALINAN) | kf.FKL19.astype(str).str.startswith("O-6")]
    tgl_sal = sal.groupby("PSTV01").FKL04.max()
    x = kp.join(tgl_sal.rename("sal"), how="inner")
    x = x[(x.sal >= AWAL) & (x.sal <= POTRET)]
    for kode, (a, b), lab in [("D09", (1, 6), "Jan-Jun"), ("D10", (10, 12), "Okt-Des")]:
        g = x[x.sal.dt.month.between(a, b)]
        catat(D, kode, f"kohort KIA ibu, PBPU, melahirkan {lab} 2024: nonaktif", pw(g.np, g.w), "%", len(g), "tidak",
              "sampel kontekstual terpisah; tidak bisa digabung dengan sampel reguler")
    kt = m("kia_fktp")
    anc = kt[kt.FKP14A.astype(str).str.match(ANC)].groupby("PSTV01").FKP03.min()
    jeda_anc = (x.sal - anc.reindex(x.index)).dt.days
    ada = jeda_anc > 0
    catat(D, "D11", "kohort KIA ibu PBPU yang melahirkan: tercatat ANC (Z34-Z36) di FKTP sebelum persalinan",
          pw(ada, x.w), "%", len(x), "tidak")
    catat(D, "D12", "jeda ANC pertama ke persalinan: median", qw(jeda_anc[ada], x.w[ada], .5), "hari", int(ada.sum()),
          "tidak", des=0)
    return pd.DataFrame(BARIS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sampel", default=os.path.join("..", "02-full-project", "data_sample"),
                    help="folder Data Sampel BPJS (berisi folder 'Data Sampel Reguler Edisi 2025' dst.)")
    ap.add_argument("--cache", default=os.path.join("..", "02-full-project", "_cache_kalibrasi"),
                    help="folder cache baris-per-baris, DI LUAR repo")
    ap.add_argument("--out", default="kalibrasi")
    ap.add_argument("--hanya_baca", action="store_true", help="hanya isi cache, lalu berhenti")
    ap.add_argument("--tambahan", action="store_true",
                    help="hanya hitung B16-B20 (RAM kecil, tanpa cache) dan sisipkan ke CSV yang ada; "
                         "cek silang ke A15, A16, B01, B02")
    a = ap.parse_args()
    if a.tambahan:
        return sisipkan_tambahan(a)
    if os.path.abspath(a.cache).startswith(os.path.abspath(".") + os.sep):
        raise SystemExit("--cache tidak boleh di dalam repo: isinya data baris-per-baris.")
    os.makedirs(a.cache, exist_ok=True)
    if a.hanya_baca:
        for nama in TABEL:
            muat(nama, a.sampel, a.cache)
        return
    t = hitung(a.sampel, a.cache)
    os.makedirs(a.out, exist_ok=True)
    f = os.path.join(a.out, "target_sampel_bpjs_2024.csv")
    t.to_csv(f, index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.max_colwidth", 80):
        print(t[["kode", "uraian", "nilai", "satuan", "n_sampel"]].to_string(index=False))
    print(f"\nditulis: {f} ({len(t)} baris, agregat saja)")


if __name__ == "__main__":
    main()
