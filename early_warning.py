#!/usr/bin/env python3
"""
early_warning.py - TEPAT jalur 1: peringatan dini SEBELUM peserta menunggak.

Unit analisis: peserta-bulan. Untuk tiap peserta PBPU/BP mandiri yang berstatus AKTIF
pada tanggal 1 bulan t, model memperkirakan peluang ia berstatus NONAKTIF pada tanggal 1
salah satu dari bulan t+1, t+2, atau t+3. Artinya: ada iuran bulan t, t+1, atau t+2 yang
belum dibayar sampai akhir bulannya (Perpres 59/2024 Ps. 42 ayat 1).

Titik prediksi = tanggal 1 bulan t. Semua fitur hanya memakai data SEBELUM tanggal itu.
Skor keluar sebelum jatuh tempo iuran bulan t (tanggal 10; Perpres 82/2018 Ps. 40 ayat 1),
jadi petugas punya waktu sekitar 10 hari untuk mengingatkan sebelum tanggal jatuh tempo, dan
sampai akhir bulan sebelum status berubah.

Model: regresi logistik. Validasi waktu: latih pada titik prediksi 2023-07 s.d. 2024-09
(label sampai 2024-12), uji pada 2025-01 s.d. 2025-09 (label sampai 2025-12). Tidak ada
jendela label yang tumpang tindih antara latih dan uji.

Yang sengaja TIDAK dipakai sebagai fitur:
  - label_ground_truth: hanya dibuka di langkah evaluasi.
  - flag DTSEN: satu-satunya snapshot bertanggal 2025-01-01. Untuk titik prediksi 2023-2024
    flag itu belum ada, dan di generator flag tersebut ikut ditentukan oleh waktu guncangan
    yang terjadi kemudian (kebocoran informasi masa depan). DTSEN dipakai di lapisan aksi,
    bukan di model.
  - jenis kelamin, usia, wilayah: model tidak memakai atribut demografis.

Keluaran early warning hanya memicu intervensi yang membantu (pengingat, tawaran autodebet,
cek kelayakan PBI). Skor ini tidak pernah memasukkan peserta ke rute verifikasi.

Pemakaian:
    python early_warning.py --data data --out hasil
"""
import argparse
import os

import matplotlib
import matplotlib.ticker
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from cek_sinyal import KLAIM_BESAR, muat, saring_cakupan

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BULAN = pd.date_range("2023-01-01", "2025-12-01", freq="MS")   # titik status: tanggal 1
HORIZON = 3                     # bulan ke depan
LOOKBACK = 12                   # bulan riwayat untuk fitur
JATUH_TEMPO = 10                # tanggal jatuh tempo iuran (Perpres 82/2018 Ps. 40 ayat 1)
LATIH = ("2023-07", "2024-09")  # mulai 2023-07 supaya ada >= 6 bulan riwayat
UJI = ("2025-01", "2025-09")
K_PERSEN = [1, 5, 10, 20]       # k = kapasitas petugas, sebagai % peserta aktif per bulan

NA, AKTIF, NONAKTIF, TUNGGU = 0, 1, 2, 3

# fitur kontinu distandardisasi (rasio odds per 1 SD); fitur biner tetap 0/1
# Klaim Rp absolut dan "bulan terbanyak dibayar sekaligus" sempat diuji, lalu dibuang: keduanya
# kolinear dengan rasio klaim/iuran dan bulan telat, sehingga tanda koefisiennya terbalik dan
# tidak bisa dijelaskan ke petugas.
KONTINU = ["bulan_nonaktif_12", "n_reaktivasi_12", "bulan_telat_dibayar_12",
           "log_rasio_klaim_iuran_12", "log_masa_kepesertaan"]
BINER = ["pernah_nonaktif", "aktif_kembali_3bln", "klaim_besar_bulan_lalu",
         "klaim_besar_2_3bln", "klaim_besar_4_12bln", "autodebet", "kelas_1", "kelas_2"]
FITUR = KONTINU + BINER

