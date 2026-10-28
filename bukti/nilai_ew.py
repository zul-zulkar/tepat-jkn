#!/usr/bin/env python3
"""
nilai_ew.py - TEPAT N06: penilaian peringatan dini (T6, T7), pra-registrasi bagian 4.

Jalankan dari folder utama repo, dengan eval-kit panitia di --kit:
    python bukti/nilai_ew.py --kit ../healthkathon-eval-kit

Model dan aturan sederhana persis seperti early_warning.py (latih 2023-07 s.d. 2024-09,
uji 2025-01 s.d. 2025-09, pemecah seri aturan seed 7). Entitas = peserta-bulan,
kelompok = id_peserta (resampling per peserta).

T6: lift pada k 1% untuk peserta yang belum pernah nonaktif, uji Jan-Sep 2025 digabung:
    tiap bulan diambil 1% teratas (kapasitas per bulan), lalu hasil sembilan bulan
    dijumlah: lift = (TP / k) / base rate, keduanya dari gabungan bulan.
    Pembanding: rata-rata lift per bulan (cara early_warning.py) dan satu peringkat
    gabungan semua peserta-bulan.
T7: ablasi berpasangan eval-kit (stress.ablation): aturan sederhana vs model, k 1%,
    semua peserta aktif dan yang belum pernah nonaktif.
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))
HASIL = AKAR / "bukti" / "hasil"

import early_warning as EW  # noqa: E402
from cek_sinyal import muat, saring_cakupan  # noqa: E402

assert Path(EW.__file__).resolve().parent == AKAR


def lift_per_bulan(X, kol, porsi=0.01):
    tp = k_tot = 0
    lifts = []
    for _, g in X.groupby("bulan"):
        k = max(1, int(round(len(g) * porsi)))
        top = g.nlargest(k, kol)
        tp += top["y"].sum()
        k_tot += k
        lifts.append((top["y"].mean()) / g["y"].mean())
    gab = (tp / k_tot) / X["y"].mean()
    return dict(k_total=k_tot, tp=int(tp), presisi_gabungan=tp / k_tot, base_rate=X["y"].mean(),
                lift_gabungan=gab, lift_rata_per_bulan=float(np.mean(lifts)),
                lift_min_bulan=float(np.min(lifts)), lift_maks_bulan=float(np.max(lifts)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=str(AKAR.parent / "healthkathon-eval-kit"))
    a = ap.parse_args()
    sys.path.insert(0, a.kit)
    from hkeval import metrics as M
    from hkeval import stress

    rng = np.random.default_rng(7)
    D, _ = saring_cakupan(muat(str(AKAR / "data")))
    P = EW.bangun_panel(D)
    tr = P[P["bulan"].between(*EW.LATIH)]
    te = P[P["bulan"].between(*EW.UJI)].copy()
    model = EW.Model().fit(tr)
    te["p"] = model.prob(te)
    te["p_aturan"] = EW.skor_aturan(te, rng)
    baru = te[te["pernah_nonaktif"] == 0].copy()

    out = ["N06 peringatan dini (T6, T7)", "",
           f"cek kanonik: AUC model {roc_auc_score(te['y'], te['p']):.3f}, aturan "
           f"{roc_auc_score(te['y'], te['p_aturan']):.3f}, belum pernah nonaktif "
           f"{roc_auc_score(baru['y'], baru['p']):.3f} (n {len(baru):,}, base rate {baru['y'].mean():.1%})"]

    # T6
    r = lift_per_bulan(baru, "p")
    r_acak = lift_per_bulan(baru.assign(_a=np.random.default_rng([7, 2]).random(len(baru))), "_a")
    yb, pb = baru["y"].to_numpy(), baru["p"].to_numpy()
    lift_peringkat = M.lift_at_k(yb, pb, 0.01)
    est, lo, hi = M.bootstrap_ci(lambda y, s: M.lift_at_k(y, s, 0.01), yb, pb,
                                 groups=baru["id_peserta"].to_numpy(), n=1000, seed=0)
    t6 = pd.DataFrame([dict(uji="T6", **r, lift_peringkat_gabungan=lift_peringkat,
                            lift_peringkat_ik95_bawah=lo, lift_peringkat_ik95_atas=hi,
                            lift_acak_gabungan=r_acak["lift_gabungan"], target=">= 3x",
                            lulus=r["lift_gabungan"] >= 3)])
    t6.round(4).to_csv(HASIL / "t6_lift_ew.csv", index=False)
    out += ["", f"T6 belum pernah nonaktif, k 1% per bulan, Jan-Sep 2025 digabung: presisi "
            f"{r['presisi_gabungan']:.1%} vs base rate {r['base_rate']:.1%} -> lift {r['lift_gabungan']:.1f}x "
            f"(target >= 3x: {'LULUS' if r['lift_gabungan'] >= 3 else 'MELESET'})",
            f"    rata-rata lift per bulan {r['lift_rata_per_bulan']:.1f}x (rentang {r['lift_min_bulan']:.1f}-"
            f"{r['lift_maks_bulan']:.1f}); satu peringkat gabungan {lift_peringkat:.1f}x "
            f"(IK95% per peserta {lo:.1f}-{hi:.1f}); acak {r_acak['lift_gabungan']:.1f}x"]

    # T7: ablasi berpasangan eval-kit
    baris = []
    for nama, X in [("semua_aktif", te), ("belum_pernah_nonaktif", baru)]:
        X = X.reset_index(drop=True)
        ent = X["id_peserta"] + "|" + X["bulan"].astype(str)
        truth = HASIL / f"_ew_truth_{nama}.csv"
        pd.DataFrame({"entity_id": ent, "label": X["y"]}).to_csv(truth, index=False)
        varian = {}
        for v, kol in [("aturan sederhana", "p_aturan"), ("aturan + model", "p")]:
            f = HASIL / f"ew_{nama}_{'aturan' if kol == 'p_aturan' else 'model'}.csv"
            pd.DataFrame({"entity_id": ent, "group_id": X["id_peserta"], "score": X[kol]}).to_csv(f, index=False)
            varian[v] = str(f)
        tab = stress.ablation(varian, str(truth), capacity=0.01)
        tab.insert(0, "populasi", nama)
        baris.append(tab)
        os.remove(truth)
    t7 = pd.concat(baris)
    t7.to_csv(HASIL / "t7_ablasi_ew.csv", index=False)
    out += ["", "T7 ablasi berpasangan (eval-kit stress.ablation, k 1% dari gabungan peserta-bulan):",
            t7.to_string(index=False)]
    teks = "\n".join(out)
    print(teks)
    (HASIL / "ringkasan_n06_ew.txt").write_text(teks + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
