# Cara kerja TEPAT: aturan triase, skor urutan, peringatan dini, uji lonjakan

Kondisi per 30 Oktober 2026 (commit `f194054`). Semua ambang di bawah disalin dari kode
(`cek_sinyal.py`, `early_warning.py`, `bukti/skor_verifikasi.py`).

## 1. Triase peserta yang sudah menunggak (`cek_sinyal.py`)

Triase dihitung per 31 Desember 2025 untuk peserta PBPU/BP mandiri, dari riwayat Januari 2023
sampai Desember 2025. Triase **tidak membaca label** (kunci jawaban data sintetis).

### Ciri perilaku per peserta (fungsi `fitur_peserta`)

| Ciri | Arti |
|---|---|
| `rasio_hari_aktif` | Porsi hari berstatus aktif dari seluruh hari teramati (masa tunggu tidak dihitung). |
| `n_reaktivasi` | Berapa kali peserta berpindah dari nonaktif ke aktif. |
| `n_reakt_terkait_klaim` | Berapa reaktivasi yang diikuti **klaim besar** dalam **90 hari**. |
| `porsi_reakt_terkait` | `n_reakt_terkait_klaim / n_reaktivasi`. |
| Klaim besar | Rawat inap (RITL) apa pun, atau rawat jalan (RJTL) senilai **Rp1 juta atau lebih**. |
| `rasio_klaim_iuran` | Total klaim dibagi total iuran yang dibayar. |
| `tunggakan_bulan` | Bulan tertunggak per 31 Des 2025, dari status terakhir; paling banyak 24. |
| `pola_rutin_lalu_berhenti` | Deteksi titik patah: rutin aktif sedikitnya 9 bulan, lalu nyaris tidak aktif (rata-rata aktif ≤ 25%) sedikitnya 4 bulan sampai akhir data. Skor patah ≥ 0,6. Ini tanda orang jatuh miskin yang belum tercatat di DTSEN. |
| `baru_klaim_lalu_berhenti` | Pendaftar sejak 2023 yang mendapat klaim besar dalam 0-90 hari sejak pertama aktif, lalu menunggak 6 bulan atau lebih. |
| `rentang_desil` | Flag DTSEN: `1-5` (miskin), `6-10`, atau `tidak_padan`. |

### Aturan rute (fungsi `triase`), urut prioritas

1. **`verifikasi_pola_reaktivasi`** bila
   - (`n_reakt_terkait_klaim` ≥ 1 **dan** `porsi_reakt_terkait` ≥ 0,5 **dan** `rasio_hari_aktif` < 0,5)
   - **atau** `baru_klaim_lalu_berhenti`,
   - **dan** DTSEN **bukan** desil 1-5 (pengaman).
2. **`rujuk_cek_kelayakan_PBI`** bila `tunggakan_bulan` ≥ 3 dan (DTSEN desil 1-5 **atau**
   `pola_rutin_lalu_berhenti`), dan tidak masuk rute 1.
3. **`pengingat_autodebet_REHAB`** bila `n_reaktivasi` ≥ 3, dan tidak masuk rute 1 atau 2.
4. **`nonaktif_lama_tanpa_sinyal`** bila `tunggakan_bulan` ≥ 12 dan tidak pernah reaktivasi, dan
   tidak masuk rute 2.
5. Sisanya **`tanpa_tindakan`**.

Peserta rute PBI yang tertangkap lewat pola, padahal DTSEN-nya belum desil 1-5, ditandai
`jeda_dtsen`. Di data dasar ada 603 orang seperti ini.

### Alasan satu kalimat untuk petugas

Tiap rute menghasilkan alasan yang bisa dibaca. Contoh bentuknya:
- Verifikasi: "2 dari 2 reaktivasi diikuti klaim besar <= 90 hari; aktif 30% waktu; klaim/iuran 16,7x".
- Verifikasi, pendaftar baru: "pendaftar baru: klaim besar <= 90 hari sejak aktif, lalu menunggak 8 bln; ...".
- PBI: "menunggak 7 bln; DTSEN desil 1-5" atau "...; rutin lalu berhenti sejak 2024-05 (DTSEN belum mencerminkan)".
- Pengingat: "4 kali nonaktif lalu melunasi; hanya 0 terkait klaim".
- Nonaktif lama: "menunggak 14 bln tanpa reaktivasi; perlu verifikasi kemampuan".

