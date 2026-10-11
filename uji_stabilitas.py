#!/usr/bin/env python3
"""
uji_stabilitas.py - TEPAT: ulangi seluruh pipeline pada beberapa seed (= beberapa "dunia"
sintetis dengan parameter yang sama) dan catat rentang tiap metrik.

Per seed: buat data dengan generate_data.simulasi, lalu jalankan
  - uji bunching rawat inap terjadwal dan plasebo IGD (cek_sinyal.py),
  - triase dan validasinya terhadap label (cek_sinyal.py),
  - early warning: validasi waktu latih 2023-07 s.d. 2024-09, uji 2025-01 s.d. 2025-09
    (early_warning.py).
Parameter generator TIDAK diubah. Seed analisis (bootstrap, pemecah seri) sama dengan bawaan
skrip lain, sehingga baris seed 2026 identik dengan hasil/ringkasan.txt dan
hasil/early_warning_ringkasan.txt.

Yang diukur di sini adalah variasi antar-dunia dengan asumsi yang sama. Ini BUKAN
ketidakpastian terhadap kondisi nyata: kalau asumsinya salah, kelima seed salah bersama.

Pemakaian:
    python uji_stabilitas.py --seeds 2026 1 2 3 4 --n 20000 --out hasil     # +-4 menit
"""
import argparse
import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import cek_sinyal as cs
import early_warning as ew
import generate_data as gd

SEED_ANALISIS = 7   # bawaan --seed di cek_sinyal.py dan early_warning.py

KETERANGAN = {
    "bunching_lebih": "bunching terjadwal: kelebihan hari 46-60 (kasus)",
    "bunching_ci_bawah": "bunching terjadwal: batas bawah IK95% kelebihan",
    "bunching_kurang": "bunching terjadwal: kekurangan hari 31-45 (kasus)",
    "bunching_lompat": "bunching terjadwal: lompatan = kelebihan + kekurangan",
    "bunching_lompat_ci_bawah": "bunching terjadwal: batas bawah IK95% lompatan",
    "denda_terhindar_juta": "denda terhindar (Rp juta, biaya sintetis)",
    "lunas_hari0": "melunasi tunggakan di hari masuk RS (kasus)",
    "plasebo_igd_lebih": "plasebo IGD: kelebihan hari 46-60 (kasus)",
    "plasebo_igd_lompat": "plasebo IGD: lompatan",
    "plasebo_igd_lompat_ci_bawah": "plasebo IGD: batas bawah IK95% lompatan",
    "plasebo_igd_lompat_ci_atas": "plasebo IGD: batas atas IK95% lompatan",
    "verifikasi_presisi": "rute verifikasi: presisi (target reaktivasi_saat_butuh)",
    "verifikasi_recall": "rute verifikasi: recall",
    "pbi_presisi": "rute cek PBI: presisi (target tidak_mampu)",
    "pbi_recall": "rute cek PBI: recall",
    "rehab_presisi": "rute pengingat/REHAB: presisi (target lalai)",
    "rehab_recall": "rute pengingat/REHAB: recall",
    "tidak_mampu_di_verifikasi": "peserta tidak mampu yang masuk rute verifikasi (orang)",
    "pbi_lewat_pola": "rute PBI tertangkap lewat pola meski DTSEN belum 1-5 (orang)",
    "ew_auc": "early warning: AUC uji",
    "ew_auc_aturan": "early warning: AUC aturan bulan nonaktif",
    "ew_auc_belum_pernah": "early warning: AUC peserta belum pernah nonaktif",
    "ew_presisi_1pct_model": "early warning: presisi 1% teratas, model",
    "ew_presisi_1pct_aturan": "early warning: presisi 1% teratas, aturan",
    "ew_presisi_5pct_model": "early warning: presisi 5% teratas, model",
    "ew_presisi_5pct_aturan": "early warning: presisi 5% teratas, aturan",
    "ew_belum_pernah_presisi_1pct": "early warning: presisi 1% teratas di peserta belum pernah nonaktif",
}


