#!/usr/bin/env python3
"""
kasus_jujur.py - TEPAT: populasi uji "orang jujur yang mirip curang" dan satu jenis
curang yang ditahan (hold-out). Salinan generate_data.py (commit e53b6d2) dengan perubahan
yang ditandai "KASUS JUJUR". Dipakai untuk N03/N04 dan target T3/T5 pra-registrasi.

Lima jenis, jumlah sama persis (n / 5 per jenis):
  - jatuh_miskin_sakit     (jujur): rutin bayar, satu kali sakit berat (rawat inap lalu
                            perawatan lanjutan), penghasilan hilang saat itu; melunasi untuk
                            berobat, lalu berhenti.
  - kronis_bolong_sekali   (jujur): sering berobat seri (cuci darah/kemoterapi), bayar rutin,
                            bolong tepat satu bulan, lalu melunasi.
  - pembayar_musiman       (jujur): melunasi semua tunggakan saat panen (Mar-Apr, Agu-Sep),
                            jarang bayar di bulan lain. Tanpa autodebet.
  - baru_sakit_tetap_bayar (jujur): mendaftar karena sedang sakit, lalu terus bayar rutin.
  - baru_berhenti_cepat    (bayar-saat-butuh, DITAHAN): mendaftar karena butuh layanan,
                            lalu berhenti bayar; saat data berakhir tunggakannya 3-5 bulan,
                            di bawah batas 6 bulan aturan TEPAT.

Pakai (dari folder utama repo):
    python bukti/kasus_jujur.py --n 2500 --seed 2026 --n_lain 0 --out bukti/data_jujur

Tabel wilayah sama persis dengan data dasar (seed yang sama); semua orang memakai RNG
[seed, 3], jadi data dasar seed 2026 tidak berubah. ID peserta diawali "J-" supaya tidak
tertukar dengan ID data dasar. Label tetap di label_ground_truth.csv, hanya untuk menilai.
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

# KASUS JUJUR: lima jenis, jumlah sama persis
SEGMEN = ["jatuh_miskin_sakit", "kronis_bolong_sekali", "pembayar_musiman",
          "baru_sakit_tetap_bayar", "baru_berhenti_cepat"]
RSB_SEG = {"baru_berhenti_cepat"}            # satu-satunya jenis bayar-saat-butuh
BULAN_PANEN = {3, 4, 8, 9}                   # Mar, Apr, Agu, Sep
KELAS_P = {
    "jatuh_miskin_sakit": [0.10, 0.30, 0.60],
    "kronis_bolong_sekali": [0.25, 0.35, 0.40],
    "pembayar_musiman": [0.05, 0.20, 0.75],
    "baru_sakit_tetap_bayar": [0.20, 0.35, 0.45],
    "baru_berhenti_cepat": [0.20, 0.30, 0.50],
}
P_PENGAKAL = 0.45                # porsi reaktivasi_saat_butuh yang mengakali batas 45 hari
# KASUS JUJUR: bulan daftar jenis yang ditahan (indeks bulan sejak Jan 2021, ujung kanan tidak ikut)
HOLDOUT_BULAN = (52, 55)         # daftar Mei-Jul 2025 -> berhenti bayar Agu-Okt 2025

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
    # KASUS JUJUR
    if seg in ("kronis_bolong_sekali", "baru_sakit_tetap_bayar"):
        return 0.995 if autodebet else 0.975            # seperti patuh
    if seg == "jatuh_miskin_sakit":
        if d >= shock:
            return 0.05                                  # penghasilan hilang
        return 0.995 if autodebet else 0.975
    if seg == "pembayar_musiman":
        return 0.95 if (month_of(d) % 12 + 1) in BULAN_PANEN else 0.15
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
    # KASUS JUJUR
    base = {"kronis_bolong_sekali": 0.97, "baru_sakit_tetap_bayar": 0.97,
            "pembayar_musiman": 0.90, "baru_berhenti_cepat": 0.98}.get(seg)
    if seg == "jatuh_miskin_sakit":
        if d < shock:
            base = 0.97
        elif d - shock <= 90:
            base = 0.85              # masih berusaha melunasi demi berobat
        else:
            base = 0.20
    if jenis == "rjtl_biasa":    # jarang ada yang melunasi tunggakan demi kunjungan ringan
        base *= 0.10 if seg in RSB_SEG else 0.35
    return base


def simulasi(n, seed, n_lain=0):
    # KASUS JUJUR: wilayah sama dengan data dasar, orang memakai RNG [seed, 3]
    n_w = 40
    pov = np.round(np.random.default_rng(seed).beta(2, 7, n_w), 3)
    rng = np.random.default_rng([seed, 3])
    kode_w = [f"W{k:02d}" for k in range(1, n_w + 1)]
    wilayah = pd.DataFrame({"kode_wilayah": kode_w, "indeks_kemiskinan": pov})
    w_poor = pov / pov.sum()
    w_other = 0.7 / n_w + 0.3 * (1 - pov) / (1 - pov).sum()

    peserta, bayar_rows, status_rows, klaim_rows, dtsen_rows, label_rows = [], [], [], [], [], []
    cnt = {"bayar": 0, "klaim": 0, "episode": 0}

    seg_idx = np.resize(np.arange(len(SEGMEN)), n)   # KASUS JUJUR: n / 5 per jenis
    rng.shuffle(seg_idx)

    for k in range(n):
        pid = f"J-{k + 1:06d}"
        seg = SEGMEN[seg_idx[k]]
        rsb = seg in RSB_SEG
        kelas = int(rng.choice([1, 2, 3], p=KELAS_P[seg]))
        iuran = IURAN[kelas]
        usia = int(np.clip(rng.normal(48 if rsb else 42, 13 if rsb else 14), 18, 85))
        jk = "L" if rng.random() < 0.5 else "P"
        wil = kode_w[rng.choice(n_w, p=w_poor if seg == "tidak_mampu" else w_other)]
        baru = seg in ("baru_sakit_tetap_bayar", "baru_berhenti_cepat")   # KASUS JUJUR
        pengakal = rsb and rng.random() < P_PENGAKAL
        f_usia = float(np.clip(0.6 + (usia - 18) / 40, 0.6, 2.2))

        # KASUS JUJUR: jatuh miskin = satu sakit berat yang sudah ditentukan
        sakit_berat = None
        if seg == "jatuh_miskin_sakit":
            sakit_berat = (int(rng.integers(WIN_START + 60, WIN_END - 150)),
                           "ritl_darurat" if rng.random() < 0.5 else "ritl_elektif")
        bulan_bolong = None
        if seg == "kronis_bolong_sekali":
            bulan_bolong = int(rng.integers(WIN_I0 + 3, N_MONTH - 3))

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
        kena_denda = set()                   # reaktivasi yang dendanya sudah dipakai
        hari_bayar = []
        heap = []
        hold = [-INF]                        # reaktivasi_saat_butuh tetap bayar sampai hari ini

        # ---- kepesertaan awal ----
        if not baru:
            i0, act_start = 0, -INF
            tgl_daftar = (date(2016, 1, 1) - BASE).days + int(rng.integers(0, 365 * 5))
            autodebet = rng.random() < (0.20 if seg == "tidak_mampu" else 0.35)
            if seg == "pembayar_musiman":
                autodebet = False                        # KASUS JUJUR
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
            if seg == "baru_berhenti_cepat":  # KASUS JUJUR: daftar cukup akhir, lihat HOLDOUT_*
                onset0 = int(rng.integers(MS[HOLDOUT_BULAN[0]], MS[HOLDOUT_BULAN[1]]))
                tgl_daftar = onset0 - int(rng.integers(0, 8))
            elif rsb or seg == "baru_sakit_tetap_bayar":   # daftar karena sudah butuh layanan
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
            if seg == "kronis_bolong_sekali" and jenis == "rjtl_seri":
                rate *= 25                           # KASUS JUJUR: berobat seri rutin
            for _ in range(rng.poisson(rate * tahun)):
                heapq.heappush(heap, (int(rng.integers(t_from, WIN_END + 1)), 2, "onset", jenis))
        if onset0 is not None:
            jenis0 = "ritl_elektif" if rng.random() < 0.65 else "rjtl_seri"
            if seg == "baru_berhenti_cepat":
                jenis0 = "ritl_elektif"         # KASUS JUJUR: satu rawat inap, lalu berhenti
            jadwalkan(act_start, jenis0)
        if sakit_berat is not None:                  # KASUS JUJUR
            heapq.heappush(heap, (sakit_berat[0], 2, "sakit_berat", sakit_berat[1]))

        while heap:
            d, _, typ, payload = heapq.heappop(heap)
            if d > WIN_END:
                continue
            if typ == "bayar":
                i = payload
                if settled[i] != INF:
                    continue
                if i == bulan_bolong:                # KASUS JUJUR: bolong tepat sekali
                    continue
                p = 1.0 if d <= hold[0] else p_bayar(seg, autodebet, d, shock)
                if rng.random() < p:
                    ada_tunggakan = any(settled[j] == INF for j in range(i0, i))
                    kanal = "autodebet" if (autodebet and not ada_tunggakan) else kanal_lunas()
                    bayar(d, i, kanal)
            elif typ == "sakit_berat":             # KASUS JUJUR: jatuh miskin karena sakit
                jenis = payload
                shock = d                           # penghasilan hilang mulai hari ini
                if not aktif(d):
                    if rng.random() >= p_reaktivasi(seg, d, shock, jenis):
                        continue
                    bayar(d, month_of(d), kanal_lunas())
                jadwalkan(d, jenis)
                # perawatan lanjutan (rehabilitasi/kemoterapi) 2-6 minggu kemudian
                jadwalkan(d + int(rng.integers(14, 43)), "rjtl_seri")
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
            if seg in ("tidak_mampu", "jatuh_miskin_sakit"):
                p15 = 0.85 if shock <= SNAPSHOT_DTSEN else 0.20
            else:                                       # KASUS JUJUR
                p15 = {"kronis_bolong_sekali": 0.08, "pembayar_musiman": 0.30,
                       "baru_sakit_tetap_bayar": 0.08, "baru_berhenti_cepat": 0.15}[seg]
            dtsen_rows.append((pid, "1-5" if rng.random() < p15 else "6-10", SNAPSHOT_DTSEN))

        peserta.append((pid, tgl_daftar, kelas, iuran, usia, jk, wil, bool(autodebet)))
        label_rows.append((pid, seg, bool(pengakal), bool(baru),
                           None if shock == INF else int(shock)))

    # ---- segmen di luar cakupan: PPU, PBI, PBPU/BP yang dibayar Pemda ----
    # RNG terpisah supaya data PBPU/BP mandiri di atas tidak berubah.
    seg_kepesertaan = list(np.where(np.random.default_rng([seed, 1]).random(n) < 0.85, "PBPU", "BP"))
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
        for jenis, cfg in JENIS.items():
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
                    biaya = int(round(cfg["biaya"] * TARIF_KELAS[kelas]
                                      * rng_l.lognormal(-cfg["sd"] ** 2 / 2, cfg["sd"]), -3))
                    los = 1 + int(rng_l.poisson(3 if jenis == "ritl_darurat" else 2)) \
                        if cfg["layanan"] == "RITL" else 0
                    kunjungan.append((h, jenis, kelompok, eps, biaya, los))
        denda_dipakai = False
        for h, jenis, kelompok, eps, biaya, los in sorted(kunjungan):
            if h > WIN_END or (tunggak and tunggak[0] <= h < tunggak[1]):
                continue                 # di luar jendela, atau sedang dihentikan sementara
            cfg = JENIS[jenis]
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
    a = ap.parse_args()
    n_lain = round(0.15 * a.n) if a.n_lain is None else a.n_lain

    tabel = simulasi(a.n, a.seed, n_lain)
    os.makedirs(a.out, exist_ok=True)
    for nama, df in tabel.items():
        df.to_csv(os.path.join(a.out, f"{nama}.csv"), index=False)
        print(f"{nama:20s} {len(df):>9,d} baris")


if __name__ == "__main__":
    main()
