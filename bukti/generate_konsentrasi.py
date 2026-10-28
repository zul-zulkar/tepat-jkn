#!/usr/bin/env python3
"""
generate_konsentrasi.py - N04 / target T8: dial konsentrasi.

Data dasar yang sama dengan generate_data.py, dengan SATU perbedaan: peserta segmen
reaktivasi_saat_butuh (bayar-saat-butuh) hanya ditempatkan di beberapa wilayah
(bawaan W01-W05, sesuai pra-registrasi). Bobot antarwilayah di dalam lima wilayah itu
sama dengan bobot data dasar.

Undian acak lain tidak berubah, sehingga peserta lain, pembayaran, status, klaim, dan
DTSEN identik dengan data dasar. Skrip ini memeriksanya sendiri dan berhenti bila ada beda,
supaya perbandingan T8 vs T2 hanya mengukur efek konsentrasi.

Pakai (dari folder utama repo):
    python bukti/generate_konsentrasi.py
    python bukti/generate_konsentrasi.py --wilayah W01 W02 W03 W04 W05 --out bukti/data_konsentrasi
    python bukti/generate_konsentrasi.py --profil sampel2024 --out bukti/data_konsentrasi_sampel2024

Folder keluaran berisi tabel yang sama dengan data/ ditambah konsentrasi.txt (wilayah yang
dipakai dan jumlah peserta per wilayah). Label tetap di label_ground_truth.csv, hanya
untuk menilai.
"""
import argparse
import os
import sys

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AKAR)                       # generate_data.py ASLI di folder utama repo

import generate_data as gd  # noqa: E402

assert os.path.dirname(os.path.abspath(gd.__file__)) == AKAR, f"generate_data terbaca dari {gd.__file__}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--n_lain", type=int, default=None)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--profil", default="asumsi", choices=list(gd.PROFIL))
    ap.add_argument("--wilayah", nargs="+", default=[f"W{k:02d}" for k in range(1, 6)])
    ap.add_argument("--out", default=os.path.join("bukti", "data_konsentrasi"))
    a = ap.parse_args()
    n_lain = round(0.15 * a.n) if a.n_lain is None else a.n_lain

    pekat = gd.simulasi(a.n, a.seed, n_lain, profil=a.profil, wilayah_rsb=a.wilayah)
    dasar = gd.simulasi(a.n, a.seed, n_lain, profil=a.profil)

    # hanya kode_wilayah peserta bayar-saat-butuh yang boleh berbeda
    lab = pekat["label_ground_truth"].set_index("id_peserta")["segmen"]
    rsb = pekat["peserta"]["id_peserta"].map(lab).eq("reaktivasi_saat_butuh")
    for nama in pekat:
        if nama == "peserta":
            a1, b1 = pekat[nama], dasar[nama]
            sama_lain = a1.drop(columns="kode_wilayah").equals(b1.drop(columns="kode_wilayah"))
            sama_non_rsb = a1.loc[~rsb, "kode_wilayah"].equals(b1.loc[~rsb, "kode_wilayah"])
            if not (sama_lain and sama_non_rsb):
                raise SystemExit("peserta berbeda dari data dasar di luar kode_wilayah bayar-saat-butuh")
        elif not pekat[nama].equals(dasar[nama]):
            raise SystemExit(f"tabel {nama} berbeda dari data dasar")
    luar = sorted(set(pekat["peserta"].loc[rsb, "kode_wilayah"]) - set(a.wilayah))
    if luar:
        raise SystemExit(f"ada peserta bayar-saat-butuh di luar wilayah pilihan: {luar}")

    os.makedirs(a.out, exist_ok=True)
    for nama, df in pekat.items():
        df.to_csv(os.path.join(a.out, f"{nama}.csv"), index=False)
        print(f"{nama:20s} {len(df):>9,d} baris")
    ps = pekat["peserta"]
    per_w = ps.loc[rsb].groupby("kode_wilayah").size()
    porsi = (ps.loc[rsb].groupby("kode_wilayah").size() / ps[ps.kode_wilayah.isin(a.wilayah)]
             .groupby("kode_wilayah").size()).round(3)
    with open(os.path.join(a.out, "konsentrasi.txt"), "w", encoding="utf-8") as f:
        f.write(f"profil={a.profil} seed={a.seed} n={a.n} n_lain={n_lain}\n")
        f.write(f"wilayah_bayar_saat_butuh={' '.join(a.wilayah)}\n")
        f.write("peserta bayar-saat-butuh per wilayah:\n")
        for w in a.wilayah:
            f.write(f"  {w}: {int(per_w.get(w, 0))} orang ({100 * porsi.get(w, 0):.1f}% peserta wilayah itu)\n")
        f.write("Semua tabel lain identik dengan data dasar (diperiksa saat dibuat).\n")
    print(f"\nbayar-saat-butuh: {int(rsb.sum())} orang, semuanya di {', '.join(a.wilayah)}; "
          f"tabel lain identik dengan data dasar. Ringkasan: {os.path.join(a.out, 'konsentrasi.txt')}")


if __name__ == "__main__":
    main()