LABEL_FITUR = {
    "bulan_nonaktif_12": "bulan nonaktif, 12 bln terakhir",
    "n_reaktivasi_12": "jumlah aktif kembali, 12 bln terakhir",
    "bulan_telat_dibayar_12": "bulan iuran telat yang dilunasi, 12 bln terakhir",
    "log_rasio_klaim_iuran_12": "log(1 + klaim/iuran), 12 bln terakhir",
    "log_masa_kepesertaan": "log(1 + bulan sejak daftar)",
    "pernah_nonaktif": "pernah nonaktif sejak 2023",
    "aktif_kembali_3bln": "aktif kembali dalam 3 bln terakhir",
    "klaim_besar_bulan_lalu": "klaim besar bulan lalu",
    "klaim_besar_2_3bln": "klaim besar 2-3 bln lalu",
    "klaim_besar_4_12bln": "klaim besar 4-12 bln lalu",
    "autodebet": "terdaftar autodebet",
    "kelas_1": "kelas 1 (dibanding kelas 3)",
    "kelas_2": "kelas 2 (dibanding kelas 3)",
}

WARNA_MODEL, WARNA_ATURAN = "#2a78d6", "#eb6834"
PERMUKAAN, TINTA, TINTA_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def idx_bulan(ym):
    return int(np.flatnonzero(BULAN == pd.Timestamp(ym + "-01"))[0])


# ---------------------------------------------------------------- matriks dasar
def matriks_status(st, ids):
    """Status pada tanggal 1 tiap bulan: 0 belum terdaftar, 1 aktif, 2 nonaktif, 3 masa tunggu."""
    pos = {pid: i for i, pid in enumerate(ids)}
    kode = {"aktif": AKTIF, "nonaktif": NONAKTIF, "masa_tunggu": TUNGGU}
    S = np.zeros((len(ids), len(BULAN)), dtype=np.int8)
    t = BULAN.to_numpy()
    for pid, a, b, s in st[["id_peserta", "tgl_mulai", "tgl_selesai", "status"]].itertuples(index=False):
        lo = np.searchsorted(t, np.datetime64(a), "left")
        hi = np.searchsorted(t, np.datetime64(b), "right")
        S[pos[pid], lo:hi] = kode[s]
    return S


def _nomor_bulan(tgl):
    """Indeks bulan relatif terhadap Jan 2023 (boleh negatif)."""
    tgl = pd.to_datetime(tgl)
    return ((tgl.dt.year - 2023) * 12 + tgl.dt.month - 1).to_numpy()


def _ym_ke_nomor(s):
    th = s.str.slice(0, 4).astype(int)
    bl = s.str.slice(5, 7).astype(int)
    return ((th - 2023) * 12 + bl - 1).to_numpy()


def matriks_pembayaran(bayar, ids):
    """Per peserta x bulan tanggal bayar: bulan iuran yang dibayar lewat jatuh tempo dan
    rupiah iuran."""
    pos = pd.Series(np.arange(len(ids)), index=ids)
    b = bayar[bayar["tgl_bayar"] >= BULAN[0]]
    r = pos.loc[b["id_peserta"]].to_numpy()
    mb = _nomor_bulan(b["tgl_bayar"])
    hb = b["tgl_bayar"].dt.day.to_numpy()
    awal, akhir = _ym_ke_nomor(b["periode_awal"]), _ym_ke_nomor(b["periode_akhir"])
    # bulan j terlambat bila tgl_bayar > tanggal 10 bulan j
    telat = np.clip(np.minimum(akhir, mb - 1) - awal + 1, 0, None) \
        + ((awal <= mb) & (mb <= akhir) & (hb > JATUH_TEMPO))
    T = len(BULAN)
    TL, IU = np.zeros((len(ids), T)), np.zeros((len(ids), T))
    np.add.at(TL, (r, mb), telat)
    np.add.at(IU, (r, mb), b["nominal"].to_numpy())
    return TL, IU


def matriks_klaim(klaim, ids):
    pos = pd.Series(np.arange(len(ids)), index=ids)
    r = pos.loc[klaim["id_peserta"]].to_numpy()
    mk = _nomor_bulan(klaim["tgl_masuk"])
    besar = ((klaim["jenis_layanan"] == "RITL") | (klaim["biaya_klaim"] >= KLAIM_BESAR)).to_numpy()
    T = len(BULAN)
    KB, KR = np.zeros((len(ids), T)), np.zeros((len(ids), T))
    np.add.at(KB, (r, mk), besar.astype(float))
    np.add.at(KR, (r, mk), klaim["biaya_klaim"].to_numpy())
    return KB, KR


