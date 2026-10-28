# Pra-registrasi evaluasi TEPAT

File ini di-push ke GitHub sebelum penilaian dijalankan. Jam push di GitHub
membuktikan target di bawah ditetapkan sebelum hasil diketahui. Perubahan
sesudahnya hanya lewat commit baru yang menyebut alasannya. Susunan bagiannya
mengikuti templates/preregistration.md di healthkathon-eval-kit.

Riwayat:
- Commit bfb3c54 (24 Okt 2026, 17.02 WIB, Zenda): target T1-T8 dan hipotesis
  penilai. Bagian lain tertinggal karena yang tersalin masih template eval-kit
  kosong, dan `bukti/kasus_jujur.py` pada commit itu kosong.
- Revisi ini (28 Okt 2026): melengkapi bagian 0-3 dan 5-8, dan mengunci kode
  kasus jujur, skor urutan, dan penilai. Target T1-T8 dan hipotesis penilai
  tidak berubah (dicocokkan baris per baris dengan bfb3c54). Aturan IGD
  (bagian 5) ditetapkan Zul pada 28 Okt, sebelum penilaian apa pun.
- Revisi ini juga mengganti satu kalimat di bagian 7: angka plasebo lama tidak
  bisa ditelusuri ke berkas di repo, jadi diganti angka plasebo IGD kanonik.

## 0. Yang sudah terjadi sebelum revisi ini (diungkap)

1. Belum ada penilaian berlabel pada data kasus jujur maupun data konsentrasi.
   T3, T5, dan T8 belum dihitung.
2. 24 dan 28 Okt: perilaku generator kasus jujur dicek tanpa menjalankan aturan
   triase (jumlah per jenis, bulan bayar, sebaran tunggakan akhir). Dua rancangan
   awal diubah setelah cek ini, sebelum aturan triase dijalankan: jenis
   jatuh_miskin_sakit dijamin mengalami satu sakit berat (rancangan lama: sekitar
   dua pertiga tidak pernah sakit), dan jenis yang ditahan hanya mendapat satu
   rawat inap (rancangan lama: hampir separuh masih berobat sampai akhir tahun).
3. `bukti/kasus_jujur.py` kosong di bfb3c54. Dibangun ulang 28 Okt dari rancangan
   24 Okt. Sebaran tunggakan akhir jenis yang ditahan sama persis dengan cek
   24 Okt (dari 500 orang: 0 bulan 79, 2 bulan 47, 3 bulan 112, 4 bulan 125,
   5 bulan 98, 6 bulan 39).
4. Skor urutan jalur diperiksa dihitung 28 Okt tanpa membaca label
   (`bukti/skor_verifikasi.py`; file label diblokir di skrip itu).
5. 27-28 Okt: hasil TEPAT berlabel pada data dasar profil `sampel2024` sudah
   terlihat (presisi jalur diperiksa 89,4%; 76 peserta tidak mampu ikut masuk
   jalur itu; AUC peringatan dini 0,815). Profil itu dibuat dengan menyesuaikan
   generator ke angka agregat Data Sampel BPJS 2024
   (`kalibrasi/target_sampel_bpjs_2024.csv`). Ia bukan data pra-registrasi dan
   tidak dipakai untuk mengubah target, aturan, atau kode di bawah.
6. `generate_data.py` bertambah opsi profil (`--profil`, dan `wilayah_rsb` di
   `simulasi`). Keluaran bawaan (profil `asumsi`) identik byte-per-byte dengan
   versi e53b6d2 (tujuh CSV, md5 sama) dan `cocokkan_angka.py` 58 dari 58.
7. Aturan, generator, kasus jujur, skor, dan penilai ditulis Zul bersama asisten
   AI Claude (Anthropic). Penilaian dijalankan Claude dalam sesi bersama Zul,
   bukan oleh Zenda. Penulis detektor dan penilai karena itu tidak independen.
   Ini keterbatasan, dan dilaporkan di slide bukti.

## 1. Catatan

- Tanggal: versi pertama 24 Oktober 2026; revisi ini 28 Oktober 2026
- Penulis aturan dan generator dasar: Muhammad Zulkarnain (dengan asisten AI)
- Penilai: asisten AI Claude di sesi bersama Zul (bagian 0, butir 7)
- Zenda Oka Briantiko: mengunggah versi pertama dan menulis hipotesis IGD
- Yang diuji:
  - aturan triase `cek_sinyal.py`, commit 091dcdd
  - model peringatan dini `early_warning.py`, commit 9c8613c
