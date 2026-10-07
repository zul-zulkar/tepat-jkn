#!/usr/bin/env python3
"""
generate_data.py - TEPAT: generator data sintetis peserta JKN segmen PBPU/BP mandiri,
untuk prototipe Healthkathon 2026 (kategori Efisiensi Risiko pada Peserta).

Data ini fiktif. Tidak ada data peserta JKN atau data DTSEN asli di dalamnya.
Parameter perilaku dan biaya juga karangan kami, jadi kalibrasi dulu sebelum
mengutip angkanya.

Aturan JKN yang kami modelkan (disederhanakan):
  - Iuran porsi peserta: Kelas 1 Rp150.000, Kelas 2 Rp100.000, Kelas 3 Rp42.000.
  - Peserta baru membayar iuran pertama >= 14 hari setelah daftar, aktif sejak bayar.
  - Peserta nonaktif kalau ada bulan sebelum bulan berjalan yang belum ia bayar.
  - Peserta aktif lagi pada hari ia melunasi tunggakan (maks 24 bulan terakhir).
  - Denda pelayanan untuk rawat inap dalam 45 hari setelah reaktivasi
        = 5% x biaya x min(bulan tertunggak, 12), maksimal Rp30 juta.

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


IURAN = {1: 150_000, 2: 100_000, 3: 42_000}
TARIF_KELAS = {1: 1.2, 2: 1.1, 3: 1.0}

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


def p_bayar(seg, autodebet, d, shock):
    if seg == "patuh":
        return 0.995 if autodebet else 0.975
    if seg == "lalai":
        return 0.80 if autodebet else 0.60
    if seg == "tidak_mampu":
        if d >= shock:
            return 0.05
        return 0.95 if autodebet else 0.90
    return 0.02                  # reaktivasi_saat_butuh di luar masa "tahan"


def p_reaktivasi(seg, d, shock, jenis):
    base = {"patuh": 0.97, "lalai": 0.90, "reaktivasi_saat_butuh": 0.98}.get(seg)
    if seg == "tidak_mampu":
        base = 0.20 if d >= shock else 0.85
    if jenis == "rjtl_biasa":    # jarang ada yang melunasi tunggakan demi kunjungan ringan
        base *= 0.10 if seg == "reaktivasi_saat_butuh" else 0.35
    return base


def simulasi(n, seed):
    rng = np.random.default_rng(seed)

    n_w = 40
    pov = np.round(rng.beta(2, 7, n_w), 3)
    kode_w = [f"W{k:02d}" for k in range(1, n_w + 1)]
    wilayah = pd.DataFrame({"kode_wilayah": kode_w, "indeks_kemiskinan": pov})
    w_poor = pov / pov.sum()
    w_other = 0.7 / n_w + 0.3 * (1 - pov) / (1 - pov).sum()

    peserta, bayar_rows, status_rows, klaim_rows, dtsen_rows, label_rows = [], [], [], [], [], []
    cnt = {"bayar": 0, "klaim": 0, "episode": 0}

    for k in range(n):
        pid = f"P-{k + 1:06d}"
        seg = SEGMEN[rng.choice(4, p=SEG_P)]
        rsb = seg == "reaktivasi_saat_butuh"
        kelas = int(rng.choice([1, 2, 3], p=KELAS_P[seg]))
        iuran = IURAN[kelas]
        usia = int(np.clip(rng.normal(48 if rsb else 42, 13 if rsb else 14), 18, 85))
        jk = "L" if rng.random() < 0.5 else "P"
        wil = kode_w[rng.choice(n_w, p=w_poor if seg == "tidak_mampu" else w_other)]
        baru = rng.random() < (0.35 if rsb else 0.20)
        pengakal = rsb and rng.random() < P_PENGAKAL
        f_usia = float(np.clip(0.6 + (usia - 18) / 40, 0.6, 2.2))

        # guncangan ekonomi (hanya segmen tidak_mampu)
        shock = INF
        shock_pra = False
        if seg == "tidak_mampu":
            if rng.random() < 0.25:
                shock, shock_pra = WIN_START - 1, True
            else:
                shock = int(rng.integers(WIN_START, WIN_END - 120))

        settled = [INF] * N_MONTH            # hari lunas tiap bulan kewajiban
        reakt = []                           # (hari, bulan_tertunggak)
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
            cfg = JENIS[jenis]
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
        for jenis, cfg in JENIS.items():
            rate = cfg["rate"] * f_usia * (MULT_SERIUS_RSB if (rsb and jenis in SERIUS) else 1.0)
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
                p = 1.0 if d <= hold[0] else p_bayar(seg, autodebet, d, shock)
                if rng.random() < p:
                    ada_tunggakan = any(settled[j] == INF for j in range(i0, i))
                    kanal = "autodebet" if (autodebet and not ada_tunggakan) else kanal_lunas()
                    bayar(d, i, kanal)
            elif typ == "onset":
                jenis = payload
                if not aktif(d):
                    if rng.random() >= p_reaktivasi(seg, d, shock, jenis):
                        continue         # tidak berobat lewat JKN
                    bayar(d, month_of(d), kanal_lunas())
                jadwalkan(d, jenis)
            else:                        # layanan
                jenis, kelompok, eps = payload
                cfg = JENIS[jenis]
                if not aktif(d):
                    if rng.random() >= p_reaktivasi(seg, d, shock, jenis):
                        continue
                    bayar(d, month_of(d), kanal_lunas())
                biaya = int(round(cfg["biaya"] * TARIF_KELAS[kelas]
                                  * rng.lognormal(-cfg["sd"] ** 2 / 2, cfg["sd"]), -3))
                denda = 0
                if cfg["layanan"] == "RITL":
                    for r_day, n_t in reversed(reakt):
                        if r_day <= d:
                            if d - r_day <= 45:
                                denda = int(min(0.05 * biaya * min(n_t, 12), 30_000_000))
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

    # ---- rakit DataFrame ----
    def tgl(s):
        return pd.to_datetime(BASE) + pd.to_timedelta(s, unit="D")

    df_peserta = pd.DataFrame(peserta, columns=["id_peserta", "tgl_daftar", "kelas", "iuran_bulanan",
                                                "usia_2023", "jenis_kelamin", "kode_wilayah", "autodebet"])
    df_peserta["tgl_daftar"] = tgl(df_peserta["tgl_daftar"]).dt.date

    df_bayar = pd.DataFrame(bayar_rows, columns=["id_bayar", "id_peserta", "tgl_bayar", "periode_awal",
                                                 "periode_akhir", "jumlah_bulan_dibayar", "nominal", "kanal"])
    df_bayar["tgl_bayar"] = tgl(df_bayar["tgl_bayar"]).dt.date
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
    ap.add_argument("--n", type=int, default=20000, help="jumlah peserta")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data", help="folder keluaran")
    a = ap.parse_args()

    tabel = simulasi(a.n, a.seed)
    os.makedirs(a.out, exist_ok=True)
    for nama, df in tabel.items():
        df.to_csv(os.path.join(a.out, f"{nama}.csv"), index=False)
        print(f"{nama:20s} {len(df):>9,d} baris")


if __name__ == "__main__":
    main()