def _jumlah(C, a, b):
    """Jumlah kolom a..b-1 dari matriks kumulatif C (kolom 0 = nol); kosong bila b <= a."""
    b = max(b, 0)
    return C[:, b] - C[:, min(max(a, 0), b)]


def _kum(M):
    return np.concatenate([np.zeros((M.shape[0], 1)), np.cumsum(M, axis=1)], axis=1)


# ---------------------------------------------------------------- panel
def bangun_panel(D):
    """Satu baris per (peserta, bulan t) dengan status aktif pada tanggal 1 bulan t."""
    ps = D["peserta"].reset_index(drop=True)
    ids = ps["id_peserta"].to_numpy()
    S = matriks_status(D["status"], ids)
    TL, IU = matriks_pembayaran(D["bayar"], ids)
    KB, KR = matriks_klaim(D["klaim"], ids)
    cTL, cIU, cKB, cKR = _kum(TL), _kum(IU), _kum(KB), _kum(KR)
    tdaftar = pd.to_datetime(ps["tgl_daftar"])
    kelas = ps["kelas"].to_numpy()
    iuran_bln = ps["iuran_bulanan"].to_numpy(dtype=float)

    bagian = []
    T = len(BULAN)
    for m in range(1, T):
        el = S[:, m] == AKTIF
        if not el.any():
            continue
        a = max(0, m - LOOKBACK)
        riw = S[:, a:m]
        teramati = np.isin(riw, (AKTIF, NONAKTIF)).sum(1)
        non = (riw == NONAKTIF).sum(1)
        trans = (S[:, a:m] == NONAKTIF) & (S[:, a + 1:m + 1] == AKTIF)   # nonaktif -> aktif
        trans3 = (S[:, max(0, m - 3):m] == NONAKTIF) & (S[:, max(1, m - 2):m + 1] == AKTIF)
        klaim_rp = _jumlah(cKR, a, m)
        iuran_rp = np.maximum(_jumlah(cIU, a, m), iuran_bln)
        if m + HORIZON < T:
            y = (S[:, m + 1:m + 1 + HORIZON] == NONAKTIF).any(1).astype(float)
        else:
            y = np.full(len(ids), np.nan)            # label belum tersedia (bulan operasional)
        bulan_daftar = ((BULAN[m] - tdaftar).dt.days / 30.44).clip(lower=0).to_numpy()
        f = pd.DataFrame({
            "id_peserta": ids,
            "bulan": BULAN[m].strftime("%Y-%m"),
            "bulan_teramati_12": teramati,
            "bulan_nonaktif_12": non,
            "n_reaktivasi_12": trans.sum(1),
            "bulan_telat_dibayar_12": _jumlah(cTL, a, m),
            "log_rasio_klaim_iuran_12": np.log1p(klaim_rp / iuran_rp),
            "log_masa_kepesertaan": np.log1p(bulan_daftar),
            "pernah_nonaktif": (S[:, :m] == NONAKTIF).any(1).astype(int),
            "aktif_kembali_3bln": trans3.any(1).astype(int),
            "klaim_besar_bulan_lalu": (KB[:, m - 1] > 0).astype(int),
            "klaim_besar_2_3bln": (_jumlah(cKB, m - 3, m - 1) > 0).astype(int),
            "klaim_besar_4_12bln": (_jumlah(cKB, m - 12, m - 3) > 0).astype(int),
            "autodebet": ps["autodebet"].astype(int).to_numpy(),
            "kelas_1": (kelas == 1).astype(int),
            "kelas_2": (kelas == 2).astype(int),
            "kelas": kelas,
            "y": y,
        })
        bagian.append(f[el])
    return pd.concat(bagian, ignore_index=True)


