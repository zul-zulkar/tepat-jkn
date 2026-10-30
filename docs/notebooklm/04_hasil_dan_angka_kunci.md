# Hasil dan angka kunci TEPAT

Kondisi per 30 Oktober 2026 (commit `f194054`). Semua angka dari data sintetis, profil `asumsi`,
seed 2026, kecuali disebut lain. Angka ini dijalankan ulang pada 30 Okt 2026 dan cocok 58 dari 58
dengan angka kanonik (`cocokkan_angka.py`).

> **Cara membaca:** tim menanam pola di data buatan sendiri, lalu mencoba menemukannya lagi. Angka
> di bawah membuktikan kode bekerja. Angka ini **belum** mengukur kinerja di data BPJS yang asli.

Berkas sumber: `hasil/ringkasan.txt`, `hasil/early_warning_ringkasan.txt`,
`hasil/stabilitas_ringkasan.txt`, `hasil/daya_uji_ringkasan.txt`, `hasil_kalibrasi/ringkasan.txt`.

## 1. Cakupan

- Dianalisis: 20.000 peserta PBPU/BP mandiri.
- Dikeluarkan: 1.543 PPU, 1.036 PBI, 421 PBPU/BP-Pemda (total 3.000).
- 159 kasus aktif-lagi peserta PPU tidak dihitung, karena terjadi akibat pemberi kerja telat bayar.

## 2. Jumlah per rute triase (tanpa label)

| Rute | Peserta | Tunggakan (Rp miliar) | Klaim (Rp miliar) | Iuran dibayar (Rp miliar) |
|---|---|---|---|---|
| `verifikasi_pola_reaktivasi` | 909 | 0,88 | 22,64 | 1,50 |
| `rujuk_cek_kelayakan_PBI` | 2.133 | 1,51 | 10,37 | 2,80 |
| `pengingat_autodebet_REHAB` | 5.059 | 0,18 | 30,18 | 14,64 |
| `nonaktif_lama_tanpa_sinyal` | 224 | 0,43 | 0,00 | 0,00 |
| `tanpa_tindakan` | 11.675 | 0,53 | 66,20 | 32,21 |

603 peserta rute PBI tertangkap lewat pola "rutin lalu berhenti" padahal DTSEN mereka belum desil 1-5.

## 3. Ketepatan triase (dibanding kunci jawaban)

**Presisi:** dari peserta yang masuk sebuah jalur, berapa persen yang memang kelompok sasarannya.
**Recall:** dari semua anggota kelompok sasaran, berapa persen yang masuk jalur itu.

| Jalur | Sasaran | Presisi | Recall |
|---|---|---|---|
| `verifikasi_pola_reaktivasi` | bayar saat butuh | 98,0% | 44,3% |
| `rujuk_cek_kelayakan_PBI` | tidak mampu | 86,3% | 70,5% |
| `pengingat_autodebet_REHAB` | lalai | 86,8% | 88,7% |

- 18 peserta tidak mampu salah masuk jalur verifikasi (0 peserta patuh). Ini kesalahan yang paling
  ingin dikurangi tim.
- Isi jalur verifikasi: 891 bayar-saat-butuh + 18 tidak mampu.
- Recall jalur verifikasi rendah (44,3%) karena sebagian peserta bayar-saat-butuh belum perlu berobat
  selama masa pengamatan, jadi polanya belum terlihat.

## 4. Uji lonjakan hari ke-45

| Ukuran | Rawat inap terjadwal | Plasebo IGD |
|---|---|---|
| Kasus 0-120 hari setelah reaktivasi | 1.295 | 1.073 (536 di hari 0) |
| Kelebihan hari 46-60 | 169 (IK95% 131-213) | 24 (IK95% −1 s.d. 51) |
| Kekurangan hari 31-45 | 58 | −21 (negatif = juga kelebihan) |
| **Lompatan** | **227 (IK95% 185-274)** | **4 (IK95% −24 s.d. 31), mencakup 0** |

- Lunas tunggakan tepat di hari masuk RS: 62 kasus (sinyal terpisah).
- Perkiraan denda yang lolos: **Rp745 juta** (satu rawat inap per reaktivasi, maks Rp20 juta, biaya
  sintetis).
- Kenapa memakai lompatan, bukan kelebihan saja: di IGD, hari 46-60 juga kelebihan 24 kasus, tetapi
  hari 31-45 ikut kelebihan 21 kasus. Artinya kurva perkiraannya yang terlalu rendah, bukan ada yang
  menunda.
- Di data sintetis IGD memang tidak pernah ditunda, jadi plasebo ini menguji **metode**, bukan
  perilaku. Di data nyata, sebagian rawat inap terencana bisa masuk lewat IGD.

## 5. Peringatan dini

Latih: 2023-07 s.d. 2024-09 (203.457 peserta-bulan). Uji: 2025-01 s.d. 2025-09 (129.390
peserta-bulan). Tingkat dasar menunggak 21,2%.

| Ukuran (data uji) | Nilai |
|---|---|
| AUC model, semua peserta aktif | 0,854 (per bulan 0,845-0,866) |
| AUC aturan sederhana "bulan nonaktif dalam 12 bulan" | 0,822 |
| Brier model / tanpa model | 0,1127 / 0,1673 |
| Presisi 5% teratas, model / aturan | 80,1% / 79,4% |
| Presisi 1% teratas, model / aturan | 93,4% / 95,0% |
| AUC peserta yang belum pernah nonaktif | 0,708 (n 68.445; tingkat dasar 6,0%) |
| Presisi 1% teratas di kelompok itu | 52,2% (lift 8,6x) |