### Soal IGD dalam aturan

Rawat inap lewat IGD tetap dihitung sebagai klaim besar (aturan "A"). Keputusan ini ditetapkan Zul
pada 28 Okt 2026 sebelum penilaian. Alasannya: jalur verifikasi hanyalah daftar periksa untuk
petugas, bukan vonis. Varian tanpa IGD ("B") dihitung terpisah sebagai analisis sensitivitas. Di
aplikasi, petugas diberi tahu bila bukti seorang peserta hanya berupa rawat inap IGD.

## 2. Skor urutan jalur verifikasi (`bukti/skor_verifikasi.py`)

Aturan triase hanya menjawab ya/tidak. Petugas butuh urutan kalau kapasitasnya terbatas (misalnya
hanya sanggup memeriksa 200 orang). Skor dibuat **tanpa label** dan dikunci di pra-registrasi:

```
skor = porsi_reakt_terkait × (1 − rasio_hari_aktif) × ln(1 + klaim_rp / maks(iuran_rp, iuran_bulanan))
       + 1 bila baru_klaim_lalu_berhenti
skor = 0 bila DTSEN desil 1-5
```

Dalam bahasa sehari-hari: makin sering reaktivasi diikuti klaim besar, makin jarang aktif, dan
makin besar klaim dibanding iuran, makin tinggi skornya. Logaritma mencegah klaim raksasa
menenggelamkan dua pengali lain (klaim 1x iuran → 0,69; 10x → 2,40; 100x → 4,62).

Cara pakai yang dikunci (pra-registrasi bagian 3a):
- Skor **hanya mengurutkan peserta di dalam jalur verifikasi**. Peserta di luar jalur tidak pernah
  masuk daftar periksa, berapa pun skornya.
- Daftar periksa pada kapasitas k = min(k, isi jalur) peserta jalur dengan skor tertinggi. Sisa
  kapasitas tidak diisi orang lain.
- Seri dipecah acak dengan seed tetap (`default_rng([7, 1])`, tambahan (1 + u) × 0,000001).
- Di aplikasi, petugas melihat peringkat dan alasan, **bukan angka skor**. Skor tidak pernah
  ditampilkan ke peserta.

Di data dasar, skor 909 peserta jalur berkisar 0,15-5,70; 310 orang skornya tepat 1,00
(kebanyakan pendaftar baru yang hanya mendapat bonus +1).

**Catatan penting (temuan eksploratif, lihat sumber 05):** di dalam jalur, skor ini ternyata
menaruh orang jujur sedikit di atas orang yang bayar-saat-butuh (AUC 0,40, di bawah acak). Rumus
tidak diubah setelah temuan ini, sesuai pra-registrasi.

## 3. Peringatan dini (`early_warning.py`)

- **Unit:** peserta-bulan. Untuk tiap peserta yang **aktif** pada tanggal 1 bulan t, model menebak
  peluang ia **nonaktif** pada tanggal 1 salah satu bulan t+1, t+2, atau t+3.
- **Waktu:** skor keluar tanggal 1, sebelum jatuh tempo tanggal 10 (Perpres 82/2018 Ps. 40 ayat 1).
  Petugas punya sekitar 10 hari untuk mengingatkan.
- **Model:** regresi logistik.
- **Validasi waktu:** latih pada titik 2023-07 s.d. 2024-09, uji pada 2025-01 s.d. 2025-09. Jendela
  label tidak tumpang tindih. Fitur hanya memakai data sebelum titik tebakan; ini dicek dengan
  memotong data di 2024-06.
- **Fitur** (dengan rasio odds dari model latih):

| Fitur | Rasio odds |
|---|---|
| pernah nonaktif sejak 2023 | 2,53 |
| bulan iuran telat yang dilunasi, 12 bln terakhir (per 1 SD) | 1,51 |
| bulan nonaktif, 12 bln terakhir (per 1 SD) | 1,43 |
| klaim besar 2-3 bln lalu | 1,28 |
| jumlah aktif kembali, 12 bln terakhir (per 1 SD) | 1,24 |
| klaim besar bulan lalu | 1,18 |
| aktif kembali dalam 3 bln terakhir | 1,13 |
| log(1 + klaim/iuran), 12 bln terakhir (per 1 SD) | 1,10 |
| kelas 2 (dibanding kelas 3) | 0,87 |
| klaim besar 4-12 bln lalu | 0,79 |
| log(1 + bulan sejak daftar) (per 1 SD) | 0,76 |
| kelas 1 (dibanding kelas 3) | 0,76 |
| terdaftar autodebet | 0,72 |