# ---------------------------------------------------------------- model
class Model:
    """Regresi logistik dengan standardisasi fitur kontinu (rata-rata/SD dari data latih)."""

    def fit(self, X):
        self.mu = X[KONTINU].mean()
        self.sd = X[KONTINU].std().replace(0, 1)
        self.lr = LogisticRegression(C=1.0, max_iter=2000)
        self.lr.fit(self._z(X), X["y"].astype(int))
        self.coef = pd.Series(self.lr.coef_[0], index=FITUR)
        self.rata_z = self._z(X).mean()
        return self

    def _z(self, X):
        Z = X[FITUR].astype(float).copy()
        Z[KONTINU] = (Z[KONTINU] - self.mu) / self.sd
        return Z

    def prob(self, X):
        return self.lr.predict_proba(self._z(X))[:, 1]

    def kontribusi(self, X):
        """Kontribusi log-odds tiap fitur, relatif terhadap peserta latih rata-rata."""
        return (self._z(X) - self.rata_z) * self.coef

    def tabel_koef(self):
        t = pd.DataFrame({"fitur": FITUR, "keterangan": [LABEL_FITUR[f] for f in FITUR],
                          "koef": self.coef.values, "rasio_odds": np.exp(self.coef.values),
                          "skala": ["per 1 SD" if f in KONTINU else "ya vs tidak" for f in FITUR],
                          "sd_latih": [self.sd[f] if f in KONTINU else np.nan for f in FITUR]})
        return t.reindex(t["koef"].abs().sort_values(ascending=False).index)


def skor_aturan(X, rng):
    """Pembanding sederhana: urutkan menurut bulan nonaktif 12 bulan terakhir."""
    return X["bulan_nonaktif_12"] + 0.1 * X["n_reaktivasi_12"] + 1e-3 * rng.random(len(X))


def presisi_at_k(X, skor, k_persen):
    """Rata-rata per bulan: presisi, recall, dan lift pada k teratas."""
    hasil = []
    for _, g in X.assign(_s=skor).groupby("bulan"):
        k = max(1, int(round(len(g) * k_persen / 100)))
        top = g.nlargest(k, "_s")
        tp = top["y"].sum()
        hasil.append((k, tp / k, tp / max(g["y"].sum(), 1), (tp / k) / g["y"].mean()))
    h = np.array(hasil)
    return dict(k_rata=h[:, 0].mean(), presisi=h[:, 1].mean(), recall=h[:, 2].mean(),
                lift=h[:, 3].mean())


def kalibrasi(y, p, n_bin=10):
    q = pd.qcut(p, n_bin, labels=False, duplicates="drop")
    return pd.DataFrame({"p": p, "y": y, "bin": q}).groupby("bin").agg(
        prediksi=("p", "mean"), aktual=("y", "mean"), n=("y", "size"))


# ---------------------------------------------------------------- lapisan aksi
def saran_intervensi(baris):
    """Aturan, bukan model. Early warning hanya memicu bantuan, tidak pernah verifikasi."""
    if baris["rentang_desil"] == "1-5":
        return "cek_kelayakan_PBI"
    if not baris["autodebet"]:
        return "pengingat_H-5_dan_tawaran_autodebet"
    return "pengingat_saldo_autodebet"


def alasan(model, X, n=2):
    kon = model.kontribusi(X)
    teks = []
    for i, (_, r) in enumerate(X.iterrows()):
        top = kon.iloc[i].sort_values(ascending=False)
        bagian = []
        for f, v in top.head(n).items():
            if v <= 0:
                break
            bagian.append(_frasa(f, r))
        teks.append("; ".join(bagian) if bagian else "kombinasi faktor kecil")
    return teks


def _frasa(f, r):
    if f == "bulan_nonaktif_12":
        return f"nonaktif {int(r[f])} dari {int(r['bulan_teramati_12'])} bulan terakhir"
    if f == "n_reaktivasi_12":
        return f"{int(r[f])} kali aktif kembali dalam 12 bulan"
    if f == "bulan_telat_dibayar_12":
        return f"melunasi {int(r[f])} bulan iuran telat dalam 12 bulan terakhir"
    if f == "log_rasio_klaim_iuran_12":
        return f"klaim {np.expm1(r[f]):.1f}x iuran dalam 12 bulan"
    if f == "log_masa_kepesertaan":
        return f"peserta {np.expm1(r[f]):.0f} bulan"
    if f == "autodebet":
        return "tidak memakai autodebet" if not r[f] else "memakai autodebet"
    if f in ("kelas_1", "kelas_2"):
        return f"kelas {int(r['kelas'])}"
    return LABEL_FITUR[f] if r[f] else "tidak " + LABEL_FITUR[f]


