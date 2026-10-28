# Hasil penilaian T1-T8 (N06)

Dijalankan 28 Okt 2026, 17.50-18.10 WITA, setelah pra-registrasi bagian 3a di-push
(`601a1d8`, 17.48 WITA). Data sintetis profil `asumsi`, seed 2026. Data yang dibuat
ulang di cloud identik dengan data di laptop: md5 sama setelah CR dibuang.
Eval-kit commit `336bf7b`.

Skrip: `bukti/nilai_kasus_jujur.py` (T3, T5, IGD), `bukti/nilai_jalur.py` (T1, T2, T4, T8),
`bukti/nilai_ew.py` (T6, T7).

## Target pra-registrasi

| Kode | Hasil | Target | Status |
|---|---|---|---|
| T1 | Presisi 60,0% (selang 95% 55,7-63,8%); diperiksa 125 orang dari kapasitas 202, karena isi jalur lebih kecil dari k. Angka eval-kit apa adanya: 38,1% (32,2-44,1%) | batas bawah >= 50% | **Lulus**, hanya dengan aturan 3a (min(k, isi jalur)). Dengan cara bawaan eval-kit, meleset |
| T2 | Presisi 98,0% (IK95% per wilayah 96,0-99,5%), 196 dari 200 | batas bawah >= 80% | **Lulus** |
| T3 | jatuh_miskin_sakit 32 dari 500 (6,4%); kronis_bolong_sekali, pembayar_musiman, baru_sakit_tetap_bayar 0 | <= 5% per jenis; jatuh_miskin_sakit <= 1% | **Meleset** (jatuh_miskin_sakit) |
| T4 | 18 peserta jujur di jalur diperiksa | dinilai bila >= 30 | **Terlalu sedikit untuk dinilai**. Rasio tertinggi, sekadar informasi: kelas 3, 1,64x |
| T5 | baru_berhenti_cepat 35 dari 500 (7,0%) | tanpa ambang | lemah |
| T6 | Lift 8,6x (presisi 52,3% vs dasar 6,0%), rentang per bulan 8,0-9,3x | >= 3x | **Lulus** (angka ini sudah diketahui sebelumnya) |
| T7 | Semua peserta aktif: aturan 94,8% vs model 93,3%, selisih -1,5 poin (IK -2,7 s.d. -0,1; p 0,03). Belum pernah nonaktif: aturan 5,1% (= acak) vs model 51,7%, selisih +46,6 poin (p < 0,01) | tanpa ambang | model hanya berguna untuk yang belum pernah nonaktif |
| T8 | Presisi 98,0% (IK95% per wilayah 92,0-99,5%, lebih lebar dari T2); W01-W05 100%; 4 wilayah lain masing-masing 1 orang jujur (0%) | tanpa ambang | isi jalur tidak berubah; yang melebar hanya selangnya |

## T1 di lima tingkat prevalensi (k 1%, 200 undian)

| Prevalensi | Diperiksa / k | Presisi (selang 95%) | Eval-kit apa adanya | Lift |
|---|---|---|---|---|
| 0,5% | 87 / 201 | 42,5% (35,9-48,5) | 18,9% | 85x |
| 1% | 125 / 202 | 60,0% (55,7-63,8) | 38,1% | 60x |
| 2% | 201 / 204 | 75,1% (72,8-76,5) | 74,0% | 38x |
| 5% | 211 / 211 | 82,9% (82,5-84,4) | 82,9% | 17x |
| 10% | 223 / 223 | 93,3% (92,8-93,3) | 93,3% | 9x |

Cek kedua untuk prevalensi 1% (hipergeometrik, tanpa simulasi): 59,8% (55,4-63,5%).

## Aturan asli (A) vs tanpa IGD (B), analisis sensitivitas

| | A (dipakai) | B |
|---|---|---|
| Jalur diperiksa, data dasar | 909 | 683 |
| Presisi / recall, data dasar | 98,0% / 44,3% | 98,8% / 33,5% |
| Peserta jujur di jalur, data dasar | 18 | 8 |
| jatuh_miskin_sakit di jalur | 32 (6,4%) | 32 (6,4%) |
| baru_berhenti_cepat di jalur | 35 (7,0%) | 35 (7,0%) |

B tidak mengubah apa pun di kasus jujur. Peserta jatuh_miskin_sakit yang ikut masuk jalur
tertangkap lewat rawat jalan lanjutan >= Rp1 juta sesudah aktif lagi, bukan lewat rawat
inap IGD. Hipotesis penilai ("jumlah orang jujur akan bertambah") tidak terbukti: di data
dasar jumlahnya berkurang, dari 18 ke 8.

## Eksploratif (tidak dipra-registrasi, jangan dipakai sebagai uji)

- **Skor urutan menaruh orang jujur di atas.** Di dalam jalur (data dasar + kasus jujur,
  976 orang, 50 jujur), AUC skor untuk membedakan curang dari jujur 0,40, di bawah acak.
  Rata-rata skor jatuh_miskin_sakit 1,79, sedangkan bayar-saat-butuh 1,44. Di T2, presisi
  200 teratas (98,0%) sama dengan presisi seluruh jalur (98,0%), jadi skor tidak menambah
  apa-apa. Di prevalensi 1%, isi jalur lebih kecil dari k, sehingga skor tidak berperan.
  Rumus tidak diubah setelah melihat hasil ini.
- **Beban tanpa label** (`beban_strata.csv`): peserta usia > 55 tahun masuk jalur
  1,66x rata-rata, usia <= 35 tahun 0,6x. Kelas, kemiskinan wilayah, dan jenis kelamin
  0,9-1,1x.
- Bug eval-kit: kartu bukti berhenti dengan ValueError bila tidak ada kelompok jujur
  (data dasar: semua 40 wilayah punya peserta bayar-saat-butuh). Kartu data dasar memakai
  peserta sebagai kelompok (`bukti_dasar_per_peserta.html`). Angka T2 per wilayah dihitung
  langsung dengan `metrics.bootstrap_ci`.
