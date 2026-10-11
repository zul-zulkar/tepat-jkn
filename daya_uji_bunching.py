#!/usr/bin/env python3
"""
daya_uji_bunching.py - TEPAT: berapa kasus penundaan yang dibutuhkan agar uji bunching
di hari ke-45 mendeteksinya?

Cara kerja (simulasi Monte Carlo, tanpa label):
  1. Bentuk distribusi "tanpa penundaan" = kurva kontrafaktual dari analisis bunching
     rawat inap terjadwal (cek_sinyal.py) pada data yang diberikan, hari 1-120.
  2. Untuk tiap jumlah kasus N (rawat inap terjadwal 1-120 hari setelah reaktivasi):
     - H0: tarik N kasus dari distribusi itu, hitung lompatan (kelebihan hari 46-60 +
       kekurangan hari 31-45). Ambang = persentil 97,5 dari lompatan di bawah H0,
       setara dengan syarat "IK95% lompatan di atas 0" di cek_sinyal.py.
     - H1: pindahkan X kasus yang jatuh di hari 1-45 ke hari 46 + Exp(4), sama seperti
       pengakal di generate_data.py. Daya = porsi simulasi dengan lompatan di atas ambang.
  3. Efek minimum terdeteksi (MDE) = X terkecil dengan daya >= 80%.
  Pola kedua, 46 + Exp(15), menguji penundaan yang lebih menyebar (skenario S6).

Batasan: distribusi H0 diambil dari kurva polinomial yang mulus. Bentuk nyata bisa
bergelombang (lihat plasebo IGD), sehingga ambang sebenarnya bisa lebih tinggi. Hasil ini
batas bawah kebutuhan sampel, bukan janji performa.

Pemakaian:
    python daya_uji_bunching.py --data data --out hasil          # +-1 menit
"""
import argparse
import os

import matplotlib
import numpy as np
import pandas as pd

import cek_sinyal as cs

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

N_GRID = [250, 500, 1000, 2500, 5000, 10000, 20000]
PORSI = [0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.10, 0.15, 0.20]
POLA = {"bawaan_46+Exp(4)": 4.0, "menyebar_46+Exp(15)": 15.0}
DAYA_TARGET = 0.80
ALFA = 0.025                       # satu sisi, setara IK95% dua sisi di atas 0
N_KURVA = [500, 1000, 2500, 5000, 10000]
WARNA_KURVA = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]   # biru, terang -> gelap


def lompat(hitung):
    """Kelebihan hari 46-60 + kekurangan hari 31-45 terhadap kontrafaktual (sama dengan cek_sinyal)."""
    cf = cs._cf(hitung)
    lo, hi = cs.JENDELA_LEBIH
    a, b = cs.JENDELA_KURANG
    return (hitung[lo:hi + 1] - cf[lo:hi + 1]).sum() + (cf[a:b + 1] - hitung[a:b + 1]).sum()


def tarik(rng, p0, n):
    """Hitungan per hari 0..120 dari N kasus di hari 1..120."""
    h = np.zeros(cs.MAKS_HARI + 1)
    h[1:] = rng.multinomial(n, p0)
    return h