- Generator data dasar: `generate_data.py`, commit e53b6d2; fd02b41 menambah
  opsi profil dengan keluaran bawaan identik (bagian 0, butir 6)
- Kode uji yang sudah di-commit di fd02b41: `bukti/kasus_jujur.py`,
  `bukti/generate_konsentrasi.py`, `bukti/skor_verifikasi.py`
- Kode uji yang di-commit bersama revisi ini: `bukti/cek_sinyal_tanpa_igd.py`,
  `bukti/nilai_kasus_jujur.py`
- Dikerjakan langsung di `main`, di atas commit 5298f7f
- Penulis generator sama dengan penulis aturan, dan ia mengenal aturannya
  saat menulis generator. Ini keterbatasan, dan dilaporkan di slide bukti.

## 2. Kondisi uji

- Sumber data: sintetis buatan tim. Tidak ada data BPJS.
- Data dasar: `generate_data.py --n 20000 --seed 2026`. 20.000 peserta PBPU/BP
  mandiri, Jan 2023 sampai Des 2025. Semua angka proposal berasal dari data ini.
- Kasus jujur: `python bukti/kasus_jujur.py --n 2500 --seed 2026 --n_lain 0
  --out bukti/data_jujur`. RNG [2026, 3], tepat 500 orang per jenis, tabel
  wilayah sama dengan data dasar, ID diawali J-.
  - jatuh_miskin_sakit (jujur): bayar seperti peserta patuh sampai satu sakit
    berat (rawat inap lewat IGD atau terjadwal, lalu perawatan lanjutan
    berkali-kali). Penghasilan hilang hari itu: sesudahnya jarang bayar,
    masih melunasi demi berobat dalam 90 hari pertama, lalu hampir berhenti.
  - kronis_bolong_sekali (jujur): berobat seri (cuci darah, kemoterapi,
    rehabilitasi) jauh lebih sering dari rata-rata, bayar seperti peserta
    patuh, ditambah satu bulan bolong yang disengaja, lalu melunasi.
  - pembayar_musiman (jujur): melunasi semua tunggakan saat panen
    (Mar-Apr dan Agu-Sep), jarang bayar di bulan lain, tanpa autodebet.
  - baru_sakit_tetap_bayar (jujur): daftar karena sedang sakit, lalu terus
    bayar seperti peserta patuh.
  - baru_berhenti_cepat (bayar-saat-butuh, jenis yang ditahan): daftar akhir
    Apr sampai Jul 2025 (25 Apr - 30 Jul), satu rawat inap terjadwal, lalu berhenti bayar.
    Dirancang agar tunggakannya 3-5 bulan saat data berakhir, di bawah batas
    6 bulan aturan TEPAT. Sebaran sebenarnya ada di bagian 0, butir 3.
  - Spesifikasi kelima jenis disusun tim yang juga menulis aturan. Ini uji
    kesulitan, bukan uji buta.
- Dial konsentrasi: `python bukti/generate_konsentrasi.py` (seed 2026). Sama
  dengan data dasar kecuali kode wilayah peserta bayar-saat-butuh, yang hanya
  W01-W05; skrip memeriksa sendiri bahwa semua tabel lain identik. Hasil
  pembuatan: 2.012 peserta bayar-saat-butuh, semuanya di W01-W05 (42-46%
  peserta tiap wilayah itu). Dunia terpisah, hanya untuk pembanding.
- Asal parameter generator:
  - dari regulasi: iuran per kelas, batas 45 hari, denda 5% per bulan
    tertunggak (maks 12 bulan, maks Rp20 juta), tunggakan maks 24 bulan
    (Perpres 64/2020, Perpres 59/2024)
  - dikalibrasi ke statistik publik: tidak ada pada profil `asumsi`, yang
    dipakai untuk semua target. Profil `sampel2024` dikalibrasi ke agregat Data
    Sampel BPJS 2024 dan TIDAK dipakai untuk T1-T8; hasilnya, bila ada,
    dilaporkan terpisah sebagai tambahan.
  - dikarang tim: proporsi segmen (patuh 52%, lalai 25%, tidak mampu 13%,
    bayar-saat-butuh 10%), peluang bayar dan reaktivasi, laju dan biaya
    layanan, porsi penunda hari ke-45 (45%), dan semua perilaku kasus jujur
- Kapasitas k: belum ada angka resmi. Rumusnya petugas x kasus per petugas
  per hari x hari kerja.
  - jalur diperiksa: 0,5%, 1%, 2% peserta (100, 200, 400 dari 20.000).
    Angka utama: 1%.
  - peringatan dini: 1% dan 5% peserta aktif per bulan.
