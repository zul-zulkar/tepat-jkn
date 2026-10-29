#!/usr/bin/env python3
"""
cek_realisme.py - TEPAT: bandingkan data sintetis dengan angka agregat Data Sampel BPJS
Kesehatan 2024 (kalibrasi/target_sampel_bpjs_2024.csv, dibuat oleh kalibrasi_sampel.py).

Setiap ukuran dihitung dengan definisi yang sama dengan kalibrasi_sampel.py, sejauh data
sintetis mengizinkan:
  - potret status 31 Des 2024; populasi = peserta PBPU mandiri yang sudah terdaftar;
  - "lama" = terdaftar s.d. 2022, "baru" = terdaftar 2024 (di data sampel: tahun sampel);
  - klaim besar = rawat inap atau klaim >= Rp1 juta; aktivitas = tanggal pulang klaim RS;
  - B16-B20 (rawat inap menurut usia, peserta lama) hanya pembanding, tidak dipakai kalibrasi.
Data sintetis tidak berbobot; angka sampel berbobot. Generator hanya membuat orang dewasa
dan tidak punya data FKTP, jadi baris C hanya memakai klaim RS (C01-C09).

Pemakaian:
    python cek_realisme.py --data data                       # data dasar (profil asumsi)
    python cek_realisme.py --data data --out hasil_kalibrasi --nama realisme_asumsi.csv
    python cek_realisme.py --data data_sampel2024 --out hasil_kalibrasi --nama realisme_sampel2024.csv
Keluaran: tabel di layar, dan <out>/<nama> bila --out diberikan.
"""
import argparse
import os

import numpy as np
import pandas as pd

POTRET = pd.Timestamp("2024-12-31")
AWAL = pd.Timestamp("2024-01-01")
KLAIM_BESAR = 1_000_000
JEDA_PASCA = 90
PITA_USIA = [(18, 30), (30, 45), (45, 60), (60, 200)]   # sama dengan A11-A14 dan B16-B19


def baca(folder):
    p = pd.read_csv(os.path.join(folder, "peserta.csv"), parse_dates=["tgl_daftar"])
    s = pd.read_csv(os.path.join(folder, "riwayat_status.csv"), parse_dates=["tgl_mulai", "tgl_selesai"])
    k = pd.read_csv(os.path.join(folder, "klaim.csv"), parse_dates=["tgl_masuk", "tgl_keluar"])
    return p, s, k