def satu_seed(n, seed):
    with tempfile.TemporaryDirectory() as tmp:
        for nama, df in gd.simulasi(n, seed, round(0.15 * n)).items():
            df.to_csv(os.path.join(tmp, f"{nama}.csv"), index=False)
        D, _ = cs.saring_cakupan(cs.muat(tmp))
    r = {"seed": seed}

    # bunching dan plasebo (urutan dan seed rng sama dengan cek_sinyal.main)
    re = cs.tabel_reaktivasi(D["status"], D["bayar"])
    h = cs.analisis_bunching(D["klaim"], re, np.random.default_rng(SEED_ANALISIS))
    pl = cs.analisis_bunching(D["klaim"], re, np.random.default_rng([SEED_ANALISIS, 45]),
                              cara_masuk="IGD")
    r.update(bunching_lebih=h["lebih"], bunching_ci_bawah=h["ci"][0], bunching_kurang=h["kurang"],
             bunching_lompat=h["lompat"], bunching_lompat_ci_bawah=h["ci_lompat"][0],
             denda_terhindar_juta=h["denda_terhindar"] / 1e6, lunas_hari0=h["hari0"],
             plasebo_igd_lebih=pl["lebih"], plasebo_igd_lompat=pl["lompat"],
             plasebo_igd_lompat_ci_bawah=pl["ci_lompat"][0],
             plasebo_igd_lompat_ci_atas=pl["ci_lompat"][1])

    # triase
    p = cs.triase(cs.fitur_peserta(D, re))
    v = p.merge(D["label"], on="id_peserta")
    for kunci, rute, seg in [("verifikasi", "verifikasi_pola_reaktivasi", "reaktivasi_saat_butuh"),
                             ("pbi", "rujuk_cek_kelayakan_PBI", "tidak_mampu"),
                             ("rehab", "pengingat_autodebet_REHAB", "lalai")]:
        tp = ((v["rute"] == rute) & (v["segmen"] == seg)).sum()
        r[f"{kunci}_presisi"] = tp / max((v["rute"] == rute).sum(), 1)
        r[f"{kunci}_recall"] = tp / max((v["segmen"] == seg).sum(), 1)
    r["tidak_mampu_di_verifikasi"] = int(((v["rute"] == "verifikasi_pola_reaktivasi")
                                          & (v["segmen"] == "tidak_mampu")).sum())
    r["pbi_lewat_pola"] = int(p["jeda_dtsen"].sum())

    # early warning (logika sama dengan early_warning.main)
    P = ew.bangun_panel(D)
    tr = P[P["bulan"].between(*ew.LATIH)]
    te = P[P["bulan"].between(*ew.UJI)].copy()
    model = ew.Model().fit(tr)
    te["p"] = model.prob(te)
    te["p_aturan"] = ew.skor_aturan(te, np.random.default_rng(SEED_ANALISIS))
    baru = te[te["pernah_nonaktif"] == 0]
    r.update(ew_auc=roc_auc_score(te["y"], te["p"]),
             ew_auc_aturan=roc_auc_score(te["y"], te["p_aturan"]),
             ew_auc_belum_pernah=roc_auc_score(baru["y"], baru["p"]))
    for k in (1, 5):
        r[f"ew_presisi_{k}pct_model"] = ew.presisi_at_k(te, te["p"], k)["presisi"]
        r[f"ew_presisi_{k}pct_aturan"] = ew.presisi_at_k(te, te["p_aturan"], k)["presisi"]
    r["ew_belum_pernah_presisi_1pct"] = ew.presisi_at_k(baru, baru["p"], 1)["presisi"]
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[2026, 1, 2, 3, 4])
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", default="hasil")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    baris = []
    for s in a.seeds:
        print(f"seed {s} ...", flush=True)
        baris.append(satu_seed(a.n, s))
    per_seed = pd.DataFrame(baris).set_index("seed")
    per_seed.round(4).to_csv(os.path.join(a.out, "stabilitas_per_seed.csv"))

    rk = pd.DataFrame({
        "metrik": per_seed.columns,
        "keterangan": [KETERANGAN[c] for c in per_seed.columns],
        "min": per_seed.min().values,
        "maks": per_seed.max().values,
        f"seed_{a.seeds[0]}": per_seed.iloc[0].values,
    })
    rk.round(4).to_csv(os.path.join(a.out, "stabilitas_ringkasan.csv"), index=False)

    out = [f"== UJI STABILITAS: {len(a.seeds)} seed ({', '.join(map(str, a.seeds))}), "
           f"n = {a.n:,} + {round(0.15 * a.n):,} segmen lain, parameter generator bawaan =="]
    say = out.append
    say("Rentang = variasi antar-dunia sintetis dengan asumsi sama, bukan ketidakpastian nyata.\n")
    tampil = rk.copy()
    for c in ["min", "maks", f"seed_{a.seeds[0]}"]:
        tampil[c] = [f"{x:.1%}" if ("presisi" in m or "recall" in m) else
                     (f"{x:.3f}" if m.startswith("ew_auc") else f"{x:,.0f}")
                     for m, x in zip(tampil["metrik"], tampil[c])]
    say(tampil[["keterangan", "min", "maks", f"seed_{a.seeds[0]}"]].to_string(index=False))

    n_seed = len(per_seed)
    say("\n-- Uji lolos/gagal per seed --")
    say(f"bunching terjadwal: IK95% lompatan di atas 0 pada "
        f"{int((per_seed['bunching_lompat_ci_bawah'] > 0).sum())}/{n_seed} seed")
    pl_ok = (per_seed["plasebo_igd_lompat_ci_bawah"] <= 0) & (per_seed["plasebo_igd_lompat_ci_atas"] >= 0)
    say(f"plasebo IGD: IK95% lompatan mencakup 0 pada {int(pl_ok.sum())}/{n_seed} seed")
    say(f"plasebo IGD, ukuran lama (kelebihan 46-60 saja): "
        f"{per_seed['plasebo_igd_lebih'].min():.0f} s.d. {per_seed['plasebo_igd_lebih'].max():.0f} kasus")
    say(f"early warning: aturan >= model di 1% teratas pada "
        f"{int((per_seed['ew_presisi_1pct_aturan'] >= per_seed['ew_presisi_1pct_model']).sum())}/{n_seed} seed")

    teks = "\n".join(out)
    print(teks)
    with open(os.path.join(a.out, "stabilitas_ringkasan.txt"), "w", encoding="utf-8") as f:
        f.write(teks + "\n")


if __name__ == "__main__":
    main()