# ---------------------------------------------------------------- grafik
def _gaya(ax):
    ax.set_facecolor(PERMUKAAN)
    ax.tick_params(colors=TINTA_2, labelsize=9)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.grid(color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)


def _koma(x, d=0):
    return f"{x:.{d}f}".replace(".", ",")


def _panel_presisi(ax, kurva, judul, label_pembanding, ymax):
    pct = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%")
    ax.plot(kurva["k"], kurva["model"] * 100, color=WARNA_MODEL, lw=2, marker="o", ms=6,
            label="Regresi logistik", zorder=3)
    ax.plot(kurva["k"], kurva["pembanding"] * 100, color=WARNA_ATURAN, lw=2, marker="s", ms=6,
            label=label_pembanding, zorder=3)
    dasar = kurva["dasar"].iloc[0] * 100
    ax.axhline(dasar, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(kurva["k"].max(), dasar + ymax * 0.015, f"base rate {_koma(dasar)}%", color=TINTA_2,
            fontsize=8.5, ha="right", va="bottom")
    ax.set_ylim(0, ymax)
    ax.yaxis.set_major_formatter(pct)
    ax.xaxis.set_major_formatter(pct)
    ax.set_xlabel("k: porsi peserta yang dihubungi per bulan", color=TINTA_2, fontsize=10)
    ax.set_ylabel("Presisi pada k teratas", color=TINTA_2, fontsize=10)
    ax.set_title(judul, loc="left", fontsize=11, color=TINTA, fontweight="bold")
    leg = ax.legend(frameon=False, fontsize=9, loc="upper right")
    for t in leg.get_texts():
        t.set_color(TINTA)


def plot(kal, kurva_semua, kurva_baru, auc, auc_baru, path):
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 5.4), dpi=160)
    fig.patch.set_facecolor(PERMUKAAN)
    for ax in (a1, a2, a3):
        _gaya(ax)
    pct = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%")

    a1.plot([0, 1], [0, 1], color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1)
    a1.text(0.06, 0.13, "kalibrasi sempurna", color=TINTA_2, fontsize=8.5, rotation=45,
            rotation_mode="anchor", transform=a1.transAxes)
    a1.plot(kal["prediksi"], kal["aktual"], color=WARNA_MODEL, lw=2, marker="o", ms=6, zorder=3)
    a1.set_xlim(0, 1)
    a1.set_ylim(0, 1)
    a1.xaxis.set_major_formatter(pct)
    a1.yaxis.set_major_formatter(pct)
    a1.set_xlabel("Peluang yang diprediksi (rata-rata per desil)", color=TINTA_2, fontsize=10)
    a1.set_ylabel("Porsi yang benar-benar menunggak", color=TINTA_2, fontsize=10)
    a1.set_title(f"Kalibrasi, data uji 2025 (AUC {_koma(auc, 2)})", loc="left", fontsize=11,
                 color=TINTA, fontweight="bold")

    _panel_presisi(a2, kurva_semua, "Semua peserta aktif: model = aturan",
                   "Aturan: bulan nonaktif 12 bln", 100)
    _panel_presisi(a3, kurva_baru, f"Belum pernah menunggak (AUC {_koma(auc_baru, 2)})",
                   "Aturan (di sini = acak)", 60)

    fig.text(0.008, 0.975, "Early warning: peluang peserta aktif menunggak dalam 3 bulan",
             ha="left", va="top", fontsize=13, fontweight="bold", color=TINTA)
    fig.text(0.008, 0.928, "Data sintetis. Latih 2023-07 s.d. 2024-09, uji 2025-01 s.d. 2025-09. "
             "Pola perilaku ditanam di generator, jadi angka ini menguji pipeline, bukan performa "
             "di data BPJS.", ha="left", va="top", fontsize=9.5, color=TINTA_2)
    fig.tight_layout(rect=(0, 0, 1, 0.89), w_pad=2.5)
    fig.savefig(path, facecolor=PERMUKAAN)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="hasil")
    ap.add_argument("--k_daftar", type=float, default=5,
                    help="ukuran daftar operasional, %% peserta aktif (= kapasitas petugas)")
    ap.add_argument("--seed", type=int, default=7, help="pemecah seri skor aturan")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    D, _ = saring_cakupan(muat(a.data))
    P = bangun_panel(D)
    tr = P[P["bulan"].between(*LATIH)]
    te = P[P["bulan"].between(*UJI)].copy()

    model = Model().fit(tr)
    te["p"] = model.prob(te)
    te["p_aturan"] = skor_aturan(te, rng)

    lab = D["label"].set_index("id_peserta")["segmen"]
    te["segmen"] = te["id_peserta"].map(lab)              # hanya untuk evaluasi

    out = []
    say = out.append
    say("== EARLY WARNING: peluang peserta aktif menunggak dalam 3 bulan (data sintetis) ==")
    say(f"panel latih  {LATIH[0]} s.d. {LATIH[1]} : {len(tr):,} peserta-bulan, "
        f"{tr['id_peserta'].nunique():,} peserta, base rate {tr['y'].mean():.1%}")
    say(f"panel uji    {UJI[0]} s.d. {UJI[1]} : {len(te):,} peserta-bulan, "
        f"{te['id_peserta'].nunique():,} peserta, base rate {te['y'].mean():.1%}")

    auc = roc_auc_score(te["y"], te["p"])
    auc_aturan = roc_auc_score(te["y"], te["p_aturan"])
    per_bulan = te.groupby("bulan").apply(lambda g: roc_auc_score(g["y"], g["p"]),
                                          include_groups=False)
    baru = te[te["pernah_nonaktif"] == 0]
    say("\n-- Diskriminasi --")
    say(f"AUC model                      : {auc:.3f} (per bulan {per_bulan.min():.3f}-{per_bulan.max():.3f})")
    say(f"AUC aturan sederhana           : {auc_aturan:.3f}")
    say(f"AUC subset belum pernah nonaktif: {roc_auc_score(baru['y'], baru['p']):.3f} "
        f"(n = {len(baru):,}; base rate {baru['y'].mean():.1%})")

    say("\n-- Kalibrasi --")
    say(f"Brier model {brier_score_loss(te['y'], te['p']):.4f}; "
        f"Brier tanpa model (base rate latih) {brier_score_loss(te['y'], np.full(len(te), tr['y'].mean())):.4f}")
    say(f"rata-rata prediksi {te['p'].mean():.1%} vs aktual {te['y'].mean():.1%}")
    kal = kalibrasi(te["y"].to_numpy(), te["p"].to_numpy())
    say(kal.round(3).to_string())
    ks = te.groupby("segmen").agg(prediksi=("p", "mean"), aktual=("y", "mean"), n=("y", "size"))
    say("\nkalibrasi per segmen laten (label hanya untuk evaluasi):")
    say(ks.round(3).to_string())

    say("\n-- Presisi pada k teratas, rata-rata per bulan uji --")
    say("k = kapasitas petugas. Angka resmi kapasitas belum tersedia, jadi k dinyatakan "
        "sebagai % peserta aktif per bulan.")
    baris = []
    for k in K_PERSEN:
        m_ = presisi_at_k(te, te["p"], k)
        r_ = presisi_at_k(te, te["p_aturan"], k)
        baris.append((k, round(m_["k_rata"]), m_["presisi"], r_["presisi"], m_["recall"],
                      r_["recall"], m_["lift"]))
    tk = pd.DataFrame(baris, columns=["k_persen", "k_orang_per_bulan", "presisi_model",
                                      "presisi_aturan", "recall_model", "recall_aturan",
                                      "lift_model"])
    say(tk.round(3).to_string(index=False))

    say("\n-- Subset peserta yang belum pernah nonaktif sejak 2023 --")
    say("Di sini aturan sederhana tidak punya informasi (semua bernilai 0), jadi sama dengan acak.")
    say("Ini satu-satunya bagian di mana model memberi nilai tambah atas aturan.")
    baris = []
    for k in K_PERSEN:
        m_ = presisi_at_k(baru, baru["p"], k)
        r_ = presisi_at_k(baru, baru["p_aturan"], k)
        baris.append((k, round(m_["k_rata"]), m_["presisi"], r_["presisi"], m_["recall"],
                      m_["lift"]))
    say(pd.DataFrame(baris, columns=["k_persen_subset", "k_orang_per_bulan", "presisi_model",
                                     "presisi_aturan_acak", "recall_model", "lift_model"]
                     ).round(3).to_string(index=False))
    kb = baru.groupby("segmen").agg(n=("y", "size"), base_rate=("y", "mean"))
    say("isi subset menurut segmen laten:")
    say(kb.round(3).to_string())

    say(f"\nkomposisi {a.k_daftar:g}% teratas menurut segmen laten (hanya evaluasi):")
    top = te.groupby("bulan", group_keys=False).apply(
        lambda g: g.nlargest(max(1, int(round(len(g) * a.k_daftar / 100))), "p"))
    komp = top.groupby("segmen").agg(n=("y", "size"), presisi=("y", "mean"))
    komp["porsi"] = komp["n"] / komp["n"].sum()
    say(komp.round(3).to_string())

    say("\n-- Koefisien (dilatih 2023-07 s.d. 2024-09) --")
    say("Rasio odds > 1 menaikkan peluang menunggak. Kontinu: per 1 SD; biner: ya vs tidak.")
    say("Observasi berulang per peserta, jadi selang kepercayaan biasa tidak valid dan tidak dilaporkan.")
    koef = model.tabel_koef()
    say(koef[["keterangan", "rasio_odds", "skala"]].round(2).to_string(index=False))
    koef.round(4).to_csv(os.path.join(a.out, "early_warning_koefisien.csv"), index=False)

    # kurva presisi untuk grafik
    ks_grid = [1, 2, 5, 10, 15, 20, 30]

    def kurva(X):
        return pd.DataFrame({
            "k": ks_grid,
            "model": [presisi_at_k(X, X["p"], k)["presisi"] for k in ks_grid],
            "pembanding": [presisi_at_k(X, X["p_aturan"], k)["presisi"] for k in ks_grid],
            "dasar": X.groupby("bulan")["y"].mean().mean(),
        })

    plot(kal, kurva(te), kurva(baru), auc, roc_auc_score(baru["y"], baru["p"]),
         os.path.join(a.out, "early_warning.png"))

    # daftar operasional: model dilatih ulang pada semua bulan berlabel, skor bulan terakhir
    berlabel = P[P["y"].notna() & (P["bulan"] >= LATIH[0])]
    final = Model().fit(berlabel)
    akhir = P[P["bulan"] == P["bulan"].max()].copy()
    akhir["skor"] = final.prob(akhir)
    k = max(1, int(round(len(akhir) * a.k_daftar / 100)))
    daftar = akhir.nlargest(k, "skor").copy()
    daftar = daftar.merge(D["dtsen"][["id_peserta", "rentang_desil"]], on="id_peserta", how="left")
    daftar["rentang_desil"] = daftar["rentang_desil"].fillna("tidak_padan")
    daftar["alasan"] = alasan(final, daftar)
    daftar["saran_intervensi"] = daftar.apply(saran_intervensi, axis=1)
    daftar["peringkat"] = np.arange(1, len(daftar) + 1)
    kol = ["peringkat", "id_peserta", "bulan", "skor", "alasan", "saran_intervensi",
           "rentang_desil", "autodebet", "kelas"]
    daftar[kol].round({"skor": 3}).to_csv(os.path.join(a.out, "early_warning_daftar.csv"), index=False)
    say(f"\n-- Daftar operasional bulan {akhir['bulan'].iloc[0]} (label belum ada) --")
    say(f"model dilatih ulang pada {len(berlabel):,} peserta-bulan berlabel; "
        f"{len(akhir):,} peserta aktif dinilai; {k} teratas ({a.k_daftar:g}%) masuk daftar")
    say(daftar["saran_intervensi"].value_counts().to_string())

    teks = "\n".join(out)
    print(teks)
    with open(os.path.join(a.out, "early_warning_ringkasan.txt"), "w", encoding="utf-8") as f:
        f.write(teks + "\n")


if __name__ == "__main__":
    main()
