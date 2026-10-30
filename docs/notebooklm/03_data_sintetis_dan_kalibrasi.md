# Data sintetis TEPAT dan kalibrasinya ke Data Sampel BPJS 2024

Kondisi per 30 Oktober 2026 (commit `f194054`).

## Prinsip

- **Semua data peserta di repo buatan tim (sintetis).** Tidak ada data peserta JKN atau DTSEN asli.
- Angka perilaku dan biaya di profil bawaan **dikarang tim** dan belum memakai tarif INA-CBG.
- Generator: `generate_data.py`. Seed yang sama menghasilkan data yang sama persis.
- Data penuh (sekitar 50 MB) tidak di-commit; dibuat ulang dengan
  `python generate_data.py --n 20000 --seed 2026 --out data` (sekitar 20 detik).
- Contoh kecil di `data_sampel/`: 500 peserta mandiri + 75 peserta kelompok lain (seed 2026).

## Dunia yang disimulasikan

- Periode: Januari 2023 sampai Desember 2025.
- `--n 20000` peserta PBPU/BP mandiri, ditambah 15% dari n peserta kelompok lain (PPU, PBI,
  PBPU/BP-Pemda) supaya analisis bisa membuktikan bahwa kelompok itu dikeluarkan.
- 40 wilayah karangan, masing-masing dengan indeks kemiskinan.

### Segmen laten (kunci jawaban, profil `asumsi`)

| Segmen | Porsi | Perilaku |
|---|---|---|
| `patuh` | 52% | Bayar rutin. |
| `lalai` | 25% | Mampu, sering bolong, lalu melunasi. |
| `tidak_mampu` | 13% | Bayar rutin sampai kena guncangan ekonomi, lalu berhenti. 25% sudah jatuh miskin sebelum 2023. |
| `reaktivasi_saat_butuh` | 10% | Nyaris tidak membayar, melunasi menjelang layanan mahal, lalu berhenti lagi. **45%** dari segmen ini "pengakal_45": menunda rawat inap terjadwal sampai lewat hari ke-45. Segmen ini juga 1,8x lebih sering butuh layanan mahal (seleksi adversal). |

Semua porsi ini karangan tim. Label disimpan di tabel terpisah (`label_ground_truth`) dan hanya
dipakai untuk mengukur hasil.

### Kebutuhan layanan (profil `asumsi`, per orang-tahun, dikali faktor usia)

| Jenis | Laju | Biaya rata-rata | Cara masuk |
|---|---|---|---|
| Rawat jalan biasa | 0,80 | Rp300 ribu | poli |
| Rawat jalan seri (kemoterapi, radioterapi, rehabilitasi) | 0,012 | Rp2,5 juta | poli |
| Rawat inap darurat | 0,04 | Rp7 juta | IGD |
| Rawat inap elektif | 0,05 | Rp12 juta | terjadwal |

Faktor usia pada laju layanan juga asumsi tim tanpa sumber. Ini penting untuk temuan keadilan
(lihat sumber 05): peserta di atas 55 tahun lebih sering masuk jalur verifikasi, dan sebagian besar
kemiringan itu datang dari asumsi ini.

### DTSEN

Flag biner (desil `1-5` atau `6-10`) dengan satu tanggal pemutakhiran. Sengaja dibuat terlambat
diperbarui: orang yang jatuh miskin setelah tanggal itu sering masih tercatat 6-10. Ini yang
membuat pola "rutin lalu berhenti" berguna.

## Tujuh tabel

| Tabel | Kolom utama |
|---|---|
| `peserta` | id_peserta (nama samaran), tgl_daftar, kelas, iuran_bulanan, usia_2023, jenis_kelamin, kode_wilayah, autodebet, segmen_kepesertaan (PBPU/BP/PPU/PBI/PBPU_BP_Pemda), pembayar_iuran |
| `pembayaran` | tgl_bayar, periode_awal, periode_akhir, jumlah_bulan_dibayar, nominal, kanal |
| `riwayat_status` | tgl_mulai, tgl_selesai, status (aktif/nonaktif/masa_tunggu) |
| `klaim` | id_episode, tgl_masuk, tgl_keluar, jenis_layanan (RJTL/RITL), cara_masuk, kelompok_layanan, biaya_klaim, denda_pelayanan |
| `dtsen_flag` | rentang_desil, tgl_pemutakhiran |
| `wilayah` | kode_wilayah, indeks_kemiskinan |
| `label_ground_truth` | segmen, pengakal_45, peserta_baru, tgl_guncangan. **Hanya untuk mengukur hasil.** |

