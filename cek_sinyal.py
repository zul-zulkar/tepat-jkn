#!/usr/bin/env python3
"""
cek_sinyal.py - TEPAT: uji sinyal pada data sintetis. Deteksi tidak memakai label.
Skrip baru membuka label di langkah terakhir, untuk mengukur hasil.

Langkah:
  1. Uji bunching rawat inap terjadwal di sekitar hari ke-45 setelah reaktivasi
     (kontrafaktual polinomial + bootstrap), plus estimasi denda yang terhindar.
  2. Fitur perilaku per peserta: rasio hari aktif, jumlah reaktivasi, kaitan
     reaktivasi dengan klaim besar, rasio klaim/iuran, tunggakan akhir, dan pola
     "rutin lalu berhenti" (indikasi guncangan ekonomi).
  3. Triase berbasis aturan: rute intervensi dan alasan per peserta.
  4. Validasi triase terhadap label.

Pemakaian:
    python cek_sinyal.py --data data --out hasil
"""
import argparse
import os
import warnings

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AKHIR = pd.Timestamp("2025-12-31")
BATAS = 45                     # hari, batas denda pelayanan
JENDELA_KURANG = (31, 45)      # hari-hari yang kehilangan kasus
JENDELA_LEBIH = (46, 60)       # hari-hari yang kelebihan kasus
MAKS_HARI = 120
DERAJAT = 4
KLAIM_BESAR = 1_000_000        # RITL apa pun, atau RJTL >= Rp1 juta
JEDA_KAIT = 90                 # reaktivasi "terkait" bila klaim besar <= 90 hari sesudahnya

# warna grafik
WARNA_AKTUAL, WARNA_CF = "#2a78d6", "#eb6834"
PERMUKAAN, TINTA, TINTA_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def muat(folder):
    baca = lambda n, **kw: pd.read_csv(os.path.join(folder, f"{n}.csv"), **kw)  # noqa: E731
    return dict(
        peserta=baca("peserta"),
        bayar=baca("pembayaran", parse_dates=["tgl_bayar"]),
        status=baca("riwayat_status", parse_dates=["tgl_mulai", "tgl_selesai"]),
        klaim=baca("klaim", parse_dates=["tgl_masuk", "tgl_keluar"]),
        dtsen=baca("dtsen_flag"),
        label=baca("label_ground_truth"),
    )


def tabel_reaktivasi(status, bayar):
    st = status.sort_values(["id_peserta", "tgl_mulai"]).copy()
    st["sebelum"] = st.groupby("id_peserta")["status"].shift()
    re = st[(st["status"] == "aktif") & (st["sebelum"] == "nonaktif")][["id_peserta", "tgl_mulai"]]
    re = re.rename(columns={"tgl_mulai": "tgl_reakt"})
    bulan = (bayar.groupby(["id_peserta", "tgl_bayar"])["jumlah_bulan_dibayar"].max()
             .reset_index().rename(columns={"tgl_bayar": "tgl_reakt"}))
    re = re.merge(bulan, on=["id_peserta", "tgl_reakt"], how="left")
    re["bulan_tertunggak"] = (re["jumlah_bulan_dibayar"] - 1).clip(lower=1)
    return re.drop(columns="jumlah_bulan_dibayar").sort_values("tgl_reakt").reset_index(drop=True)


# ---------------------------------------------------------------- bunching
def _cf(hitung):
    x = np.arange(MAKS_HARI + 1)
    # hari 0 (lunas tunggakan di hari masuk RS) punya pola sendiri, jadi kami keluarkan dari fit
    luar = ((x >= 1) & (x < JENDELA_KURANG[0])) | (x > JENDELA_LEBIH[1])
    koef = np.polyfit(x[luar], hitung[luar], DERAJAT)
    return np.clip(np.polyval(koef, x), 0, None)


def _ukur(hari):
    hitung = np.bincount(hari, minlength=MAKS_HARI + 1)[: MAKS_HARI + 1].astype(float)
    cf = _cf(hitung)
    lo, hi = JENDELA_LEBIH
    a, b = JENDELA_KURANG
    lebih = (hitung[lo:hi + 1] - cf[lo:hi + 1]).sum()
    kurang = (cf[a:b + 1] - hitung[a:b + 1]).sum()
    return hitung, cf, lebih, kurang


