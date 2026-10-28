#!/usr/bin/env python3
"""
generate_data.py - TEPAT: generator data sintetis peserta JKN segmen PBPU/BP mandiri,
untuk prototipe Healthkathon 2026 (kategori Efisiensi Risiko pada Peserta).

Data ini fiktif. Tidak ada data peserta JKN atau data DTSEN asli di dalamnya.

Dua profil parameter (--profil):
  - asumsi (bawaan): parameter karangan tim. Semua angka proposal, aplikasi, dan
    cocokkan_angka.py memakai profil ini, dan hasilnya identik dengan versi sebelum
    profil ada.
  - sampel2024: parameter yang bisa diamati dikalibrasi ke angka agregat Data Sampel
    BPJS Kesehatan 2024 (kalibrasi/target_sampel_bpjs_2024.csv, dibuat oleh
    kalibrasi_sampel.py; dibandingkan oleh cek_realisme.py). Lihat PROFIL di bawah.
    Perilaku iuran (segmen laten) tetap tidak teramati di data sampel, jadi angka
    deteksi di profil ini tetap uji pipeline, bukan performa.

Aturan JKN yang kami modelkan (disederhanakan; rujukan lengkap ada di README):
  - Cakupan analisis: PBPU/BP yang iurannya dibayar sendiri. Peserta PPU, PBI, dan
    PBPU/BP yang iurannya dibayar Pemda dibuat terpisah (--n_lain) supaya model bisa
    mengeluarkannya. Denda tidak berlaku bagi PBI dan PBPU/BP-Pemda (Perpres 59/2024
    Ps. 42 ayat 8); denda PPU ditanggung pemberi kerja (Ps. 42 ayat 7).
  - Iuran per orang per bulan: Kelas 1 Rp150.000, Kelas 2 Rp100.000, Kelas 3 Rp42.000
    (Rp35.000 dibayar peserta + Rp7.000 bantuan pemerintah; Perpres 64/2020 Ps. 34
    ayat 1 huruf b). Prototipe menagih Rp42.000 penuh untuk kelas 3, termasuk bulan
    tertunggak. Bantuan hanya untuk peserta aktif (Ps. 34 ayat 4), jadi porsi yang
    ditagih untuk bulan tertunggak masih TERBUKA.
  - Peserta baru membayar iuran pertama >= 14 hari setelah daftar, aktif sejak bayar.
    Dasar hukum masa tunggu ini belum kami verifikasi (TERBUKA).
  - Penjaminan dihentikan sementara per Peserta kalau ada bulan sebelum bulan berjalan
    yang belum dibayar (Perpres 59/2024 Ps. 42 ayat 1).
  - Peserta aktif lagi pada hari ia melunasi tunggakan, paling banyak 24 bulan
    (Ps. 42 ayat 3).
  - Denda pelayanan untuk SATU KALI rawat inap tingkat lanjutan dalam 45 hari sejak
    aktif kembali = 5% x biaya x min(bulan tertunggak, 12), paling tinggi Rp20 juta
    (Ps. 42 ayat 5-6). "Biaya" di sini biaya klaim sintetis, bukan paket INA-CBG.
    Angka 2,5% dan Rp30 juta hanya untuk skema transisi 2020 (ayat 6a), tidak dipakai.
  - Unit simulasi adalah peserta. Tagihan kolektif per KK (Peraturan BPJS 5/2018
    Ps. 12 ayat 4 dan Ps. 14 ayat 4) belum dimodelkan.

Segmen laten (ground truth). Generator menyimpan label di tabel terpisah. Jangan
pakai label itu untuk melatih model yang kamu sebut "tanpa label".
  - patuh                  : bayar rutin.
  - lalai                  : mampu, sering bolong, lalu melunasi.
  - tidak_mampu            : bayar rutin sampai kena guncangan ekonomi, lalu berhenti.
  - reaktivasi_saat_butuh  : nyaris tidak membayar, melunasi menjelang layanan
                             mahal, lalu berhenti lagi.
    Sebagian segmen ini "pengakal_45": mereka menunda rawat inap terjadwal sampai
    lewat hari ke-45 setelah reaktivasi supaya tidak kena denda pelayanan.

Flag DTSEN berbentuk biner (rentang desil 1-5 atau 6-10) dengan satu tanggal
pemutakhiran. Orang yang jatuh miskin setelah tanggal itu sering masih tercatat 6-10.

Pemakaian:
    python generate_data.py --n 20000 --seed 2026 --out data
    python generate_data.py --n 20000 --seed 2026 --profil sampel2024 --out data_sampel2024
    (--n = peserta PBPU/BP mandiri; --n_lain = peserta segmen lain, bawaan 15% dari n)
"""
import argparse
import bisect
import heapq
import math
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