## Aturan JKN yang ditiru (disederhanakan)

| Aturan di generator | Dasar | Status |
|---|---|---|
| Hanya PBPU/BP yang bayar sendiri yang dianalisis | Perpres 59/2024 Ps. 42 ayat 7-8 | Berlaku |
| Iuran: K1 Rp150.000, K2 Rp100.000, K3 Rp42.000 (Rp35.000 peserta + Rp7.000 bantuan) | Perpres 64/2020 Ps. 34 ayat 1 huruf b | Berlaku; prototipe menagih Rp42.000 penuh untuk K3 |
| Bantuan iuran K3 hanya untuk peserta aktif; bagian yang ditagih untuk bulan tertunggak belum jelas | Perpres 64/2020 Ps. 34 ayat 4 | **Terbuka** |
| Iuran pertama paling cepat 14 hari setelah daftar | Belum diverifikasi | **Terbuka** |
| Belum bayar sampai akhir bulan → jaminan berhenti mulai tanggal 1 bulan berikutnya, per peserta | Perpres 59/2024 Ps. 42 ayat 1 | Berlaku |
| Aktif lagi setelah melunasi tunggakan (maks 24 bulan) dan iuran bulan berjalan | Perpres 59/2024 Ps. 42 ayat 3; Peraturan BPJS 5/2018 Ps. 26 ayat 2 | Berlaku |
| Denda satu kali rawat inap dalam 45 hari sejak aktif lagi: 5% × biaya × bulan tertunggak (maks 12), maks Rp20 juta | Perpres 59/2024 Ps. 42 ayat 5-6; Peraturan BPJS 2/2024 Ps. 24 ayat 8 | Berlaku; biaya klaim sintetis, belum paket INA-CBG |
| Pembayaran lewat VA, sekaligus untuk seluruh anggota KK | Peraturan BPJS 5/2018 Ps. 12 ayat 3-4; Ps. 14 ayat 3-4 | **Belum ditiru**; generator masih per peserta |

Denda 2,5% dan batas Rp30 juta tidak dipakai: batas Rp30 juta dari Perpres 64/2020 Ps. 42 ayat 6
sudah diubah, dan 2,5% hanya untuk masa peralihan 2020 (ayat 6a).

## Dua profil generator

- **`asumsi` (bawaan):** parameter karangan tim. **Semua angka proposal, aplikasi, dan
  `cocokkan_angka.py` memakai profil ini.**
- **`sampel2024`:** parameter yang bisa diamati dikalibrasi ke angka agregat Data Sampel BPJS
  Kesehatan 2024. Hanya pembanding; tidak dipakai untuk target pra-registrasi T1-T8.

### Kalibrasi ke Data Sampel BPJS 2024

- `kalibrasi_sampel.py` membaca data sampel mentah dari folder **di luar repo**, lalu hanya menulis
  angka agregat ke `kalibrasi/target_sampel_bpjs_2024.csv` (71 baris ukuran).
- Aturan data (pakta integritas dan jawaban panitia 28 Okt 2026): hanya persentase, rasio, median,
  rata-rata dari kelompok besar; kelompok < 100 orang/klaim dikosongkan; jumlah dibulatkan ke
  ratusan; tanpa wilayah, faskes, ID, atau tanggal. Data mentah dan cache-nya tetap di luar repo.
- **Batas yang tidak bisa diatasi:** data sampel tidak berisi pembayaran iuran, status bulanan,
  atau tanggal aktif lagi. Status kepesertaannya satu potret akhir periode (dianggap 31 Des 2024).
  Jadi data sampel **tidak bisa memvalidasi** triase atau peringatan dini. Yang bisa: mengecek
  seberapa mirip data sintetis dengan data nyata.

Parameter `sampel2024` yang berubah: segmen menjadi patuh 40%, lalai 10%, tidak mampu 42%,
bayar-saat-butuh 8%; porsi kelas 10,8% / 14,4% / 74,8%; usia sama untuk semua segmen; biaya rawat
inap turun ke sekitar Rp4-5 juta; rawat jalan RS jauh lebih jarang; semua peserta dibuat PBPU (BP
hampir tidak pernah nonaktif karena premi). Proporsi segmen ini **satu kombinasi yang cocok**,
bukan perkiraan proporsi sebenarnya; segmen laten tetap tidak teramati.