- **Sengaja tidak dipakai:** label; flag DTSEN (hanya satu potret per 2025-01-01, dan di generator
  isinya ikut ditentukan kejadian sesudahnya, jadi bocor dari masa depan); jenis kelamin, usia,
  wilayah.
- **Lapisan aksi (aturan, bukan model):** DTSEN desil 1-5 → `cek_kelayakan_PBI`; belum autodebet →
  `pengingat_H-5_dan_tawaran_autodebet`; sudah autodebet → `pengingat_saldo_autodebet`.
  Peringatan dini **tidak pernah** mengirim orang ke jalur verifikasi.
- **Daftar operasional Desember 2025:** model dilatih ulang pada 375.076 peserta-bulan berlabel;
  14.237 peserta aktif dinilai; 712 teratas (5%) masuk daftar: 452 pengingat H-5 + tawaran
  autodebet, 173 cek kelayakan PBI, 87 pengingat saldo autodebet.

## 4. Uji lonjakan hari ke-45 (*bunching*)

Tujuan: mendeteksi apakah ada yang menunda rawat inap terjadwal sampai lewat hari ke-45 setelah
aktif lagi, supaya lolos denda pelayanan.

Langkah:
1. Ambil rawat inap **terjadwal** 0-120 hari setelah reaktivasi; hitung jumlah kasus per hari.
2. Buat kurva perkiraan "kalau tidak ada yang menunda" (kontrafaktual): polinomial derajat 4,
   di-fit hanya pada hari 1-30 dan 61-120. Hari 0 (lunas tunggakan di hari masuk RS) punya pola
   sendiri dan dikeluarkan.
3. **Kelebihan** = kasus aktual dikurangi kurva di hari 46-60.
   **Kekurangan** = kurva dikurangi kasus aktual di hari 31-45.
4. **Lompatan** = kelebihan + kekurangan. Ini ukuran ujinya. Orang yang menunda memindahkan kasus
   dari sebelum hari ke-45 ke sesudahnya, jadi kedua sisi berubah. Kalau kurvanya sekadar terlalu
   rendah, kedua jendela sama-sama kelebihan dan saling meniadakan.
5. Selang 95% dari bootstrap (300 ulangan). Uji dianggap menemukan sinyal bila IK95% lompatan di
   atas 0.
6. **Plasebo IGD:** langkah yang sama untuk rawat inap lewat IGD, yang tidak bisa ditunda. Lompatan
   IGD seharusnya sekitar 0.
7. **Perkiraan denda yang lolos:** porsi kasus berlebih × denda hipotetis kasus di hari 46-60.
   Denda = 5% × biaya klaim × min(bulan tertunggak, 12), paling tinggi Rp20 juta, hanya satu rawat
   inap per reaktivasi. Biaya klaim di sini sintetis, bukan paket INA-CBG.

Aturan tafsir yang dijaga di halaman Kebijakan: lompatan **bukan** jumlah rawat inap yang ditunda
(kasus yang pindah terhitung dua kali). Perkiraan kasus yang ditunda adalah **kelebihan** di hari
46-60.

Keterbatasan metode: polinomial dengan rentang tetap. Untuk data asli, tim menyarankan metode dengan
batasan integrasi (Chetty dkk. 2011; Kleven 2016).

## 5. Satu peserta, satu tindakan (aplikasi)

Di Daftar kerja, satu peserta hanya mendapat satu tindakan, dengan urutan prioritas:
verifikasi > cek PBI > berisiko menunggak (peringatan dini) > pengingat. Pada kapasitas 5%: daftar
triase 7.788 peserta dan daftar berisiko menunggak 650 peserta. Jumlah per rute di proposal (909,
2.133, 224) tidak berubah; 537 peserta rute pengingat ditangani lewat daftar berisiko menunggak.