INF = math.inf
BASE = date(2021, 1, 1)          # indeks bulan 0 = Jan 2021
N_MONTH = 60                     # Jan 2021 .. Des 2025
WIN_I0 = 24                      # jendela observasi mulai Jan 2023


def _month_start(i):
    y, m = divmod(i, 12)
    return (date(2021 + y, m + 1, 1) - BASE).days


MS = [_month_start(i) for i in range(N_MONTH + 1)]
WIN_START = MS[WIN_I0]           # 2023-01-01
WIN_END = MS[N_MONTH] - 1        # 2025-12-31
SNAPSHOT_DTSEN = (date(2025, 1, 1) - BASE).days


def month_of(d):
    return bisect.bisect_right(MS, d) - 1


def to_date(d):
    return BASE + timedelta(days=int(d))


def ym(i):
    y, m = divmod(i, 12)
    return f"{2021 + y}-{m + 1:02d}"


IURAN = {1: 150_000, 2: 100_000, 3: 42_000}   # Perpres 64/2020 Ps. 34 ayat (1) huruf b
TARIF_KELAS = {1: 1.2, 2: 1.1, 3: 1.0}

# Denda pelayanan, Perpres 59/2024 Ps. 42 ayat (5)-(6)
JENDELA_DENDA = 45               # hari sejak status aktif kembali
DENDA_PERSEN = 0.05              # per bulan tertunggak
DENDA_MAKS_BULAN = 12
DENDA_MAKS = 20_000_000


def hitung_denda(biaya, bulan_tertunggak):
    return int(min(DENDA_PERSEN * biaya * min(bulan_tertunggak, DENDA_MAKS_BULAN), DENDA_MAKS))


# Segmen di luar cakupan (Perpres 59/2024 Ps. 42 ayat 7-8)
SEG_LAIN = ["PPU", "PBI", "PBPU_BP_Pemda"]
SEG_LAIN_P = [0.50, 0.35, 0.15]
PEMBAYAR = {"PPU": "pemberi_kerja", "PBI": "pemerintah_pusat", "PBPU_BP_Pemda": "pemerintah_daerah"}

SEGMEN = ["patuh", "lalai", "tidak_mampu", "reaktivasi_saat_butuh"]
SEG_P = [0.52, 0.25, 0.13, 0.10]
KELAS_P = {
    "patuh": [0.25, 0.35, 0.40],
    "lalai": [0.20, 0.35, 0.45],
    "tidak_mampu": [0.05, 0.15, 0.80],
    "reaktivasi_saat_butuh": [0.20, 0.30, 0.50],
}
P_PENGAKAL = 0.45                # porsi reaktivasi_saat_butuh yang mengakali batas 45 hari

# Laju kejadian kebutuhan layanan per orang-tahun (dikalikan faktor usia).
JENIS = {
    "rjtl_biasa": dict(rate=0.80, layanan="RJTL", masuk="poli", biaya=300_000, sd=0.5,
                       kelompok=["konsultasi_spesialis", "pemeriksaan_penunjang", "kontrol_rutin"]),
    "rjtl_seri": dict(rate=0.012, layanan="RJTL", masuk="poli", biaya=2_500_000, sd=0.3,
                      kelompok=["kemoterapi", "radioterapi", "rehabilitasi_medik"]),
    "ritl_darurat": dict(rate=0.04, layanan="RITL", masuk="IGD", biaya=7_000_000, sd=0.6,
                         kelompok=["trauma", "infeksi_akut", "kardiovaskular_akut"]),
    "ritl_elektif": dict(rate=0.05, layanan="RITL", masuk="terjadwal", biaya=12_000_000, sd=0.5,
                         kelompok=["bedah_elektif", "persalinan_terencana", "prosedur_jantung"]),
}
SERIUS = {"rjtl_seri", "ritl_darurat", "ritl_elektif"}
MULT_SERIUS_RSB = 1.8            # seleksi adversal: segmen ini lebih sering butuh layanan mahal