Bacaan jujur:
- Untuk semua peserta, model **tidak lebih baik** dari aturan sederhana bila petugas hanya sanggup
  menghubungi sedikit orang. Di k ≤ 2%, aturan malah sedikit lebih tepat di semua seed.
- Model berguna untuk peserta yang **belum pernah menunggak**. Di kelompok itu aturan sederhana sama
  dengan menebak acak (semua bernilai 0).
- Model meremehkan risiko peserta tidak mampu (tebakan 37,5%, kenyataan 66,2%), karena generator
  tidak membuat tanda-tanda sebelum orang jatuh miskin.
- Skala nasional untuk gambaran: k 1% ≈ 175 ribu orang per bulan dari 17,46 juta peserta PBPU
  Mandiri aktif (30 Sep 2025). Angka kapasitas petugas resmi belum ada, jadi presisi dilaporkan
  untuk k 0,5-20% (`hasil/early_warning_presisi_k.csv`).

## 6. Stabilitas di 5 seed (2026, 1, 2, 3, 4)

Lima dunia sintetis dengan aturan sama. Ini variasi antar-dunia, **bukan** ketidakpastian terhadap
kondisi nyata: kalau asumsinya salah, kelimanya salah bersama.

| Angka | Terkecil-terbesar |
|---|---|
| Lonjakan terjadwal: kelebihan hari 46-60 | 152-242 kasus |
| Lonjakan terjadwal: lompatan (IK95% di atas 0 di 5 dari 5 seed) | 192-268 |
| Plasebo IGD: lompatan (IK95% mencakup 0 di 4 dari 5 seed) | −8 s.d. 28 |
| Denda yang lolos | Rp592-989 juta |
| Jalur verifikasi: presisi / recall | 98,0-98,6% / 43,0-46,7% |
| Jalur cek PBI: presisi / recall | 84,9-86,9% / 70,5-72,9% |
| Jalur pengingat: presisi / recall | 86,7-88,0% / 88,1-89,2% |
| Tidak mampu di jalur verifikasi | 13-18 orang |
| Peringatan dini: AUC | 0,849-0,854 |
| Aturan ≥ model di 1% teratas | 5 dari 5 seed |

Di seed 3, lompatan IGD 28 (IK95% 1-57), sedikit di atas nol. Jadi dengan data sebesar ini uji bisa
memberi sinyal palsu sampai sekitar 30 kasus; tim tidak mengklaim efek di bawah itu.

## 7. Daya uji lonjakan (`daya_uji_bunching.py`)

Ada 1.233 rawat inap terjadwal 1-120 hari setelah aktif lagi. Dengan jumlah itu, uji menangkap
penundaan 8 dari 10 kali (daya 80%) bila sedikitnya **54 kasus (4,4%)** bergeser melewati hari ke-45.
Dengan 10.000 kasus cukup 1,6%. Kalau penundaannya menyebar (46 + Exp(15) hari), butuh 87 kasus
(7,0%). Ambang ini dari kurva mulus, jadi kebutuhan sebenarnya bisa lebih besar.

| Kasus | Ambang lompatan | MDE bawaan | MDE menyebar |
|---|---|---|---|
| 250 | 19 | 24 (9,4%) | 39 (15,5%) |
| 1.000 | 37 | 48 (4,8%) | 73 (7,3%) |
| 1.233 | 42 | 54 (4,4%) | 87 (7,0%) |
| 10.000 | 115 | 162 (1,6%) | 228 (2,3%) |
| 20.000 | 170 | 260 (1,3%) | 357 (1,8%) |

## 8. TEPAT di profil sampel2024 (data lebih mirip data nyata)

Masih data sintetis, jadi tetap uji pipeline, bukan kinerja.

| Ukuran | Profil asumsi | Profil sampel2024 |
|---|---|---|
| Jalur verifikasi: peserta / presisi / recall | 909 / 98,0% / 44,3% | 720 / 89,4% / 39,1% |
| Tidak mampu di jalur verifikasi | 18 | **76** |
| Jalur cek PBI: presisi / recall | 86,3% / 70,5% | 96,0% / 66,9% |
| Jalur pengingat: presisi / recall | 86,8% / 88,7% | **58,6%** / 77,2% |
| Lonjakan terjadwal: kelebihan hari 46-60 | 169 (IK95% 131-213) | 126 (IK95% 95-160) |
| Plasebo IGD: lompatan | 4 (IK95% −24 s.d. 31) | −4 (IK95% −24 s.d. 19) |
| Peringatan dini: AUC model / aturan | 0,854 / 0,822 | 0,815 / 0,763 |
| Belum pernah nonaktif: presisi 1% teratas (tingkat dasar) | 52,2% (6,1%) | 46,5% (6,9%) |

Bacaan:
- Di data yang lebih realistis, presisi jalur verifikasi turun dari 98% ke 89%, dan orang tidak
  mampu yang salah masuk naik dari 18 ke 76 (lebih dari 4 kali). Ini angka yang paling perlu
  disampaikan jujur ke juri.
- Presisi jalur pengingat turun tajam ke 58,6%.
- Uji lonjakan dan plasebo IGD tetap berperilaku benar.
- Peringatan dini tetap berguna; selisih model atas aturan malah membesar (AUC +0,03 menjadi +0,05).
  Pengaruh kelas di model hilang (rasio odds 1,03 dan 1,00).