- Prevalensi bayar-saat-butuh: 10% di generator (karangan). Presisi juga
  dihitung di 0,5%, 1%, 2%, 5%, 10% dengan mengurangi peserta
  bayar-saat-butuh secara acak, 200 undian per tingkat.
- Seed: 2026 untuk data dasar; [2026, 3] untuk kasus jujur; 7 untuk undian.

## 3. Yang dikunci sebelum penilaian

- Aturan triase tidak diubah selama evaluasi. Varian tanpa IGD (bagian 5)
  dihitung di salinan terpisah.
- Kode berikut sudah atau akan di-commit sebelum dijalankan pada label:
  - `bukti/kasus_jujur.py` (generator kasus jujur)
  - `bukti/generate_konsentrasi.py` (dial konsentrasi)
  - `bukti/skor_verifikasi.py` (skor urutan, rumus di bawah)
  - `bukti/cek_sinyal_tanpa_igd.py` (varian B, bagian 5)
  - `bukti/nilai_kasus_jujur.py` (penilai T3, T5, dan perbandingan IGD)
- Skor urutan jalur diperiksa, dibuat tanpa label:
  skor = porsi_reakt_terkait x (1 - rasio_hari_aktif)
         x ln(1 + klaim_rp / maks(iuran_rp, iuran_bulanan))
         + 1 bila baru_klaim_lalu_berhenti
  skor = 0 bila DTSEN desil 1-5.
  Rumus boleh disetel hanya supaya lebih cocok dengan aturan, tanpa melihat
  label, dan setiap perubahan di-commit sebelum dinilai.
- `label_ground_truth.csv` hanya dibaca untuk menilai.

## 4. Target

| Kode | Yang diukur | Lulus bila | Kondisi |
|---|---|---|---|
| T1 | Presisi jalur diperiksa pada k 1% | batas bawah selang 95% (200 undian) >= 50% | prevalensi 1%; data dasar + kasus jujur sebagai pengecoh |
| T2 | Presisi jalur diperiksa pada k 1% | batas bawah IK95%, resampling per wilayah, >= 80% | data dasar apa adanya (prevalensi 10%); pembanding |
| T3 | Porsi kasus jujur yang masuk jalur diperiksa | <= 5% per jenis; jatuh_miskin_sakit <= 1% (paling banyak 5 dari 500) | kasus jujur, aturan asli |
| T4 | Porsi peserta jujur yang masuk jalur diperiksa, per kelompok: kelas; kemiskinan wilayah (3 kelompok); usia (<=35, 36-55, >55); jenis kelamin | tidak ada kelompok > 2x rata-rata | data dasar; dinilai hanya bila >= 30 peserta jujur masuk jalur, kalau kurang ditulis "terlalu sedikit untuk dinilai" |
| T5 | Recall jenis yang ditahan: porsi baru_berhenti_cepat yang masuk jalur diperiksa | tanpa ambang | kasus jujur |
| T6 | Lift peringatan dini pada k 1% | >= 3x | peserta yang belum pernah nonaktif; uji Jan-Sep 2025, gabungan bulan |
| T7 | Ablasi berpasangan: aturan sederhana vs aturan + model, peringatan dini | tanpa ambang | semua peserta, dan yang belum pernah nonaktif |
| T8 | Presisi jalur diperiksa pada k 1% dan rentang per wilayah | tanpa ambang | data konsentrasi, dibanding T2 |

Tidak diukur: rupiah recall, karena kerugian per orang untuk tunggakan belum
didefinisikan.

Sudah diketahui sebelum pra-registrasi, jadi bukan uji baru:
- T6: proposal melaporkan presisi 1% teratas 52,2% vs dasar sekitar 6% pada
  peserta yang belum pernah nonaktif.
- T4: proposal melaporkan hanya 18 peserta jujur di jalur diperiksa, semuanya
  tidak mampu. Kemungkinan besar T4 berakhir "terlalu sedikit untuk dinilai".
- Varian tanpa IGD mengubah jalur diperiksa dari 909 menjadi 683 peserta
  (dihitung tanpa label).

## 5. Keputusan IGD: aturan asli dipakai, varian tanpa IGD dilaporkan

Sebagian peserta masuk jalur diperiksa karena pasangan "aktif lagi, lalu rawat
inap lewat IGD". Keadaan darurat tidak bisa diatur waktunya, jadi pasangan IGD
lemah sebagai tanda kesengajaan.