def geser(rng, h, x, skala):
    """Pindahkan x kasus dari hari 1-45 ke hari 46 + floor(Exp(skala))."""
    h = h.copy()
    sumber = h[1:cs.BATAS + 1].astype(np.int64)
    x = int(min(x, sumber.sum()))
    if x == 0:
        return h
    ambil = rng.multivariate_hypergeometric(sumber, x)
    h[1:cs.BATAS + 1] -= ambil
    tujuan = np.minimum(cs.BATAS + 1 + np.floor(rng.exponential(skala, x)).astype(int), cs.MAKS_HARI)
    np.add.at(h, tujuan, 1)
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="hasil")
    ap.add_argument("--sim_h0", type=int, default=2000)
    ap.add_argument("--sim_h1", type=int, default=500)
    ap.add_argument("--seed", type=int, default=45)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    D, _ = cs.saring_cakupan(cs.muat(a.data))
    re = cs.tabel_reaktivasi(D["status"], D["bayar"])
    h = cs.analisis_bunching(D["klaim"], re, np.random.default_rng(7))
    p0 = np.clip(h["cf"][1:], 1e-9, None)
    p0 = p0 / p0.sum()
    n_data = h["n"] - h["hari0"]

    grid_n = sorted(set(N_GRID + [n_data]))
    baris, ambang = [], {}
    for n in grid_n:
        nol = np.array([lompat(tarik(rng, p0, n)) for _ in range(a.sim_h0)])
        ambang[n] = np.quantile(nol, 1 - ALFA)
        for pola, skala in POLA.items():
            for porsi in PORSI:
                x = int(round(porsi * n))
                st = np.array([lompat(geser(rng, tarik(rng, p0, n), x, skala))
                               for _ in range(a.sim_h1)])
                baris.append(dict(n_kasus=n, pola=pola, porsi_ditunda=porsi, x_ditunda=x,
                                  ambang_lompatan=ambang[n], daya=(st > ambang[n]).mean(),
                                  lompatan_rata=st.mean()))
    hasil = pd.DataFrame(baris)
    hasil.round(4).to_csv(os.path.join(a.out, "daya_uji_bunching.csv"), index=False)

    # efek minimum terdeteksi: interpolasi linear porsi pada daya 80%
    mde = []
    for (n, pola), g in hasil.groupby(["n_kasus", "pola"]):
        g = g.sort_values("porsi_ditunda")
        lewat = g[g["daya"] >= DAYA_TARGET]
        if lewat.empty:
            porsi = np.nan
        else:
            i = g.index.get_loc(lewat.index[0])
            if i == 0:
                porsi = g["porsi_ditunda"].iloc[0]
            else:
                p1, p2 = g["porsi_ditunda"].iloc[i - 1], g["porsi_ditunda"].iloc[i]
                d1, d2 = g["daya"].iloc[i - 1], g["daya"].iloc[i]
                porsi = p1 + (DAYA_TARGET - d1) * (p2 - p1) / (d2 - d1)
        mde.append(dict(n_kasus=n, pola=pola, ambang_lompatan=ambang[n], mde_porsi=porsi,
                        mde_kasus=porsi * n if porsi == porsi else np.nan))
    mde = pd.DataFrame(mde)
    mde.round(4).to_csv(os.path.join(a.out, "daya_uji_mde.csv"), index=False)

    out = ["== DAYA UJI BUNCHING (simulasi; distribusi H0 = kontrafaktual data ini) ==",
           f"kasus rawat inap terjadwal 1-120 hari setelah reaktivasi di data ini: {n_data:,}",
           f"uji: lompatan > persentil {100 * (1 - ALFA):.1f} H0 ({a.sim_h0} simulasi); "
           f"daya dari {a.sim_h1} simulasi; target daya {DAYA_TARGET:.0%}", ""]
    t = mde.pivot(index="n_kasus", columns="pola", values=["mde_kasus", "mde_porsi"])
    tampil = pd.DataFrame({
        "ambang_lompatan": mde.groupby("n_kasus")["ambang_lompatan"].first().round(0),
        "MDE_kasus_bawaan": t[("mde_kasus", "bawaan_46+Exp(4)")].round(0),
        "MDE_%_bawaan": (100 * t[("mde_porsi", "bawaan_46+Exp(4)")]).round(1),
        "MDE_kasus_menyebar": t[("mde_kasus", "menyebar_46+Exp(15)")].round(0),
        "MDE_%_menyebar": (100 * t[("mde_porsi", "menyebar_46+Exp(15)")]).round(1),
    })
    out.append(tampil.to_string())
    out.append("\nMDE = kasus yang ditunda (dipindah dari hari 1-45 ke sesudah hari 45) agar terdeteksi "
               "dengan daya 80%.")
    out.append("% = terhadap seluruh rawat inap terjadwal 1-120 hari setelah reaktivasi. "
               "NaN = tidak tercapai sampai 20%.")
    teks = "\n".join(out)
    print(teks)
    with open(os.path.join(a.out, "daya_uji_ringkasan.txt"), "w", encoding="utf-8") as f:
        f.write(teks + "\n")

    # grafik: daya vs porsi ditunda, pola bawaan, satu garis per N (biru terang -> gelap)
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    fig.patch.set_facecolor(cs.PERMUKAAN)
    ax.set_facecolor(cs.PERMUKAAN)
    g = hasil[hasil["pola"] == "bawaan_46+Exp(4)"]
    for n, warna in zip(N_KURVA, WARNA_KURVA):
        s = g[(g["n_kasus"] == n) & (g["porsi_ditunda"] <= 0.10)].sort_values("porsi_ditunda")
        ax.plot(100 * s["porsi_ditunda"], 100 * s["daya"], color=warna, lw=2, marker="o", ms=5,
                zorder=3, label=f"{n:,}".replace(",", "."))
    ax.axhline(100 * DAYA_TARGET, color=cs.TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(9.9, 100 * DAYA_TARGET - 1.5, "daya 80%", color=cs.TINTA_2, fontsize=9, ha="right",
            va="top")
    leg = ax.legend(title="Jumlah kasus N", frameon=False, fontsize=9, title_fontsize=9,
                    loc="lower right", bbox_to_anchor=(1, 0.08))
    for t in leg.get_texts() + [leg.get_title()]:
        t.set_color(cs.TINTA)
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 102)
    pct = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%")
    ax.xaxis.set_major_formatter(pct)
    ax.yaxis.set_major_formatter(pct)
    ax.set_xlabel("Porsi rawat inap terjadwal yang ditunda sampai lewat hari ke-45",
                  color=cs.TINTA_2, fontsize=10)
    ax.set_ylabel("Peluang terdeteksi (daya uji)", color=cs.TINTA_2, fontsize=10)
    ax.tick_params(colors=cs.TINTA_2, labelsize=9)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color(cs.GRID)
    ax.grid(color=cs.GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    fig.text(0.012, 0.975, "Makin banyak kasus, makin kecil penundaan yang bisa terdeteksi",
             ha="left", va="top", fontsize=13, fontweight="bold", color=cs.TINTA)
    fig.text(0.012, 0.925, "Simulasi. N = rawat inap terjadwal 1-120 hari setelah reaktivasi. "
             "Uji: lompatan di atas persentil 97,5 tanpa penundaan. Penundaan 46 + Exp(4) hari.",
             ha="left", va="top", fontsize=9, color=cs.TINTA_2)
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    fig.savefig(os.path.join(a.out, "daya_uji_bunching.png"), facecolor=cs.PERMUKAAN)
    plt.close(fig)


if __name__ == "__main__":
    main()