def analisis_bunching(klaim, re, rng, n_boot=300):
    el = klaim[(klaim["jenis_layanan"] == "RITL") & (klaim["cara_masuk"] == "terjadwal")]
    el = el.sort_values("tgl_masuk")
    m = pd.merge_asof(el, re, left_on="tgl_masuk", right_on="tgl_reakt", by="id_peserta",
                      direction="backward")
    m["hari"] = (m["tgl_masuk"] - m["tgl_reakt"]).dt.days
    m = m[m["hari"].between(0, MAKS_HARI)].copy()
    hari = m["hari"].to_numpy(dtype=int)
    hitung, cf, lebih, kurang = _ukur(hari)
    boot = np.array([_ukur(rng.choice(hari, size=len(hari)))[2] for _ in range(n_boot)])
    ci = np.percentile(boot, [2.5, 97.5])

    # estimasi denda terhindar: porsi kasus berlebih x denda hipotetis kasus di hari 46-60
    lo, hi = JENDELA_LEBIH
    di_jendela = m[m["hari"].between(lo, hi)].copy()
    di_jendela["denda_hipotetis"] = np.minimum(
        0.05 * di_jendela["biaya_klaim"] * di_jendela["bulan_tertunggak"].clip(upper=12), 30_000_000)
    porsi = max(lebih, 0) / max(len(di_jendela), 1)
    denda_terhindar = porsi * di_jendela["denda_hipotetis"].sum()
    return dict(m=m, hitung=hitung, cf=cf, lebih=lebih, kurang=kurang, ci=ci,
                n=len(hari), hari0=int((hari == 0).sum()), denda_terhindar=denda_terhindar)


def plot_bunching(h, path):
    x = np.arange(1, MAKS_HARI + 1)
    hit, cf = h["hitung"][1:], h["cf"][1:]
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=160)
    fig.patch.set_facecolor(PERMUKAAN)
    ax.set_facecolor(PERMUKAAN)
    ax.bar(x, hit, width=0.8, color=WARNA_AKTUAL, label="Rawat inap terjadwal (aktual)",
           zorder=2)
    ax.plot(x, cf, color=WARNA_CF, lw=2, label="Kontrafaktual (polinomial, tanpa hari 31-60)",
            zorder=3)
    ax.axvline(BATAS + 0.5, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1)
    ymax = max(hit.max(), cf.max())
    ax.text(BATAS - 0.5, ymax * 0.97, "batas denda: hari ke-45 ", color=TINTA_2, fontsize=9,
            va="top", ha="right")
    ax.set_xlim(0, MAKS_HARI + 1)
    ax.set_xlabel("Hari sejak reaktivasi kepesertaan sampai masuk rawat inap terjadwal",
                  color=TINTA_2, fontsize=10)
    ax.set_ylabel("Jumlah kasus per hari", color=TINTA_2, fontsize=10)
    ax.tick_params(colors=TINTA_2, labelsize=9)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    lo, hi = h["ci"]
    fig.text(0.012, 0.965, "Lonjakan rawat inap terjadwal tepat setelah batas denda 45 hari",
             ha="left", va="top", fontsize=13, fontweight="bold", color=TINTA)
    fig.text(0.012, 0.915, f"Data sintetis, hari 1-{MAKS_HARI}, n = {h['n'] - h['hari0']:,} kasus. "
             f"Massa berlebih hari 46-60: {h['lebih']:.0f} kasus (IK95% bootstrap {lo:.0f}-{hi:.0f}).",
             ha="left", va="top", fontsize=9.5, color=TINTA_2)
    leg = ax.legend(frameon=False, fontsize=9, loc="upper right")
    for t in leg.get_texts():
        t.set_color(TINTA)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(path, facecolor=PERMUKAAN)
    plt.close(fig)


# ---------------------------------------------------------------- fitur & triase

BULAN = pd.date_range("2023-01-01", "2025-12-01", freq="MS")


