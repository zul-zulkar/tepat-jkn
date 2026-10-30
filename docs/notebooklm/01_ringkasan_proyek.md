# Ringkasan proyek TEPAT

Kondisi per 30 Oktober 2026 (commit `f194054`, repo `zul-zulkar/tepat-jkn`).

## Identitas

- **Nama:** TEPAT, singkatan dari Triase Peserta Tertunggak.
- **Lomba:** BPJS Kesehatan Healthkathon 2026, kategori **Efisiensi Risiko pada Peserta**.
- **Tim:** Muhammad Zulkarnain (Zul) dan Zenda Oka Briantiko.
- **Bentuk:** prototipe. Terdiri dari pipeline analitik Python, aplikasi web Streamlit, API tipis
  (FastAPI), dan lapisan AI untuk draf pesan.
- **Lisensi:** MIT.
- **Data:** seluruhnya sintetis buatan tim. Tidak ada data peserta JKN atau data DTSEN asli di
  repo. Angka agregat dari Data Sampel BPJS Kesehatan 2024 dipakai untuk kalibrasi; panitia
  mengizinkan angka agregat seperti itu tampil di repo publik (jawaban panitia 28 Okt 2026).

## Masalah yang dijawab

Per Februari 2026 ada 63,4 juta peserta JKN nonaktif. Tunggakan iuran mencapai Rp26,47 triliun,
dan Rp22,29 triliun di antaranya dari peserta mandiri (PBPU). Sumber: Bisnis.com, 11 Februari 2026.

Tim melihat tiga alasan orang menunggak:

1. **Tidak mampu.** Dulu rutin bayar, lalu berhenti karena kesulitan ekonomi.
2. **Lalai.** Sebenarnya mampu, tapi sering telat, lalu melunasi.
3. **Bayar saat butuh.** Baru melunasi tunggakan ketika mau berobat mahal, lalu berhenti lagi.

Saat ini ketiganya diperlakukan sama. Di data tunggakan, ketiganya tampak sama: nonaktif, sekian
bulan tertunggak.

Untuk kelompok ketiga, aturan sudah punya rem: peserta yang dirawat inap dalam 45 hari setelah
aktif lagi membayar denda pelayanan untuk satu kali rawat inap (Perpres 59/2024 Ps. 42 ayat 5-6).
Celahnya: rawat inap terjadwal bisa ditunda sampai lewat hari ke-45, dan dendanya hilang.

Melunasi tunggakan sebelum berobat itu sah (Ps. 42 ayat 3). TEPAT **tidak menuduh** siapa pun
curang. TEPAT hanya menandai pola yang perlu dicek petugas.

## Tiga komponen TEPAT

1. **Sebelum menunggak: peringatan dini** (`early_warning.py`). Regresi logistik yang menebak
   peluang peserta aktif mulai menunggak dalam 3 bulan. Skor dihitung tiap tanggal 1, sebelum
   jatuh tempo tanggal 10. Skor hanya memicu bantuan: pengingat, tawaran autodebet, atau cek
   kelayakan PBI. Skor ini tidak pernah memasukkan orang ke jalur verifikasi.
2. **Sudah menunggak: triase empat rute** (`cek_sinyal.py`). Tiap peserta yang menunggak mendapat
   satu jalan bantuan yang sudah ada, dengan alasan satu kalimat untuk petugas:
   - `rujuk_cek_kelayakan_PBI`: cek apakah layak pindah ke PBI atau dibayari Pemda.
   - `pengingat_autodebet_REHAB`: pengingat, autodebet, cicilan REHAB.
   - `verifikasi_pola_reaktivasi`: petugas mengecek dulu pola "aktif lagi lalu klaim besar".
   - `nonaktif_lama_tanpa_sinyal`: petugas mengecek kemampuan bayar.
3. **Kebijakan: uji lonjakan hari ke-45** (*bunching*). Melihat apakah rawat inap terjadwal
   menumpuk tepat sesudah hari ke-45, dibanding rawat inap IGD yang tidak bisa ditunda (plasebo).
   Hasilnya bahan untuk pembuat kebijakan, bukan untuk menindak orang per orang.

TEPAT tidak membuat hukuman baru. Semua tindakan di keempat rute sudah ada di BPJS.

## Tiga pegangan (pengaman)

1. **Tanda miskin selalu menang.** Peserta DTSEN desil 1-5 tidak pernah masuk jalur verifikasi.
   Ini dicek ulang oleh kode di beberapa tempat (`cek_sinyal.py`, `siapkan_app.py`, `api.py`).
2. **Petugas yang memutuskan.** TEPAT hanya memberi urutan dan alasan.
3. **Skor tidak boleh membuat peserta kehilangan jaminan.** Skor tidak mengubah status atau manfaat.

## Cakupan

Hanya peserta PBPU/BP yang membayar iuran sendiri. Peserta PPU, PBI, dan PBPU/BP yang iurannya
dibayar Pemda dikeluarkan, karena aturan iuran dan dendanya berbeda (Perpres 59/2024 Ps. 42
ayat 7-8). Di data dasar: 20.000 peserta dianalisis, 3.000 dikeluarkan.

## Status singkat per 30 Oktober 2026

Sudah jadi:
- Generator data sintetis dengan dua profil (`asumsi` dan `sampel2024`).
- Aturan triase, uji lonjakan + plasebo IGD, model peringatan dini, uji stabilitas 5 seed,
  simulasi daya uji.
- Pemeriksa angka kanonik (`cocokkan_angka.py`, 58 pemeriksaan; lolos 58/58 saat dicek ulang
  30 Okt 2026).
- Aplikasi Streamlit empat halaman: Daftar kerja, Profil peserta, Kebijakan, Keadilan.
- API triase (`api.py`) untuk 1-50 peserta.
- Lapisan AI draf pesan (`llm.py`) dengan cadangan template; 37 uji lulus.
- Pra-registrasi evaluasi dan penilaian T1-T8 (28 Okt 2026).
- Kalibrasi ke angka agregat Data Sampel BPJS 2024 dan analisis sensitivitas keadilan.

Belum beres atau tertunda:
- Review pakar buta (N11): lembar sudah disiapkan dan sidik jarinya dicatat, tetapi hasil penilaian
  pakar belum ada di repo.
- README belum memuat halaman Kebijakan dan Keadilan, API, lapisan AI, dan hasil T1-T8 (detail di
  sumber 08).
- Tagihan per KK belum dimodelkan.
- Belum ada pengukuran di data BPJS asli. Semua angka performa berasal dari data sintetis.

## Hasil paling penting dalam satu paragraf

Di data sintetis (seed 2026), jalur verifikasi berisi 909 peserta dengan presisi 98,0% dan recall
44,3%. Uji lonjakan menemukan kelebihan 169 rawat inap terjadwal di hari 46-60, sedangkan plasebo
IGD tidak melonjak. Model peringatan dini punya AUC 0,854, tetapi **tidak lebih baik** dari aturan
sederhana untuk semua peserta; model hanya berguna untuk peserta yang belum pernah menunggak
(lift 8,6x). Di evaluasi pra-registrasi, T3 **meleset**: 6,4% peserta jujur jenis "jatuh miskin
karena sakit" ikut masuk jalur verifikasi (target paling banyak 1%). Semua angka ini membuktikan
kode bekerja di data buatan sendiri, belum membuktikan kinerja di data BPJS.