# ---- profil parameter ------------------------------------------------------------------
# BAWAAN = profil "asumsi": nilai di atas, ditambah angka yang dulu tertulis langsung di
# simulasi(). Profil lain hanya menimpa kunci yang disebut.
BAWAAN = dict(
    SEG_P=SEG_P,                                  # patuh, lalai, tidak_mampu, reaktivasi_saat_butuh
    KELAS_P=KELAS_P,                              # porsi kelas 1/2/3 per segmen
    USIA={"rsb": (48, 13), "lain": (42, 14)},     # normal(rata-rata, sb), dipotong 18-85
    P_BARU={"rsb": 0.35, "lain": 0.20},           # porsi pendaftar baru dalam jendela
    P_SHOCK_PRA=0.25,                             # tidak_mampu yang sudah jatuh miskin sebelum 2023
    P_BAYAR_LALAI=(0.80, 0.60),                   # peluang bayar bulanan segmen lalai (autodebet, tidak)
    P_REAKT_RINGAN=(0.10, 0.35),                  # pengali peluang melunasi demi rawat jalan ringan (RSB, lain)
    P_PBPU=0.85,                                  # sisanya diberi label BP
    JENIS={},                                     # timpa rate/biaya/sd per jenis layanan
    TARIF_KELAS=TARIF_KELAS,
    MULT_SERIUS_RSB=MULT_SERIUS_RSB,
    KONTROL_RJTL=0.0,                             # rata-rata kontrol ulang bulanan per rawat jalan
)

# "sampel2024": dikalibrasi ke kalibrasi/target_sampel_bpjs_2024.csv (kode di komentar).
# Yang teramati di data sampel dan dikalibrasi: tingkat nonaktif PBPU (A01), BP (A03), kelas
# (A05-A10), usia (A15-A16), rawat inap dan rawat jalan RS (B01-B06), biaya (B07-B14), dan
# rasio nonaktif sesudah klaim besar (C01-C09).
# Yang TIDAK teramati: pembayaran bulanan, aktif kembali, dan segmen laten. SEG_P,
# P_SHOCK_PRA, P_BAYAR_LALAI, dan P_REAKT_RINGAN dipilih (dengan mencoba beberapa kombinasi
# dan membandingkannya lewat cek_realisme.py) supaya A01 dan C01-C09 cocok. Itu satu kombinasi
# yang cocok, bukan perkiraan proporsi segmen sebenarnya. P_PENGAKAL dan DTSEN tidak diubah.
# Belum cocok (lihat hasil_kalibrasi/realisme_sampel2024.csv): pendaftar baru 2024 di data nyata lebih
# cepat menunggak (A20), dan usia tidak dimodelkan sebagai faktor risiko (A11-A14).
PROFIL = {
    "asumsi": {},
    "sampel2024": dict(
        SEG_P=[0.40, 0.10, 0.42, 0.08],                        # A01 + C01-C09 (lihat catatan di atas)
        KELAS_P={s: [0.108, 0.144, 0.748] for s in SEGMEN},    # A05-A07; nonaktif datar per kelas (A08-A10)
        USIA={"rsb": (44.0, 16.4), "lain": (44.0, 16.4)},      # A15-A16; RSB tidak lagi lebih tua
        P_BARU={"rsb": 0.20, "lain": 0.12},                    # B02-B03
        P_SHOCK_PRA=0.90,                                      # A01: nonaktif menetap, bukan bolong acak
        P_BAYAR_LALAI=(0.90, 0.80),                            # C04, C07: lalai lebih jarang bolong
        P_REAKT_RINGAN=(0.05, 0.15),                           # C01-C09: jarang melunasi demi rawat jalan ringan
        P_PBPU=1.0,                                            # A03: BP hampir tidak pernah nonaktif karena premi
        JENIS={
            "rjtl_biasa": dict(rate=0.11, biaya=250_000, sd=0.75),       # B05-B06, B10-B12
            "rjtl_seri": dict(rate=0.004, biaya=800_000, sd=0.30),       # B10-B12
            "ritl_darurat": dict(rate=0.036, biaya=4_300_000, sd=0.65),  # B01, B04, B07-B09
            "ritl_elektif": dict(rate=0.044, biaya=4_900_000, sd=0.65),
        },
        TARIF_KELAS={1: 1.45, 2: 1.22, 3: 1.0},     # B14; kelas 2 = interpolasi (karangan)
        MULT_SERIUS_RSB=1.8,                        # tidak teramati; tetap
        KONTROL_RJTL=12.0,                          # B05-B06: pengguna sedikit, kontrol berulang
    ),
}


def parameter(profil):
    if profil not in PROFIL:
        raise ValueError(f"profil tidak dikenal: {profil} (pilihan: {', '.join(PROFIL)})")
    prm = {**BAWAAN, **PROFIL[profil]}
    prm["JENIS"] = {j: {**cfg, **prm["JENIS"].get(j, {})} for j, cfg in JENIS.items()}
    return prm


def p_bayar(seg, autodebet, d, shock, lalai=(0.80, 0.60)):
    if seg == "patuh":
        return 0.995 if autodebet else 0.975
    if seg == "lalai":
        return lalai[0] if autodebet else lalai[1]
    if seg == "tidak_mampu":
        if d >= shock:
            return 0.05
        return 0.95 if autodebet else 0.90
    return 0.02                  # reaktivasi_saat_butuh di luar masa "tahan"