def matriks_aktif(st, ids):
    """1 = aktif, 0 = nonaktif, NaN = belum terdaftar / masa tunggu; per bulan (tanggal 15)."""
    idx = {pid: i for i, pid in enumerate(ids)}
    M = np.full((len(ids), len(BULAN)), np.nan)
    t15 = (BULAN + pd.Timedelta(days=14)).to_numpy()
    for pid, a, b, s in st[["id_peserta", "tgl_mulai", "tgl_selesai", "status"]].itertuples(index=False):
        if s == "masa_tunggu":
            continue
        lo = np.searchsorted(t15, np.datetime64(a), "left")
        hi = np.searchsorted(t15, np.datetime64(b), "right")
        M[idx[pid], lo:hi] = 1.0 if s == "aktif" else 0.0
    return M


def titik_patah(M, min_sebelum=9, min_sesudah=4):
    """skor = max_t [rata2 aktif 12 bln sebelum t] - [rata2 aktif sesudah t], dgn syarat panjang."""
    n, T = M.shape
    skor = np.full(n, -np.inf)
    best = np.full(n, np.nan)
    for t in range(min_sebelum, T - min_sesudah + 1):
        seb = M[:, max(0, t - 12):t]
        ses = M[:, t:]
        cukup = (np.sum(~np.isnan(seb), axis=1) >= min_sebelum) & (np.sum(~np.isnan(ses), axis=1) >= min_sesudah)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            s_t = np.nanmean(seb, axis=1) - np.nanmean(ses, axis=1)
            s_t = np.where(cukup & (np.nanmean(ses, axis=1) <= 0.25), s_t, -np.inf)
        upd = s_t > skor
        skor[upd], best[upd] = s_t[upd], t
    skor[~np.isfinite(skor)] = 0.0
    return skor, best

def fitur_peserta(D, re):
    p = D["peserta"][["id_peserta", "iuran_bulanan", "kelas"]].copy()
    st = D["status"].copy()
    st["durasi"] = (st["tgl_selesai"] - st["tgl_mulai"]).dt.days + 1
    obs = st[st["status"] != "masa_tunggu"]
    aktif = obs[obs["status"] == "aktif"].groupby("id_peserta")["durasi"].sum()
    total = obs.groupby("id_peserta")["durasi"].sum()
    p["rasio_hari_aktif"] = p["id_peserta"].map(aktif / total).fillna(0).round(3)

    # reaktivasi & keterkaitannya dengan klaim besar
    k = D["klaim"]
    besar = k[(k["jenis_layanan"] == "RITL") | (k["biaya_klaim"] >= KLAIM_BESAR)]
    besar = besar[["id_peserta", "tgl_masuk"]].sort_values("tgl_masuk")
    r = pd.merge_asof(re.sort_values("tgl_reakt"), besar, left_on="tgl_reakt",
                      right_on="tgl_masuk", by="id_peserta", direction="forward")
    r["terkait"] = (r["tgl_masuk"] - r["tgl_reakt"]).dt.days.le(JEDA_KAIT)
    g = r.groupby("id_peserta")
    p["n_reaktivasi"] = p["id_peserta"].map(g.size()).fillna(0).astype(int)
    p["n_reakt_terkait_klaim"] = p["id_peserta"].map(g["terkait"].sum()).fillna(0).astype(int)
    p["porsi_reakt_terkait"] = (p["n_reakt_terkait_klaim"] / p["n_reaktivasi"].replace(0, np.nan)
                                ).fillna(0).round(2)

    # rasio klaim / iuran dalam jendela
    klaim_rp = k.groupby("id_peserta")["biaya_klaim"].sum()
    iuran_rp = D["bayar"].groupby("id_peserta")["nominal"].sum()
    p["klaim_rp"] = p["id_peserta"].map(klaim_rp).fillna(0)
    p["iuran_rp"] = p["id_peserta"].map(iuran_rp).fillna(0)
    p["rasio_klaim_iuran"] = (p["klaim_rp"] / p["iuran_rp"].replace(0, np.nan)).round(2)

    # tunggakan akhir (bulan) dari status terakhir
    last = st.sort_values("tgl_mulai").groupby("id_peserta").tail(1).set_index("id_peserta")
    mulai = last["tgl_mulai"]
    bulan_unpaid = ((AKHIR.year - mulai.dt.year) * 12 + (AKHIR.month - mulai.dt.month) + 2)
    tung = np.where(last["status"] == "nonaktif", bulan_unpaid.clip(upper=24), 0)
    p["tunggakan_bulan"] = p["id_peserta"].map(pd.Series(tung, index=last.index)).astype(int)
    p["tunggakan_rp"] = p["tunggakan_bulan"] * p["iuran_bulanan"]

    # pola guncangan: rutin aktif >= 9 bulan, lalu nyaris tidak aktif >= 4 bulan sampai akhir.
    # Deteksi titik patah sederhana pada matriks status bulanan (aktif pada tanggal 15).
    M = matriks_aktif(st, p["id_peserta"])
    skor, bulan_patah = titik_patah(M)
    p["skor_patah"] = np.round(skor, 2)
    p["bulan_berhenti"] = [str(BULAN[int(b)])[:7] if (sk >= 0.6 and not np.isnan(b)) else None
                           for sk, b in zip(skor, bulan_patah)]
    p["pola_rutin_lalu_berhenti"] = skor >= 0.6

    # pendaftar baru yang langsung memakai layanan besar lalu berhenti bayar
    dft = D["peserta"].set_index("id_peserta")["tgl_daftar"]
    aktif_pertama = st[st["status"] == "aktif"].groupby("id_peserta")["tgl_mulai"].min()
    klaim_besar_pertama = besar.groupby("id_peserta")["tgl_masuk"].min()
    selisih = (p["id_peserta"].map(klaim_besar_pertama) - p["id_peserta"].map(aktif_pertama)).dt.days
    p["baru_klaim_lalu_berhenti"] = (
        pd.to_datetime(p["id_peserta"].map(dft)).ge(pd.Timestamp("2023-01-01"))
        & selisih.between(0, JEDA_KAIT) & p["tunggakan_bulan"].ge(6))

    p = p.merge(D["dtsen"][["id_peserta", "rentang_desil"]], on="id_peserta", how="left")
    p["rentang_desil"] = p["rentang_desil"].fillna("tidak_padan")
    return p