Keputusan Zul, 28 Okt 2026, sebelum penilaian: **aturan asli (A) dipakai,
apa pun hasil penilaian.** Alasan: jalur diperiksa adalah daftar periksa untuk
verifikasi lapangan oleh petugas, bukan vonis atau sanksi. Pasangan IGD tetap
diperlakukan sebagai peringatan dini yang perlu dicek, termasuk untuk peserta
yang sebenarnya melunasi karena musibah.

- Varian A (dipakai): aturan asli, rawat inap lewat IGD dihitung sebagai
  klaim besar.
- Varian B (dilaporkan, tidak dipakai): `bukti/cek_sinyal_tanpa_igd.py`,
  salinan `cek_sinyal.py` dengan satu perubahan di fungsi `fitur_peserta`
  (baris 297): rawat inap lewat IGD tidak dihitung sebagai klaim besar, baik di
  jalur reaktivasi maupun jalur pendaftar baru.
- Dibandingkan: porsi tiap jenis kasus jujur yang masuk jalur diperiksa, serta
  presisi dan recall jalur diperiksa di data dasar, untuk A dan B.
- Tidak ada aturan yang berpindah dari A ke B berdasarkan hasil. Bila A
  melanggar T3 (terutama jatuh_miskin_sakit, yang separuhnya sakit lewat IGD),
  itu dilaporkan sebagai kelemahan di slide bukti bersama angka B, dan jalur
  diperiksa dijelaskan sebagai daftar periksa. Angka 909 di proposal, aplikasi,
  dan naskah tidak berubah.
- Hipotesis penilai, ditulis sebelum hasil keluar (sama persis dengan commit
  bfb3c54):
  - jumlah orang jujur yang ikut masuk jalur diperiksa akan: Bertambah
  - ketepatan sasaran jalur diperiksa akan: Jalur periksa akan menjadi tepat
    sasaran
  - alasannya: Alasannya adalah wawancara petugas BPJS dapat menggali
    informasi untuk mengetahui lebih dalam alasan konsumen BPJS tidak rutin
    membayar sebelum klaim atau langsung melunasi tunggakan demi dapat klaim
    BPJS

## 6. Kapan dianggap gagal

- Target dengan ambang meleset kalau angkanya (untuk T1 dan T2: batas bawah
  selangnya) melewati ambang ke arah yang salah.
- Target yang meleset ditulis di slide bukti bagian titik lemah, dengan angka
  aslinya. Aturan triase tidak diubah untuk menutupinya.
- Perubahan file ini setelah push ditulis sebagai commit baru dengan alasan,
  dan disebut di slide bukti.
- Jenis kasus jujur baru yang ditambahkan setelah file ini di-push (misalnya
  dari temuan lapangan) dilaporkan terpisah sebagai tambahan, bukan bagian
  dari T3.

## 7. Uji tekan

Dijalankan:
- [ ] kasus jujur yang mirip pola (T3) dan jenis yang ditahan (T5)
- [ ] presisi di lima tingkat prevalensi (T1)
- [ ] dial konsentrasi (T8)
- [ ] ablasi berpasangan aturan sederhana vs model (T7)
- [ ] aturan asli vs tanpa IGD, sebagai analisis sensitivitas (bagian 5)
- [ ] beban per kelompok (T4): kelas, kemiskinan wilayah, usia, jenis kelamin

Tidak dijalankan:
- Plasebo data tanpa kecurangan untuk jalur diperiksa: butuh generator ketiga,
  waktu tidak cukup. Plasebo untuk uji lonjakan hari-45 memakai rawat inap IGD
  dan sudah dijalankan di data dasar: lompatan 4 (IK -24 s.d. 31),
  `hasil/ringkasan.txt`.
- Uji permutasi label: dengan presisi setinggi ini hasilnya pasti signifikan
  dan tidak menambah informasi.
- Pemindaian kebocoran: tidak dijalankan sebagai uji terpisah. Fitur aturan
  sengaja meniru pola yang ditanam generator, jadi fitur yang hampir sempurna
  menandakan data terlalu mudah, bukan label bocor. Dilaporkan sebagai
  keterbatasan.
- Review pakar buta: opsional (N11). Bila dijalankan, dilaporkan tanpa ambang.

## 8. Tanda tangan

| Nama | Peran | Tanggal |
|---|---|---|
| Zenda Oka Briantiko | mengunggah versi pertama (bfb3c54); menulis hipotesis IGD | 24 Okt 2026 |
| Muhammad Zulkarnain | penulis aturan dan generator dasar; menetapkan aturan IGD (bagian 5) | 28 Okt 2026 |
| Claude (asisten AI, Anthropic) | menulis kasus jujur, skor, dan penilai; menjalankan penilaian | 28 Okt 2026 |