### Seberapa mirip dengan data nyata

(PBPU dewasa, potret akhir 2024; angka data sampel berbobot.)

| Ukuran | Data sampel BPJS | Profil asumsi | Profil sampel2024 |
|---|---|---|---|
| Nonaktif karena premi, PBPU | 40,9% | 18,5% | 41,8% |
| Nonaktif karena premi, BP | 0,3% | 19,3% | BP tidak dibuat |
| Porsi kelas III | 74,8% | 47,6% | 74,6% |
| Nonaktif kelas I / kelas III | 40,8% / 40,1% | 13,0% / 23,6% | 42,0% / 41,8% |
| Peserta lama yang rawat jalan di RS dalam setahun | 13,2% | 52,6% | 12,9% |
| Median biaya rawat inap | Rp3,98 juta | Rp9,23 juta | Rp3,87 juta |
| Klaim rawat jalan RS ≥ Rp1 juta | 3,2% | 31,4% | 4,0% |
| Nonaktif sesudah klaim besar ÷ tanpa klaim besar (aktivitas terakhir Jan-Jun) | 1,81x | 3,22x | 1,66x |
| Sama, aktivitas terakhir Jul-Sep | 1,86x | 3,58x | 2,16x |
| Ukuran yang selisihnya ≤ 20% dari data sampel | - | 7 dari 34 | 26 dari 33 |

Pelajaran:
- Profil `asumsi` jauh dari kenyataan di banyak ukuran (hanya 7 dari 34 dalam selisih 20%). Ini
  harus diakui terbuka; semua angka proposal memakai profil ini.
- Pola "berhenti bayar sesudah klaim besar" memang ada di data nyata (sekitar 1,8-2,8x), tetapi
  profil asumsi melebih-lebihkannya.
- Di PBPU nyata, kelas tidak membedakan risiko menunggak. Beda antarkelas di profil asumsi karangan.
- Peserta BP hampir tidak pernah nonaktif karena premi, jadi cakupan yang tepat sebenarnya PBPU.
- Belum cocok: pendaftar baru 2024 di data nyata lebih cepat menunggak (22,7% vs generator 12,5%);
  usia belum memengaruhi risiko di generator; tingkat nonaktif di kelompok pengguna RS 1,2-1,8x
  lebih tinggi dari data nyata walau rasionya sudah cocok.

Dampaknya ke hasil TEPAT ada di sumber 04 (bagian "TEPAT di profil sampel2024").

## Data uji tambahan untuk evaluasi (folder `bukti/`)

- **Kasus jujur** (`bukti/kasus_jujur.py`, 2.500 orang, 500 per jenis, ID diawali `J-`): empat jenis
  orang jujur yang polanya mirip curang, ditambah satu jenis curang yang sengaja tidak dikenal
  aturan (jenis "ditahan"):
  - `jatuh_miskin_sakit` (jujur): rutin bayar sampai satu sakit berat, penghasilan hilang, masih
    melunasi demi berobat dalam 90 hari pertama, lalu hampir berhenti.
  - `kronis_bolong_sekali` (jujur): sering berobat seri, bayar rutin, bolong tepat satu bulan.
  - `pembayar_musiman` (jujur): melunasi saat panen (Mar-Apr, Agu-Sep), tanpa autodebet.
  - `baru_sakit_tetap_bayar` (jujur): daftar karena sakit, lalu terus bayar.
  - `baru_berhenti_cepat` (bayar-saat-butuh, ditahan): daftar akhir Apr-Jul 2025, satu rawat inap
    terjadwal, lalu berhenti; tunggakannya 3-5 bulan saat data berakhir, di bawah batas 6 bulan
    aturan TEPAT.
  Spesifikasi kelima jenis disusun tim yang juga menulis aturan, jadi ini **uji kesulitan, bukan uji
  buta**.
- **Dial konsentrasi** (`bukti/generate_konsentrasi.py`): data dasar yang sama, kecuali peserta
  bayar-saat-butuh hanya ditempatkan di wilayah W01-W05 (42-46% peserta tiap wilayah itu). Skrip
  memeriksa sendiri bahwa tabel lain identik.