def ukur(p, s, k, segmen="PBPU"):
    """{kode: (nilai, n)} untuk satu segmen kepesertaan."""
    cur = s[(s.tgl_mulai <= POTRET) & (s.tgl_selesai >= POTRET)].drop_duplicates("id_peserta", keep="last")
    st = cur.set_index("id_peserta").status
    p = p.assign(st=p.id_peserta.map(st))
    p = p[p.st.notna() & (p.tgl_daftar <= POTRET)]
    p = p.assign(na=p.st.eq("nonaktif"), usia=p.usia_2023 + 1, th=p.tgl_daftar.dt.year)
    out = {}
    bp = p[p.segmen_kepesertaan.eq("BP")]
    if len(bp):
        out["A03"] = (100 * bp.na.mean(), len(bp))
    pb = p[p.segmen_kepesertaan.eq(segmen)].set_index("id_peserta")
    out["A01"] = (100 * pb.na.mean(), len(pb))
    for kode, kl in [("A05", 1), ("A06", 2), ("A07", 3)]:
        out[kode] = (100 * pb.kelas.eq(kl).mean(), len(pb))
    for kode, kl in [("A08", 1), ("A09", 2), ("A10", 3)]:
        g = pb[pb.kelas.eq(kl)]
        out[kode] = (100 * g.na.mean(), len(g))
    for kode, (a, b) in zip(["A11", "A12", "A13", "A14"], [(18, 30), (30, 45), (45, 60), (60, 200)]):
        g = pb[(pb.usia >= a) & (pb.usia < b)]
        out[kode] = (100 * g.na.mean(), len(g))
    out["A15"] = (pb.usia.mean(), len(pb))
    out["A16"] = (pb.usia.std(ddof=0), len(pb))
    for kode, (a, b) in zip(["A17", "A18", "A19", "A20"], [(0, 2016), (2017, 2021), (2022, 2023), (2024, 2024)]):
        g = pb[(pb.th >= a) & (pb.th <= b)]
        out[kode] = (100 * g.na.mean(), len(g))

    k = k[k.id_peserta.isin(pb.index) & (k.tgl_keluar >= AWAL) & (k.tgl_keluar <= POTRET)].copy()
    k["ritl"] = k.jenis_layanan.eq("RITL")
    k["besar"] = k.ritl | (k.biaya_klaim >= KLAIM_BESAR)
    ri_n = k[k.ritl].groupby("id_peserta").size()
    rj_n = k[~k.ritl].groupby("id_peserta").size()
    lama, baru = pb[pb.th <= 2022], pb[pb.th == 2024]
    b1 = 100 * lama.index.isin(ri_n.index).mean()
    b2 = 100 * baru.index.isin(ri_n.index).mean()
    out["B01"] = (b1, len(lama))
    out["B02"] = (b2, len(baru))
    out["B03"] = (b2 / b1 if b1 else np.nan, len(baru))
    out["B04"] = (100 * ri_n.reindex(lama.index).fillna(0).mean(), len(lama))
    out["B05"] = (100 * lama.index.isin(rj_n.index).mean(), len(lama))
    out["B06"] = (rj_n.reindex(lama.index).fillna(0).mean(), len(lama))
    for kode, (a, b) in zip(["B16", "B17", "B18", "B19"], PITA_USIA):   # rawat inap menurut usia (cek realisme)
        g = lama[(lama.usia >= a) & (lama.usia < b)]
        out[kode] = (100 * g.index.isin(ri_n.index).mean(), len(g))
    out["B20"] = (out["B19"][0] / out["B16"][0] if out["B16"][0] else np.nan, min(out["B16"][1], out["B19"][1]))
    ri, rj = k[k.ritl], k[~k.ritl]
    out["B07"] = (ri.biaya_klaim.median(), len(ri))
    out["B08"] = (ri.biaya_klaim.quantile(.9), len(ri))
    out["B09"] = (ri.biaya_klaim.mean(), len(ri))
    out["B10"] = (rj.biaya_klaim.median(), len(rj))
    out["B11"] = (rj.biaya_klaim.quantile(.9), len(rj))
    out["B12"] = (100 * (rj.biaya_klaim >= KLAIM_BESAR).mean(), len(rj))
    out["B13"] = ((ri.tgl_keluar - ri.tgl_masuk).dt.days.mean(), len(ri))
    m1, m3 = ri[ri.kelas_rawat.eq(1)], ri[ri.kelas_rawat.eq(3)]
    out["B14"] = (m1.biaya_klaim.median() / m3.biaya_klaim.median() if len(m1) and len(m3) else np.nan,
                  min(len(m1), len(m3)))
    out["B15"] = (100 * k.ritl.mean(), len(k))

    akhir = k.groupby("id_peserta").tgl_keluar.max()
    akhir_besar = k[k.besar].groupby("id_peserta").tgl_keluar.max()
    d = pd.DataFrame({"akhir": akhir})
    d["jeda"] = (d.akhir - akhir_besar.reindex(d.index)).dt.days
    d["kel"] = np.where(d.jeda.isna(), "tanpa", np.where(d.jeda <= JEDA_PASCA, "pasca", "lain"))
    bln = d.akhir.dt.month
    d["jen"] = np.select([bln <= 6, bln <= 9], ["jan_jun", "jul_sep"], "okt_des")
    d = d.join(pb.na)
    kode = 1
    for j in ["jan_jun", "jul_sep", "okt_des"]:
        t = d[(d.jen == j) & (d.kel == "tanpa")]
        q = d[(d.jen == j) & (d.kel == "pasca")]
        pt, pq = 100 * t.na.mean(), 100 * q.na.mean()
        out[f"C{kode:02d}"] = (pt, len(t))
        out[f"C{kode + 1:02d}"] = (pq, len(q))
        out[f"C{kode + 2:02d}"] = (pq / pt if pt else np.nan, min(len(t), len(q)))
        kode += 3
    return out


def bandingkan(folder, target):
    p, s, k = baca(folder)
    u = ukur(p, s, k)
    t = pd.read_csv(target)
    t = t[t.kode.isin(u.keys())].copy()
    t["sintetis"] = [u[c][0] for c in t.kode]
    t["n_sintetis"] = [u[c][1] for c in t.kode]
    t["rasio"] = t.sintetis / t.nilai
    t["status"] = np.where((t.rasio - 1).abs() <= 0.20, "dekat", np.where(t.rasio > 1, "terlalu tinggi",
                                                                         "terlalu rendah"))
    t.loc[t.nilai.isna(), "status"] = "-"
    return t[["kode", "uraian", "satuan", "nilai", "sintetis", "rasio", "status", "dipakai_generator",
              "n_sampel", "n_sintetis"]].rename(columns={"nilai": "sampel_bpjs"})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--target", default=os.path.join("kalibrasi", "target_sampel_bpjs_2024.csv"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--nama", default="realisme.csv")
    a = ap.parse_args()
    t = bandingkan(a.data, a.target)
    with pd.option_context("display.width", 220, "display.max_rows", 200, "display.max_colwidth", 70,
                           "display.float_format", lambda v: f"{v:,.2f}"):
        print(t.drop(columns=["n_sampel", "n_sintetis"]).to_string(index=False))
    pakai = t[t.dipakai_generator.eq("ya") & t.status.ne("-")]
    print(f"\nukuran yang dipakai kalibrasi: {len(pakai)}; dalam 20% dari sampel: "
          f"{int(pakai.status.eq('dekat').sum())}")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        f = os.path.join(a.out, a.nama)
        t.round(3).to_csv(f, index=False)
        print(f"ditulis: {f}")


if __name__ == "__main__":
    main()
