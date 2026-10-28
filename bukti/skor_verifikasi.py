#!/usr/bin/env python3
"""
skor_verifikasi.py - TEPAT N05: skor urutan jalur diperiksa (rute verifikasi_pola_reaktivasi).

Aturan triase hanya menjawab ya/tidak. Petugas butuh urutan: kalau hanya sanggup
memeriksa 200 orang, mana 200 yang pertama.

Dibuat TANPA label. Skrip ini tidak membuka label_ground_truth.csv sama sekali:
pemuat data di bawah sengaja tidak membacanya, dan pembacaan file itu diblokir.

Rumus (pra-registrasi, "Yang dikunci sebelum penilaian"):

    skor = porsi_reakt_terkait x (1 - rasio_hari_aktif)
           x ln(1 + klaim_rp / maks(iuran_rp, iuran_bulanan))
           + 1 bila baru_klaim_lalu_berhenti
    skor = 0 bila DTSEN desil 1-5 (pengaman)

Makin sering reaktivasi diikuti klaim besar, makin jarang aktif, dan makin besar
klaim dibanding iuran, makin tinggi skornya.

Jalankan dari folder utama repo:
    python bukti/skor_verifikasi.py

Menulis ke bukti/hasil/:
    skor_verifikasi.csv              data dasar (data/)
    skor_verifikasi_jujur.csv        kasus jujur (bukti/data_jujur/)
    skor_verifikasi_konsentrasi.csv  dial konsentrasi (bukti/data_konsentrasi/)
    ringkasan_n05.txt                cek tanpa label
Kolom: id_peserta, skor, rute. Skor dihitung untuk semua peserta. Urutan jalur
diperiksa = baris dengan rute == verifikasi_pola_reaktivasi, diurutkan skor menurun.
File diurutkan skor menurun, seri dipecah dengan id_peserta.
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))            # cek_sinyal.py ASLI di folder utama, bukan salinan di bukti/

import numpy as np
import pandas as pd

import cek_sinyal as cs

assert Path(cs.__file__).resolve().parent == AKAR, f"cek_sinyal terbaca dari {cs.__file__}"

HASIL = AKAR / "bukti" / "hasil"
JALUR = "verifikasi_pola_reaktivasi"
SUMBER = [
    ("data", "skor_verifikasi.csv"),
    ("bukti/data_jujur", "skor_verifikasi_jujur.csv"),
    ("bukti/data_konsentrasi", "skor_verifikasi_konsentrasi.csv"),
]

# kunci jawaban tidak boleh terbaca, sengaja atau tidak
_baca_csv = pd.read_csv


def _baca_tanpa_label(path, *a, **kw):
    if "label_ground_truth" in str(path):
        raise RuntimeError("skor_verifikasi.py tidak boleh membaca label_ground_truth.csv")
    return _baca_csv(path, *a, **kw)


pd.read_csv = _baca_tanpa_label


def muat_tanpa_label(folder):
    """Sama dengan cek_sinyal.muat, tanpa tabel label."""
    baca = lambda n, **kw: pd.read_csv(folder / f"{n}.csv", **kw)  # noqa: E731
    return dict(
        peserta=baca("peserta"),
        bayar=baca("pembayaran", parse_dates=["tgl_bayar"]),
        status=baca("riwayat_status", parse_dates=["tgl_mulai", "tgl_selesai"]),
        klaim=baca("klaim", parse_dates=["tgl_masuk", "tgl_keluar"]),
        dtsen=baca("dtsen_flag"),
    )


def skor_verifikasi(p):
    rasio = p["klaim_rp"] / np.maximum(p["iuran_rp"], p["iuran_bulanan"])
    s = p["porsi_reakt_terkait"] * (1 - p["rasio_hari_aktif"]) * np.log1p(rasio)
    s = s + p["baru_klaim_lalu_berhenti"].astype(float)
    s = s.where(p["rentang_desil"] != "1-5", 0.0)      # pengaman DTSEN 1-5
    return s.round(4)


def cek(nama, p, out):
    """Cek tanpa label: apakah urutan skor sejalan dengan aturan triase."""
    n = len(p)
    jalur = p["rute"].eq(JALUR)
    nj = int(jalur.sum())
    k1 = round(0.01 * n)
    sj = p.loc[jalur, "skor"].sort_values(ascending=False)
    teratas = p.nlargest(nj, "skor", keep="all") if nj else p.iloc[:0]
    luar_atas_min = int((~jalur & (p["skor"] > sj.min())).sum()) if nj else 0
    batas_k = sj.iloc[k1 - 1] if nj >= k1 else np.nan
    seri_k = int((sj == batas_k).sum()) if nj >= k1 else 0
    out += [
        f"== {nama} ==",
        f"peserta {n}; jalur diperiksa {nj}; k 1% = {k1}",
        f"skor > 0: {int((p['skor'] > 0).sum())}; skor kosong (NaN): {int(p['skor'].isna().sum())}",
        f"jalur diperiksa dengan skor 0 (tidak bisa diurutkan): {int((jalur & p['skor'].eq(0)).sum())}",
        f"cek cepat: dari {nj} skor tertinggi, {int(teratas['rute'].eq(JALUR).sum())} di jalur diperiksa"
        f" ({teratas['rute'].eq(JALUR).mean():.1%})" if nj else "cek cepat: jalur kosong",
        f"peserta di luar jalur dengan skor di atas skor terendah jalur: {luar_atas_min}",
        f"skor jalur: maks {sj.max():.4f}, median {sj.median():.4f}, min {sj.min():.4f}" if nj else "",
        f"skor jalur pada peringkat {k1}: {batas_k:.4f}; peserta jalur dengan skor itu: {seri_k}"
        if nj >= k1 else f"jalur ({nj}) lebih kecil dari k 1% ({k1})",
        f"jalur dengan tambahan +1 (pendaftar baru klaim lalu berhenti): "
        f"{int((jalur & p['baru_klaim_lalu_berhenti']).sum())}",
        "",
    ]


def main():
    HASIL.mkdir(parents=True, exist_ok=True)
    out = ["N05 skor_verifikasi - cek tanpa label (label_ground_truth.csv tidak dibaca)", ""]
    for folder, keluar in SUMBER:
        D, _ = cs.saring_cakupan(muat_tanpa_label(AKAR / folder))
        assert "label" not in D
        re = cs.tabel_reaktivasi(D["status"], D["bayar"])
        p = cs.triase(cs.fitur_peserta(D, re))
        p["skor"] = skor_verifikasi(p)
        assert p["skor"].notna().all(), "ada skor kosong"
        assert p["id_peserta"].is_unique
        assert p.loc[p["rentang_desil"].eq("1-5"), "skor"].eq(0).all(), "pengaman DTSEN 1-5 bocor"
        assert not p.loc[p["rentang_desil"].eq("1-5"), "rute"].eq(JALUR).any()
        hasil = (p[["id_peserta", "skor", "rute"]]
                 .sort_values(["skor", "id_peserta"], ascending=[False, True]))
        hasil.to_csv(HASIL / keluar, index=False)
        cek(folder, p, out)
    teks = "\n".join(out)
    print(teks)
    (HASIL / "ringkasan_n05.txt").write_text(teks + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
