#!/usr/bin/env python3
"""
nilai_jalur.py - TEPAT N06: penilaian berlabel jalur diperiksa (T1, T2, T4, T8),
mengikuti pra-registrasi bagian 3a (commit 601a1d8).

Jalankan dari folder utama repo SETELAH pra-registrasi di-push, dengan eval-kit
panitia (github.com/Luche/healthkathon-eval-kit) di --kit:
    python bukti/nilai_jalur.py --kit ../healthkathon-eval-kit

Membaca:
    bukti/hasil/skor_verifikasi{,_jujur,_konsentrasi}.csv   (N05, tanpa label)
    data/, bukti/data_jujur/, bukti/data_konsentrasi/          (label + atribut)
Menulis ke bukti/hasil/:
    t1_presisi_prevalensi.csv   T1: 5 tingkat prevalensi x 200 undian, data dasar + kasus jujur
    t2_t8_presisi.csv           T2 (data dasar) dan T8 (konsentrasi): presisi k 200, IK95% per wilayah
    t8_presisi_per_wilayah.csv  T8: presisi per wilayah di daftar periksa
    t4_beban_jujur.csv          T4: porsi peserta jujur masuk jalur per kelompok (BERLABEL)
    beban_strata.csv            porsi semua peserta masuk jalur per kelompok (TANPA label, untuk aplikasi)
    kit_scores_{dasar,konsentrasi}.csv, kit_truth_{dasar,konsentrasi}.csv   masukan eval-kit
    ringkasan_n06_jalur.txt
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AKAR = Path(__file__).resolve().parent.parent
HASIL = AKAR / "bukti" / "hasil"
JALUR = "verifikasi_pola_reaktivasi"
CURANG = {"reaktivasi_saat_butuh", "baru_berhenti_cepat"}
K_PORSI = 0.01
TINGKAT = [0.005, 0.01, 0.02, 0.05, 0.10]
N_UNDIAN = 200


def k_dari(n, porsi=K_PORSI):
    return math.ceil(round(porsi * n, 9))      # 1% dari 20.000 = 200, tanpa galat pembulatan float


def muat(folder, nama_skor):
    s = pd.read_csv(HASIL / nama_skor)
    lab = pd.read_csv(AKAR / folder / "label_ground_truth.csv", usecols=["id_peserta", "segmen"])
    ps = pd.read_csv(AKAR / folder / "peserta.csv",
                     usecols=["id_peserta", "kelas", "usia_2023", "jenis_kelamin", "kode_wilayah"])
    d = s.merge(lab, on="id_peserta", how="left", validate="one_to_one")
    d = d.merge(ps, on="id_peserta", how="left", validate="one_to_one")
    assert d["segmen"].notna().all() and d["kode_wilayah"].notna().all()
    d["y"] = d["segmen"].isin(CURANG).astype(int)
    d["jalur"] = d["rute"].eq(JALUR)
    return d


def skor_daftar(d):
    """Bagian 3a butir 3: urut id_peserta, u dari default_rng([7, 1]), skor + (1 + u) x 1e-6 di jalur."""
    d = d.sort_values("id_peserta").reset_index(drop=True)
    u = np.random.default_rng([7, 1]).random(len(d))
    assert (d.loc[d["jalur"], "skor"] >= 0).all()
    d["skor_daftar"] = np.where(d["jalur"], d["skor"] + (1 + u) * 1e-6, 0.0)
    return d


def presisi_3a(y, s, jalur, k):
    """Bagian 3a butir 2: daftar = min(k, isi jalur) anggota jalur dengan skor tertinggi."""
    m = int(min(k, jalur.sum()))
    if m == 0:
        return np.nan, 0
    idx = np.argsort(-s, kind="mergesort")[:m]
    assert jalur[idx].all()
    return float(y[idx].mean()), m


def seri_di_batas(skor_mentah, jalur, k):
    sj = np.sort(skor_mentah[jalur])[::-1]
    if len(sj) <= k:
        return 0
    return int((sj == sj[k - 1]).sum())


def kemiskinan_tiga(folder):
    w = pd.read_csv(AKAR / folder / "wilayah.csv")
    w["kemiskinan"] = pd.qcut(w["indeks_kemiskinan"].rank(method="first"), 3,
                              labels=["rendah", "sedang", "tinggi"]).astype(str)
    return w.set_index("kode_wilayah")["kemiskinan"]


def strata(d, folder):
    d = d.copy()
    d["kemiskinan"] = d["kode_wilayah"].map(kemiskinan_tiga(folder))
    d["usia"] = pd.cut(d["usia_2023"], [0, 35, 55, 200], labels=["<=35", "36-55", ">55"]).astype(str)
    d["kelas"] = "kelas_" + d["kelas"].astype(str)
    d["jk"] = d["jenis_kelamin"]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=str(AKAR.parent / "healthkathon-eval-kit"))
    a = ap.parse_args()
    sys.path.insert(0, a.kit)
    from hkeval import metrics as M

    out = ["N06 jalur diperiksa - pra-registrasi bagian 3a (commit 601a1d8)", ""]
    dasar = skor_daftar(muat("data", "skor_verifikasi.csv"))
    konsen = skor_daftar(muat("bukti/data_konsentrasi", "skor_verifikasi_konsentrasi.csv"))
    jujur = muat("bukti/data_jujur", "skor_verifikasi_jujur.csv")
    assert (dasar["id_peserta"].values == konsen["id_peserta"].values).all()

    # ---------------------------------------------------------------- T2 dan T8
    baris, per_wil = [], []
    for nama, d, target in [("T2 data dasar", dasar, "batas bawah >= 80%"),
                            ("T8 data konsentrasi", konsen, "tanpa ambang")]:
        y, s, j = d["y"].to_numpy(), d["skor_daftar"].to_numpy(), d["jalur"].to_numpy()
        g = d["kode_wilayah"].to_numpy()
        k = k_dari(len(d))
        p, lo, hi = M.bootstrap_ci(lambda yy, ss, jj: presisi_3a(yy, ss, jj, k)[0], y, s, j,
                                   groups=g, n=1000, seed=0)
        p_kit, lo_kit, hi_kit = M.bootstrap_ci(lambda yy, ss: M.precision_at_k(yy, ss, k), y, s,
                                               groups=g, n=1000, seed=0)
        _, m = presisi_3a(y, s, j, k)
        idx = np.argsort(-s, kind="mergesort")[:m]
        pw = pd.DataFrame({"kode_wilayah": g[idx], "y": y[idx]}).groupby("kode_wilayah")["y"].agg(["size", "mean"])
        pw = pw.rename(columns={"size": "diperiksa", "mean": "presisi"}).reset_index()
        pw.insert(0, "data", nama)
        per_wil.append(pw)
        baris.append(dict(uji=nama, n=len(d), prevalensi=round(y.mean(), 4), isi_jalur=int(j.sum()), k=k,
                          diperiksa=m, presisi=round(p, 4), ik95_bawah=round(lo, 4), ik95_atas=round(hi, 4),
                          presisi_kit=round(p_kit, 4), kit_ik95_bawah=round(lo_kit, 4),
                          kit_ik95_atas=round(hi_kit, 4),
                          seri_di_batas_k=seri_di_batas(d["skor"].to_numpy(), j, k),
                          wilayah_di_daftar=len(pw), presisi_wilayah_min=round(pw["presisi"].min(), 4),
                          presisi_wilayah_maks=round(pw["presisi"].max(), 4), target=target))
        out.append(f"{nama}: presisi {p:.1%} (IK95% per wilayah {lo:.1%}-{hi:.1%}), diperiksa {m} dari "
                   f"isi jalur {int(j.sum())}; eval-kit apa adanya {p_kit:.1%} ({lo_kit:.1%}-{hi_kit:.1%}); "
                   f"presisi per wilayah {pw['presisi'].min():.1%}-{pw['presisi'].max():.1%} "
                   f"({len(pw)} wilayah)")
        # masukan eval-kit (kartu bukti)
        st = strata(d, "data" if nama.startswith("T2") else "bukti/data_konsentrasi")
        tag = "dasar" if nama.startswith("T2") else "konsentrasi"
        st[["id_peserta", "kode_wilayah", "skor_daftar", "kelas", "kemiskinan", "usia", "jk"]].rename(
            columns={"id_peserta": "entity_id", "kode_wilayah": "group_id", "skor_daftar": "score"}
        ).to_csv(HASIL / f"kit_scores_{tag}.csv", index=False)
        st[["id_peserta", "y", "segmen"]].rename(columns={"id_peserta": "entity_id", "y": "label",
                                                          "segmen": "modus"}).assign(
            modus=lambda x: np.where(x["label"] == 1, x["modus"], "")
        ).to_csv(HASIL / f"kit_truth_{tag}.csv", index=False)
    pd.DataFrame(baris).to_csv(HASIL / "t2_t8_presisi.csv", index=False)
    pd.concat(per_wil).to_csv(HASIL / "t8_presisi_per_wilayah.csv", index=False)

    # ---------------------------------------------------------------- T1
    gab = skor_daftar(pd.concat([muat("data", "skor_verifikasi.csv"), jujur], ignore_index=True))
    y, s, j = gab["y"].to_numpy(), gab["skor_daftar"].to_numpy(), gab["jalur"].to_numpy()
    non, cur = np.flatnonzero(y == 0), np.flatnonzero(y == 1)
    rng = np.random.default_rng(7)
    hasil_t1 = []
    for tingkat in TINGKAT:
        n_simpan = round(tingkat * len(non) / (1 - tingkat))
        assert n_simpan <= len(cur)
        for u in range(N_UNDIAN):
            idx = np.sort(np.concatenate([non, rng.choice(cur, n_simpan, replace=False)]))
            yy, ss, jj = y[idx], s[idx], j[idx]
            k = k_dari(len(idx))
            p, m = presisi_3a(yy, ss, jj, k)
            hasil_t1.append(dict(tingkat=tingkat, undian=u, n=len(idx), prevalensi=yy.mean(), k=k,
                                 isi_jalur=int(jj.sum()), diperiksa=m, presisi=p,
                                 presisi_kit=M.precision_at_k(yy, ss, k)))
    t1 = pd.DataFrame(hasil_t1)
    t1.to_csv(HASIL / "t1_undian.csv", index=False)
    q = lambda x, a: float(np.nanquantile(x, a))  # noqa: E731
    ring = t1.groupby("tingkat").agg(
        prevalensi=("prevalensi", "mean"), k=("k", "median"), isi_jalur=("isi_jalur", "median"),
        diperiksa=("diperiksa", "median"),
        presisi_median=("presisi", "median"), presisi_bawah=("presisi", lambda x: q(x, 0.025)),
        presisi_atas=("presisi", lambda x: q(x, 0.975)),
        kit_median=("presisi_kit", "median"), kit_bawah=("presisi_kit", lambda x: q(x, 0.025)),
        kit_atas=("presisi_kit", lambda x: q(x, 0.975))).reset_index()
    ring["lift_median"] = ring["presisi_median"] / ring["prevalensi"]
    ring.round(4).to_csv(HASIL / "t1_presisi_prevalensi.csv", index=False)
    out += ["", "T1 (data dasar + kasus jujur, k 1%, 200 undian, seed 7). Target: batas bawah >= 50% di prevalensi 1%"]
    for r in ring.itertuples():
        out.append(f"  prevalensi {r.tingkat:.1%}: presisi {r.presisi_median:.1%} "
                   f"(selang 95% {r.presisi_bawah:.1%}-{r.presisi_atas:.1%}), diperiksa {r.diperiksa:.0f} "
                   f"dari k {r.k:.0f}; eval-kit apa adanya {r.kit_median:.1%} "
                   f"({r.kit_bawah:.1%}-{r.kit_atas:.1%}); lift {r.lift_median:.1f}x")

    # ---------------------------------------------------------------- T4 dan beban tanpa label
    st = strata(dasar, "data")
    jujur_mask = st["y"].eq(0)
    n_jujur_jalur = int((jujur_mask & st["jalur"]).sum())
    t4, beban = [], []
    rata_jujur = (jujur_mask & st["jalur"]).sum() / jujur_mask.sum()
    rata_semua = st["jalur"].mean()
    for kol in ["kelas", "kemiskinan", "usia", "jk"]:
        for kel, g in st.groupby(kol):
            gj = g[g["y"].eq(0)]
            pj = gj["jalur"].mean()
            t4.append(dict(strata=kol, kelompok=kel, n_jujur=len(gj), n_jujur_jalur=int(gj["jalur"].sum()),
                           porsi=round(pj, 5), rasio_ke_rata2=round(pj / rata_jujur, 2) if rata_jujur else np.nan))
            beban.append(dict(strata=kol, kelompok=kel, n_peserta=len(g), n_jalur=int(g["jalur"].sum()),
                              porsi_jalur=round(g["jalur"].mean(), 4),
                              rasio_ke_rata2=round(g["jalur"].mean() / rata_semua, 2)))
    t4 = pd.DataFrame(t4)
    t4.to_csv(HASIL / "t4_beban_jujur.csv", index=False)
    pd.DataFrame(beban).to_csv(HASIL / "beban_strata.csv", index=False)
    out += ["", f"T4: {n_jujur_jalur} peserta jujur di jalur diperiksa (data dasar); syarat dinilai >= 30 -> "
            + ("dinilai" if n_jujur_jalur >= 30 else "terlalu sedikit untuk dinilai"),
            f"    rasio tertinggi ke rata-rata: {t4['rasio_ke_rata2'].max():.2f}x "
            f"({t4.loc[t4['rasio_ke_rata2'].idxmax(), 'strata']} {t4.loc[t4['rasio_ke_rata2'].idxmax(), 'kelompok']})"]
    teks = "\n".join(out)
    print(teks)
    (HASIL / "ringkasan_n06_jalur.txt").write_text(teks + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