def p_reaktivasi(seg, d, shock, jenis, ringan=(0.10, 0.35)):
    base = {"patuh": 0.97, "lalai": 0.90, "reaktivasi_saat_butuh": 0.98}.get(seg)
    if seg == "tidak_mampu":
        base = 0.20 if d >= shock else 0.85
    if jenis == "rjtl_biasa":    # jarang ada yang melunasi tunggakan demi kunjungan ringan
        base *= ringan[0] if seg == "reaktivasi_saat_butuh" else ringan[1]
    return base


def simulasi(n, seed, n_lain=0, profil="asumsi", wilayah_rsb=None):
    """wilayah_rsb: daftar kode wilayah (mis. ["W01", ..., "W05"]). Bila diisi, peserta
    reaktivasi_saat_butuh hanya ditempatkan di wilayah itu (dial konsentrasi). Undian acak
    lain tidak berubah, jadi peserta lain identik dengan data tanpa konsentrasi."""
    prm = parameter(profil)
    JP, TK = prm["JENIS"], prm["TARIF_KELAS"]
    rng = np.random.default_rng(seed)

    n_w = 40
    pov = np.round(rng.beta(2, 7, n_w), 3)
    kode_w = [f"W{k:02d}" for k in range(1, n_w + 1)]
    wilayah = pd.DataFrame({"kode_wilayah": kode_w, "indeks_kemiskinan": pov})
    w_poor = pov / pov.sum()
    w_other = 0.7 / n_w + 0.3 * (1 - pov) / (1 - pov).sum()
    w_rsb = None
    if wilayah_rsb:
        tidak_ada = set(wilayah_rsb) - set(kode_w)
        if tidak_ada:
            raise ValueError(f"wilayah tidak ada: {sorted(tidak_ada)}")
        w_rsb = np.where(np.isin(kode_w, list(wilayah_rsb)), w_other, 0.0)
        w_rsb = w_rsb / w_rsb.sum()

    peserta, bayar_rows, status_rows, klaim_rows, dtsen_rows, label_rows = [], [], [], [], [], []
    cnt = {"bayar": 0, "klaim": 0, "episode": 0}

    for k in range(n):
        pid = f"P-{k + 1:06d}"
        seg = SEGMEN[rng.choice(4, p=prm["SEG_P"])]
        rsb = seg == "reaktivasi_saat_butuh"
        kelas = int(rng.choice([1, 2, 3], p=prm["KELAS_P"][seg]))
        iuran = IURAN[kelas]
        usia = int(np.clip(rng.normal(*prm["USIA"]["rsb" if rsb else "lain"]), 18, 85))
        jk = "L" if rng.random() < 0.5 else "P"
        p_wil = w_poor if seg == "tidak_mampu" else (w_rsb if (rsb and w_rsb is not None) else w_other)
        wil = kode_w[rng.choice(n_w, p=p_wil)]
        baru = rng.random() < prm["P_BARU"]["rsb" if rsb else "lain"]
        pengakal = rsb and rng.random() < P_PENGAKAL
        f_usia = float(np.clip(0.6 + (usia - 18) / 40, 0.6, 2.2))

        # guncangan ekonomi (hanya segmen tidak_mampu)
        shock = INF
        shock_pra = False
        if seg == "tidak_mampu":
            if rng.random() < prm["P_SHOCK_PRA"]:
                shock, shock_pra = WIN_START - 1, True
            else:
                shock = int(rng.integers(WIN_START, WIN_END - 120))

        settled = [INF] * N_MONTH            # hari lunas tiap bulan kewajiban
        reakt = []                           # (hari, bulan_tertunggak)
        kena_denda = set()                   # reaktivasi yang dendanya sudah dipakai
        hari_bayar = []
        heap = []
        hold = [-INF]                        # reaktivasi_saat_butuh tetap bayar sampai hari ini

        # ---- kepesertaan awal ----
        if not baru:
            i0, act_start = 0, -INF
            tgl_daftar = (date(2016, 1, 1) - BASE).days + int(rng.integers(0, 365 * 5))
            autodebet = rng.random() < (0.20 if seg == "tidak_mampu" else 0.35)
            if seg == "lalai":
                k_pra = 0 if rng.random() < 0.6 else int(rng.integers(1, 5))
            elif seg == "tidak_mampu":
                k_pra = int(rng.integers(2, 13)) if shock_pra else 0
            elif rsb:
                k_pra = int(rng.integers(3, 19)) if rng.random() < 0.85 else 0
            else:
                k_pra = 0
            for i in range(0, WIN_I0 - k_pra):
                settled[i] = MS[i] + 2
            onset0 = None
        else:
            autodebet = rng.random() < 0.85
            if rsb:                          # daftar karena sudah butuh layanan
                onset0 = int(rng.integers(WIN_START + 20, MS[54]))
                tgl_daftar = onset0 - int(rng.integers(0, 8))
            else:
                onset0 = None
                tgl_daftar = int(rng.integers(WIN_START, MS[54]))
            act_start = tgl_daftar + 14 + int(rng.integers(0, 5))
            if seg == "tidak_mampu" and shock < act_start + 60:
                sisa = WIN_END - act_start - 60
                shock = act_start + 60 + (int(rng.integers(0, sisa)) if sisa > 0 else 0)
            i0 = month_of(act_start)
            settled[i0] = act_start
            cnt["bayar"] += 1
            bayar_rows.append((f"B-{cnt['bayar']:08d}", pid, act_start, ym(i0), ym(i0), 1, iuran,
                               "autodebet" if autodebet else "va_bank"))

        def aktif(d):
            if d < act_start:
                return False
            for j in range(i0, month_of(d)):
                if settled[j] > d:
                    return False
            return True

        def bayar(d, i_upto, kanal):
            mi = month_of(d)
            out = [j for j in range(i0, i_upto + 1) if settled[j] == INF]
            if not out:
                return False
            n_tunggak = sum(1 for j in out if j < mi)
            charged = [j for j in out if j >= i_upto - 23]
            for j in out:
                settled[j] = d
            hari_bayar.append(d)
            if d >= WIN_START:
                cnt["bayar"] += 1
                bayar_rows.append((f"B-{cnt['bayar']:08d}", pid, d, ym(charged[0]), ym(i_upto),
                                   len(charged), len(charged) * iuran, kanal))
            if n_tunggak > 0:
                reakt.append((d, min(n_tunggak, 24)))
                return True
            return False

        def kanal_lunas():
            return ["va_bank", "minimarket", "mobile_jkn"][int(rng.integers(0, 3))]

        def jadwalkan(t, jenis, kelompok=None):
            cfg = JP[jenis]
            if kelompok is None:
                opsi = [g for g in cfg["kelompok"]
                        if not (g == "persalinan_terencana" and (jk == "L" or usia > 45))]
                kelompok = opsi[int(rng.integers(0, len(opsi)))]
            cnt["episode"] += 1
            eps = f"E-{cnt['episode']:07d}"
            if jenis == "ritl_darurat":
                hari = [t]
            elif jenis == "rjtl_biasa":
                hari = [t + int(rng.integers(0, 4))]
                if prm["KONTROL_RJTL"] > 0:      # kontrol ulang bulanan, hanya bila sedang aktif
                    for v in range(1, 1 + int(rng.poisson(prm["KONTROL_RJTL"]))):
                        heapq.heappush(heap, (hari[0] + 30 * v, 3, "layanan", (jenis, kelompok, eps, "kontrol")))
            elif jenis == "ritl_elektif":
                adm = t + 1 + int(round(rng.gamma(2.0, 12.0)))
                if pengakal and reakt:
                    r_last, n_last = reakt[-1]
                    if 0 <= adm - r_last <= 45:
                        adm = r_last + 46 + int(rng.exponential(4.0))
                hari = [adm]
            else:                            # rjtl_seri: kunjungan mingguan 3-6 bulan
                mulai = t + int(rng.integers(0, 8))
                hari = [mulai + 7 * v for v in range(int(rng.integers(12, 26)))]
            for h in hari:
                heapq.heappush(heap, (h, 3, "layanan", (jenis, kelompok, eps)))
            if rsb:
                hold[0] = max(hold[0], hari[-1] + 20)

        # ---- antrean kejadian ----
        start_i = max(WIN_I0, i0 + (1 if baru else 0))
        for i in range(start_i, N_MONTH):
            heapq.heappush(heap, (MS[i] + int(rng.integers(0, 10)), 1, "bayar", i))
        t_from = WIN_START if not baru else act_start
        tahun = max(0.0, (WIN_END - t_from) / 365.25)
        for jenis, cfg in JP.items():
            rate = cfg["rate"] * f_usia * (prm["MULT_SERIUS_RSB"] if (rsb and jenis in SERIUS) else 1.0)
            for _ in range(rng.poisson(rate * tahun)):
                heapq.heappush(heap, (int(rng.integers(t_from, WIN_END + 1)), 2, "onset", jenis))
        if onset0 is not None:
            jadwalkan(act_start, "ritl_elektif" if rng.random() < 0.65 else "rjtl_seri")

        while heap:
            d, _, typ, payload = heapq.heappop(heap)
            if d > WIN_END:
                continue
            if typ == "bayar":
                i = payload
                if settled[i] != INF:
                    continue
                p = 1.0 if d <= hold[0] else p_bayar(seg, autodebet, d, shock, prm["P_BAYAR_LALAI"])
                if rng.random() < p:
                    ada_tunggakan = any(settled[j] == INF for j in range(i0, i))
                    kanal = "autodebet" if (autodebet and not ada_tunggakan) else kanal_lunas()
                    bayar(d, i, kanal)
            elif typ == "onset":
                jenis = payload
                if not aktif(d):
                    if rng.random() >= p_reaktivasi(seg, d, shock, jenis, prm["P_REAKT_RINGAN"]):
                        continue         # tidak berobat lewat JKN
                    bayar(d, month_of(d), kanal_lunas())
                jadwalkan(d, jenis)
            else:                        # layanan
                jenis, kelompok, eps = payload[:3]
                cfg = JP[jenis]
                if not aktif(d):
                    if len(payload) > 3:         # kontrol ulang tidak memicu pelunasan tunggakan
                        continue
                    if rng.random() >= p_reaktivasi(seg, d, shock, jenis, prm["P_REAKT_RINGAN"]):
                        continue
                    bayar(d, month_of(d), kanal_lunas())
                biaya = int(round(cfg["biaya"] * TK[kelas]
                                  * rng.lognormal(-cfg["sd"] ** 2 / 2, cfg["sd"]), -3))
                denda = 0
                if cfg["layanan"] == "RITL":
                    for r_day, n_t in reversed(reakt):
                        if r_day <= d:
                            # hanya satu kali rawat inap per reaktivasi (Ps. 42 ayat 5)
                            if d - r_day <= JENDELA_DENDA and r_day not in kena_denda:
                                denda = hitung_denda(biaya, n_t)
                                kena_denda.add(r_day)
                            break
                    los = 1 + int(rng.poisson(3 if jenis == "ritl_darurat" else 2))
                else:
                    los = 0
                cnt["klaim"] += 1
                klaim_rows.append((f"K-{cnt['klaim']:08d}", pid, eps, d, d + los, cfg["layanan"],
                                   cfg["masuk"], kelompok, kelas, biaya, denda))

        # ---- riwayat status (dihitung dari hari lunas final) ----
        kandidat = {max(WIN_START, tgl_daftar)}
        kandidat.update(MS[i] for i in range(WIN_I0, N_MONTH))
        kandidat.update(hari_bayar)
        if baru:
            kandidat.add(act_start)
        kandidat = sorted(c for c in kandidat if max(WIN_START, tgl_daftar) <= c <= WIN_END)
        seq = []
        for c in kandidat:
            st = "masa_tunggu" if c < act_start else ("aktif" if aktif(c) else "nonaktif")
            if not seq or seq[-1][1] != st:
                seq.append((c, st))
        for idx, (c, st) in enumerate(seq):
            akhir = seq[idx + 1][0] - 1 if idx + 1 < len(seq) else WIN_END
            status_rows.append((pid, c, akhir, st))

        # ---- flag DTSEN biner dengan jeda pembaruan ----
        if rng.random() < 0.92:
            if seg == "tidak_mampu":
                p15 = 0.85 if shock <= SNAPSHOT_DTSEN else 0.20
            else:
                p15 = {"patuh": 0.08, "lalai": 0.15, "reaktivasi_saat_butuh": 0.15}[seg]
            dtsen_rows.append((pid, "1-5" if rng.random() < p15 else "6-10", SNAPSHOT_DTSEN))

        peserta.append((pid, tgl_daftar, kelas, iuran, usia, jk, wil, bool(autodebet)))
        label_rows.append((pid, seg, bool(pengakal), bool(baru),
                           None if shock == INF else int(shock)))

    # ---- segmen di luar cakupan: PPU, PBI, PBPU/BP yang dibayar Pemda ----
    # RNG terpisah supaya data PBPU/BP mandiri di atas tidak berubah.
    seg_kepesertaan = list(np.where(np.random.default_rng([seed, 1]).random(n) < prm["P_PBPU"], "PBPU", "BP"))
    pembayar = ["peserta"] * n
    rng_l = np.random.default_rng([seed, 2])
    tahun_win = (WIN_END - WIN_START) / 365.25
    for k in range(n_lain):
        pid = f"P-{n + k + 1:06d}"
        sk = SEG_LAIN[rng_l.choice(3, p=SEG_LAIN_P)]
        kelas = int(rng_l.choice([1, 2], p=[0.4, 0.6])) if sk == "PPU" else 3
        iuran = None if sk == "PPU" else IURAN[3]    # PPU: persentase upah, tidak dimodelkan
        usia = int(np.clip(rng_l.normal(40, 13), 18, 85))
        jk = "L" if rng_l.random() < 0.5 else "P"
        wil = kode_w[rng_l.choice(n_w, p=w_poor if sk == "PBI" else w_other)]
        tgl_daftar = (date(2016, 1, 1) - BASE).days + int(rng_l.integers(0, 365 * 5))
        f_usia = float(np.clip(0.6 + (usia - 18) / 40, 0.6, 2.2))

        # PBI dan Pemda selalu aktif. Sebagian PPU nonaktif sementara karena pemberi kerja
        # menunggak, lalu aktif lagi setelah pemberi kerja melunasi (bukan keputusan peserta).
        tunggak = None
        if sk == "PPU" and rng_l.random() < 0.10:
            i = int(rng_l.integers(WIN_I0 + 1, N_MONTH - 6))
            n_bln = int(rng_l.integers(1, 5))
            tunggak = (MS[i], MS[i + n_bln] + int(rng_l.integers(0, 10)), n_bln)
        if tunggak:
            a, r, _ = tunggak
            status_rows.extend([(pid, WIN_START, a - 1, "aktif"), (pid, a, r - 1, "nonaktif"),
                                (pid, r, WIN_END, "aktif")])
        else:
            status_rows.append((pid, WIN_START, WIN_END, "aktif"))

        if sk == "PPU":
            for j in range(WIN_I0, N_MONTH):
                if tunggak and tunggak[0] <= MS[j] <= tunggak[1]:
                    continue
                cnt["bayar"] += 1
                bayar_rows.append((f"B-{cnt['bayar']:08d}", pid, MS[j] + int(rng_l.integers(0, 10)),
                                   ym(j), ym(j), 1, None, "pemberi_kerja"))
            if tunggak:
                i_a, i_r = month_of(tunggak[0]), month_of(tunggak[1])
                cnt["bayar"] += 1
                bayar_rows.append((f"B-{cnt['bayar']:08d}", pid, tunggak[1], ym(i_a), ym(i_r),
                                   i_r - i_a + 1, None, "pemberi_kerja"))

        kunjungan = []
        for jenis, cfg in JP.items():
            for _ in range(rng_l.poisson(cfg["rate"] * f_usia * tahun_win)):
                t = int(rng_l.integers(WIN_START, WIN_END + 1))
                opsi = [g for g in cfg["kelompok"]
                        if not (g == "persalinan_terencana" and (jk == "L" or usia > 45))]
                kelompok = opsi[int(rng_l.integers(0, len(opsi)))]
                cnt["episode"] += 1
                eps = f"E-{cnt['episode']:07d}"
                if jenis == "ritl_darurat":
                    hari = [t]
                elif jenis == "rjtl_biasa":
                    hari = [t + int(rng_l.integers(0, 4))]
                elif jenis == "ritl_elektif":
                    hari = [t + 1 + int(round(rng_l.gamma(2.0, 12.0)))]
                else:
                    mulai = t + int(rng_l.integers(0, 8))
                    hari = [mulai + 7 * v for v in range(int(rng_l.integers(12, 26)))]
                for h in hari:
                    biaya = int(round(cfg["biaya"] * TK[kelas]
                                      * rng_l.lognormal(-cfg["sd"] ** 2 / 2, cfg["sd"]), -3))
                    los = 1 + int(rng_l.poisson(3 if jenis == "ritl_darurat" else 2)) \
                        if cfg["layanan"] == "RITL" else 0
                    kunjungan.append((h, jenis, kelompok, eps, biaya, los))
        denda_dipakai = False
        for h, jenis, kelompok, eps, biaya, los in sorted(kunjungan):
            if h > WIN_END or (tunggak and tunggak[0] <= h < tunggak[1]):
                continue                 # di luar jendela, atau sedang dihentikan sementara
            cfg = JP[jenis]
            denda = 0
            if (cfg["layanan"] == "RITL" and tunggak and not denda_dipakai
                    and 0 <= h - tunggak[1] <= JENDELA_DENDA):
                denda = hitung_denda(biaya, tunggak[2])   # ditanggung pemberi kerja (ayat 7)
                denda_dipakai = True
            cnt["klaim"] += 1
            klaim_rows.append((f"K-{cnt['klaim']:08d}", pid, eps, h, h + los, cfg["layanan"],
                               cfg["masuk"], kelompok, kelas, biaya, denda))

        if rng_l.random() < 0.92:
            p15 = {"PPU": 0.10, "PBI": 0.90, "PBPU_BP_Pemda": 0.70}[sk]
            dtsen_rows.append((pid, "1-5" if rng_l.random() < p15 else "6-10", SNAPSHOT_DTSEN))
        peserta.append((pid, tgl_daftar, kelas, iuran, usia, jk, wil, False))
        label_rows.append((pid, "di_luar_cakupan", False, False, None))
        seg_kepesertaan.append(sk)
        pembayar.append(PEMBAYAR[sk])

    # ---- rakit DataFrame ----
    def tgl(s):
        return pd.to_datetime(BASE) + pd.to_timedelta(s, unit="D")

    df_peserta = pd.DataFrame(peserta, columns=["id_peserta", "tgl_daftar", "kelas", "iuran_bulanan",
                                                "usia_2023", "jenis_kelamin", "kode_wilayah", "autodebet"])
    df_peserta["tgl_daftar"] = tgl(df_peserta["tgl_daftar"]).dt.date
    df_peserta["iuran_bulanan"] = df_peserta["iuran_bulanan"].astype("Int64")
    df_peserta["segmen_kepesertaan"] = seg_kepesertaan
    df_peserta["pembayar_iuran"] = pembayar

    df_bayar = pd.DataFrame(bayar_rows, columns=["id_bayar", "id_peserta", "tgl_bayar", "periode_awal",
                                                 "periode_akhir", "jumlah_bulan_dibayar", "nominal", "kanal"])
    df_bayar["tgl_bayar"] = tgl(df_bayar["tgl_bayar"]).dt.date
    df_bayar["nominal"] = df_bayar["nominal"].astype("Int64")
    df_bayar = df_bayar.sort_values(["id_peserta", "tgl_bayar"]).reset_index(drop=True)

    df_status = pd.DataFrame(status_rows, columns=["id_peserta", "tgl_mulai", "tgl_selesai", "status"])
    df_status["tgl_mulai"] = tgl(df_status["tgl_mulai"]).dt.date
    df_status["tgl_selesai"] = tgl(df_status["tgl_selesai"]).dt.date

    df_klaim = pd.DataFrame(klaim_rows, columns=["id_klaim", "id_peserta", "id_episode", "tgl_masuk",
                                                 "tgl_keluar", "jenis_layanan", "cara_masuk",
                                                 "kelompok_layanan", "kelas_rawat", "biaya_klaim",
                                                 "denda_pelayanan"])
    df_klaim["tgl_masuk"] = tgl(df_klaim["tgl_masuk"]).dt.date
    df_klaim["tgl_keluar"] = tgl(df_klaim["tgl_keluar"]).dt.date
    df_klaim = df_klaim.sort_values(["id_peserta", "tgl_masuk"]).reset_index(drop=True)

    df_dtsen = pd.DataFrame(dtsen_rows, columns=["id_peserta", "rentang_desil", "tgl_pemutakhiran"])
    df_dtsen["tgl_pemutakhiran"] = tgl(df_dtsen["tgl_pemutakhiran"]).dt.date

    df_label = pd.DataFrame(label_rows, columns=["id_peserta", "segmen", "pengakal_45",
                                                 "peserta_baru", "tgl_guncangan"])
    df_label["tgl_guncangan"] = df_label["tgl_guncangan"].map(
        lambda s: None if pd.isna(s) else to_date(s))

    return {
        "wilayah": wilayah,
        "peserta": df_peserta,
        "pembayaran": df_bayar,
        "riwayat_status": df_status,
        "klaim": df_klaim,
        "dtsen_flag": df_dtsen,
        "label_ground_truth": df_label,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20000, help="jumlah peserta PBPU/BP mandiri")
    ap.add_argument("--n_lain", type=int, default=None,
                    help="jumlah peserta PPU, PBI, dan PBPU/BP-Pemda (bawaan: 15%% dari n)")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data", help="folder keluaran")
    ap.add_argument("--profil", default="asumsi", choices=list(PROFIL),
                    help="asumsi (bawaan, angka proposal) atau sampel2024 (dikalibrasi ke data sampel BPJS)")
    a = ap.parse_args()
    n_lain = round(0.15 * a.n) if a.n_lain is None else a.n_lain

    tabel = simulasi(a.n, a.seed, n_lain, profil=a.profil)
    os.makedirs(a.out, exist_ok=True)
    if a.profil != "asumsi":
        with open(os.path.join(a.out, "profil.txt"), "w", encoding="utf-8") as f:
            f.write(f"profil={a.profil} seed={a.seed} n={a.n} n_lain={n_lain}\n")
    for nama, df in tabel.items():
        df.to_csv(os.path.join(a.out, f"{nama}.csv"), index=False)
        print(f"{nama:20s} {len(df):>9,d} baris")


if __name__ == "__main__":
    main()