def triase(p):
    rsb = (((p["n_reakt_terkait_klaim"] >= 1) & (p["porsi_reakt_terkait"] >= 0.5)
            & (p["rasio_hari_aktif"] < 0.5))
           | p["baru_klaim_lalu_berhenti"])
    # peserta DTSEN 1-5 tidak boleh masuk rute verifikasi
    rsb = rsb & (p["rentang_desil"] != "1-5")
    miskin = (p["rentang_desil"] == "1-5") | p["pola_rutin_lalu_berhenti"]
    pbi = (p["tunggakan_bulan"] >= 3) & miskin & ~rsb
    lalai = (p["n_reaktivasi"] >= 3) & ~rsb & ~pbi
    diam = (p["tunggakan_bulan"] >= 12) & (p["n_reaktivasi"] == 0) & ~pbi
    rute = np.select(
        [rsb, pbi, lalai, diam],
        ["verifikasi_pola_reaktivasi", "rujuk_cek_kelayakan_PBI", "pengingat_autodebet_REHAB",
         "nonaktif_lama_tanpa_sinyal"],
        default="tanpa_tindakan")
    p = p.copy()
    p["rute"] = rute
    p["jeda_dtsen"] = pbi & p["pola_rutin_lalu_berhenti"] & (p["rentang_desil"] != "1-5")

    def alasan(r):
        if r.rute == "verifikasi_pola_reaktivasi" and r.baru_klaim_lalu_berhenti and r.n_reaktivasi == 0:
            return (f"pendaftar baru: klaim besar <= {JEDA_KAIT} hari sejak aktif, lalu menunggak "
                    f"{r.tunggakan_bulan} bln; klaim/iuran {r.rasio_klaim_iuran}x")
        if r.rute == "verifikasi_pola_reaktivasi":
            return (f"{r.n_reakt_terkait_klaim} dari {r.n_reaktivasi} reaktivasi diikuti klaim besar "
                    f"<= {JEDA_KAIT} hari; aktif {r.rasio_hari_aktif:.0%} waktu; "
                    f"klaim/iuran {r.rasio_klaim_iuran}x")
        if r.rute == "rujuk_cek_kelayakan_PBI":
            dasar = "DTSEN desil 1-5" if r.rentang_desil == "1-5" else \
                f"rutin lalu berhenti sejak {r.bulan_berhenti} (DTSEN belum mencerminkan)"
            return f"menunggak {r.tunggakan_bulan} bln; {dasar}"
        if r.rute == "pengingat_autodebet_REHAB":
            return (f"{r.n_reaktivasi} kali nonaktif lalu melunasi; "
                    f"hanya {r.n_reakt_terkait_klaim} terkait klaim")
        if r.rute == "nonaktif_lama_tanpa_sinyal":
            return f"menunggak {r.tunggakan_bulan} bln tanpa reaktivasi; perlu verifikasi kemampuan"
        return ""

    p["alasan"] = p.apply(alasan, axis=1)
    return p


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="hasil")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    D = muat(a.data)
    re = tabel_reaktivasi(D["status"], D["bayar"])
    out = []
    say = out.append

    h = analisis_bunching(D["klaim"], re, rng)
    plot_bunching(h, os.path.join(a.out, "bunching_hari45.png"))
    say("== 1. BUNCHING DI BATAS DENDA 45 HARI ==")
    say(f"kasus rawat inap terjadwal 0-{MAKS_HARI} hari setelah reaktivasi : {h['n']:,}")
    say(f"lunas tunggakan di hari masuk RS (hari 0) : {h['hari0']:,} kasus (sinyal terpisah)")
    say(f"massa berlebih hari 46-60 : {h['lebih']:.0f} kasus "
        f"(IK95% bootstrap {h['ci'][0]:.0f}-{h['ci'][1]:.0f})")
    say("catatan: kasus yang ditunda bisa berasal dari hari 0-45 mana pun. Untuk data nyata,")
    say("         pakai estimator dengan batasan integrasi (Chetty dkk. 2011).")
    say(f"estimasi denda terhindar  : Rp{h['denda_terhindar'] / 1e6:,.0f} juta")

    p = triase(fitur_peserta(D, re))
    cols = ["id_peserta", "rute", "alasan", "jeda_dtsen", "rentang_desil", "bulan_berhenti",
            "baru_klaim_lalu_berhenti", "n_reaktivasi",
            "n_reakt_terkait_klaim", "rasio_hari_aktif", "rasio_klaim_iuran", "tunggakan_bulan",
            "tunggakan_rp"]
    p[cols].sort_values(["rute", "tunggakan_rp"], ascending=[True, False]).to_csv(
        os.path.join(a.out, "triase_peserta.csv"), index=False)

    say("\n== 2. RUTE TRIASE (tanpa label) ==")
    ring = p.groupby("rute").agg(peserta=("id_peserta", "size"),
                                 tunggakan_rp_miliar=("tunggakan_rp", lambda s: s.sum() / 1e9),
                                 klaim_rp_miliar=("klaim_rp", lambda s: s.sum() / 1e9),
                                 iuran_rp_miliar=("iuran_rp", lambda s: s.sum() / 1e9))
    say(ring.round(2).to_string())
    say(f"\npeserta rute PBI yang tertangkap lewat pola meski DTSEN belum 1-5 "
        f"(jeda pembaruan): {int(p['jeda_dtsen'].sum())}")

    say("\n== 3. VALIDASI TERHADAP LABEL (hanya untuk mengukur) ==")
    v = p.merge(D["label"], on="id_peserta")
    say(pd.crosstab(v["rute"], v["segmen"], margins=True).to_string())
    pasangan = {"verifikasi_pola_reaktivasi": "reaktivasi_saat_butuh",
                "rujuk_cek_kelayakan_PBI": "tidak_mampu",
                "pengingat_autodebet_REHAB": "lalai"}
    say("")
    for rute, seg in pasangan.items():
        tp = ((v["rute"] == rute) & (v["segmen"] == seg)).sum()
        prec = tp / max((v["rute"] == rute).sum(), 1)
        rec = tp / max((v["segmen"] == seg).sum(), 1)
        say(f"{rute:28s} presisi {prec:6.1%}  recall {rec:6.1%}  (target segmen: {seg})")
    salah_tuduh = ((v["rute"] == "verifikasi_pola_reaktivasi")
                   & v["segmen"].isin(["patuh", "tidak_mampu"])).sum()
    say(f"peserta patuh/tidak_mampu yang masuk rute verifikasi pola reaktivasi: {salah_tuduh}")

    teks = "\n".join(out)
    print(teks)
    with open(os.path.join(a.out, "ringkasan.txt"), "w", encoding="utf-8") as f:
        f.write(teks + "\n")


if __name__ == "__main__":
    main()
