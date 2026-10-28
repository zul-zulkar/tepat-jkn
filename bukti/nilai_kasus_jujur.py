"""
nilai_kasus_jujur.py - N03: berapa orang dari tiap jenis kasus jujur yang masuk jalur
diperiksa (T3, T5), dengan aturan asli (A) dan aturan tanpa IGD (B). Juga presisi dan
recall jalur diperiksa di data dasar untuk A dan B (analisis sensitivitas IGD,
pra-registrasi bagian 5; aturan yang dipakai tetap A).

Jalankan dari folder utama repo, SETELAH pra-registrasi lengkap di-push:
    python bukti/nilai_kasus_jujur.py

Membaca: data/ (data dasar seed 2026) dan bukti/data_jujur/ (dari bukti/kasus_jujur.py).
Menulis ke bukti/hasil/:
    {kasus_jujur,data_dasar}_rute_{asli,tanpa_igd}_{jumlah,persen}.csv
    ringkasan_n03.csv  (satu baris per jenis x aturan)
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))        # cek_sinyal.py ASLI di folder utama, bukan salinan di bukti/

import pandas as pd

import cek_sinyal as A                    # aturan asli
import cek_sinyal_tanpa_igd as B          # bukti/cek_sinyal_tanpa_igd.py

assert Path(A.__file__).resolve().parent == AKAR, f"cek_sinyal terbaca dari {A.__file__}"
HASIL = AKAR / "bukti" / "hasil"
HASIL.mkdir(parents=True, exist_ok=True)
JALUR = "verifikasi_pola_reaktivasi"
CURANG = {"reaktivasi_saat_butuh", "baru_berhenti_cepat"}

ringkas = []
for folder, nama in [(AKAR / "bukti" / "data_jujur", "kasus_jujur"), (AKAR / "data", "data_dasar")]:
    D, _ = A.saring_cakupan(A.muat(str(folder)))
    re = A.tabel_reaktivasi(D["status"], D["bayar"])
    for varian, m in [("asli", A), ("tanpa_igd", B)]:
        p = m.triase(m.fitur_peserta(D, re))
        v = p.merge(D["label"][["id_peserta", "segmen"]], on="id_peserta")
        jumlah = pd.crosstab(v["segmen"], v["rute"], margins=True, margins_name="total")
        persen = pd.crosstab(v["segmen"], v["rute"], normalize="index").round(3)
        jumlah.to_csv(HASIL / f"{nama}_rute_{varian}_jumlah.csv")
        persen.to_csv(HASIL / f"{nama}_rute_{varian}_persen.csv")
        masuk = v["rute"].eq(JALUR)
        for seg, g in v.groupby("segmen"):
            ringkas.append(dict(data=nama, aturan=varian, jenis=seg, n=len(g),
                                masuk_jalur_diperiksa=int(g["rute"].eq(JALUR).sum()),
                                persen=round(100 * g["rute"].eq(JALUR).mean(), 2)))
        if nama == "data_dasar":
            curang = v["segmen"].isin(CURANG)
            ringkas.append(dict(data=nama, aturan=varian, jenis="RINGKAS jalur diperiksa",
                                n=int(masuk.sum()), masuk_jalur_diperiksa=int((masuk & curang).sum()),
                                persen=round(100 * (masuk & curang).sum() / masuk.sum(), 2)))
            ringkas.append(dict(data=nama, aturan=varian, jenis="RINGKAS tertangkap dari semua curang",
                                n=int(curang.sum()), masuk_jalur_diperiksa=int((masuk & curang).sum()),
                                persen=round(100 * (masuk & curang).sum() / curang.sum(), 2)))

r = pd.DataFrame(ringkas)
r.to_csv(HASIL / "ringkasan_n03.csv", index=False)
with pd.option_context("display.width", 140, "display.max_rows", 100):
    print(r.to_string(index=False))
print("\nCatatan: baris 'RINGKAS jalur diperiksa' = presisi (berapa % isi jalur yang memang curang);")
print("'RINGKAS tertangkap' = recall (berapa % orang curang yang masuk jalur).")
