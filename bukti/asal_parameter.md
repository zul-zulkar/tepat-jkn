# Asal parameter generator (N09)

Profil `asumsi` di `generate_data.py`, yaitu profil yang menghasilkan semua angka kanonik,
proposal, aplikasi, dan video. Satuan hitung: kelompok parameter. Satu kelompok bisa berisi
beberapa angka, misalnya iuran tiga kelas dihitung satu.

Kode: **R** = dari regulasi, **P** = dikalibrasi ke statistik publik, **K** = karangan tim,
**R?** = diperlakukan seperti aturan, tetapi dasar hukumnya belum diverifikasi.

## R: dari regulasi (6)

| # | Parameter | Nilai | Dasar |
|---|---|---|---|
| R1 | Iuran per orang per bulan | Kelas 1 Rp150.000, kelas 2 Rp100.000, kelas 3 Rp42.000 | Perpres 64/2020 Ps. 34 ayat (1) |
| R2 | Jendela denda pelayanan | 45 hari sejak aktif kembali | Perpres 59/2024 Ps. 42 ayat (5) |
| R3 | Besar denda | 5% x biaya x bulan tertunggak | Ps. 42 ayat (5)-(6) |
| R4 | Batas bulan dalam rumus denda | 12 bulan | Ps. 42 ayat (6) |
| R5 | Batas nilai denda | Rp20 juta | Ps. 42 ayat (6) |
| R6 | Tunggakan yang dibayar saat aktif kembali | paling banyak 24 bulan | Ps. 42 ayat (3) |

Aturan tanpa angka yang juga dari regulasi: penjaminan berhenti per peserta bila ada bulan
belum dibayar (ayat 1); denda hanya untuk satu rawat inap per reaktivasi (ayat 5); PPU, PBI,
dan PBPU/BP-Pemda di luar cakupan (ayat 7-8).

## R?: belum diverifikasi (2)

| # | Parameter | Nilai | Catatan |
|---|---|---|---|
| R?1 | Masa tunggu peserta baru | bayar pertama >= 14 hari setelah daftar | dasar hukum belum diverifikasi |
| R?2 | Tagihan kelas 3 untuk bulan tertunggak | Rp42.000 penuh | bantuan Rp7.000 hanya untuk peserta aktif (Perpres 64/2020 Ps. 34 ayat 4); porsi yang ditagih belum pasti |

## P: dikalibrasi ke statistik publik (0)

Tidak ada di profil `asumsi`. Profil kedua, `sampel2024`, dikalibrasi ke 66 angka agregat
Data Sampel BPJS Kesehatan 2024 (`kalibrasi/target_sampel_bpjs_2024.csv`). Hasilnya
dilaporkan terpisah (`hasil_kalibrasi/`) dan tidak mengganti angka kanonik.

## K: karangan tim (26)

| # | Parameter | Nilai di profil `asumsi` |
|---|---|---|
| K1 | Proporsi segmen laten | patuh 52%, lalai 25%, tidak mampu 13%, bayar-saat-butuh 10% |
| K2 | Porsi kelas per segmen | mis. tidak mampu 5/15/80% |
| K3 | Usia | bayar-saat-butuh rata-rata 48 (sb 13), lainnya 42 (sb 14) |
| K4 | Porsi pendaftar baru dalam jendela | bayar-saat-butuh 35%, lainnya 20% |
| K5 | Tidak mampu yang sudah jatuh miskin sebelum 2023 | 25% |
| K6 | Peluang bayar bulanan per segmen | patuh 97,5-99,5%; lalai 60-80%; tidak mampu 90-95% lalu 5% sesudah guncangan; bayar-saat-butuh 2% |
| K7 | Peluang melunasi tunggakan demi berobat | patuh 97%, lalai 90%, bayar-saat-butuh 98%, tidak mampu 85% lalu 20% |
| K8 | Pengali melunasi demi rawat jalan ringan | bayar-saat-butuh 0,10; lainnya 0,35 |
| K9 | Porsi bayar-saat-butuh yang menunda rawat inap lewat hari ke-45 | 45% |
| K10 | Waktu tunda | hari ke-46 + rata-rata 4 hari |
| K11 | Laju kebutuhan layanan per orang-tahun | rawat jalan biasa 0,80; seri 0,012; IGD 0,04; terjadwal 0,05 |
| K12 | Biaya rata-rata dan sebaran per jenis layanan | Rp300 rb; Rp2,5 jt; Rp7 jt; Rp12 jt (log-normal) |
| K13 | Pengali tarif per kelas | 1,2 / 1,1 / 1,0 |
| K14 | Bayar-saat-butuh lebih sering butuh layanan mahal | 1,8x |
| K15 | Faktor usia pada laju layanan | 0,6 + (usia - 18)/40, dibatasi 0,6-2,2 |
| K16 | Porsi autodebet | lama: 35% (tidak mampu 20%); baru: 85% |
| K17 | Tunggakan sebelum 2023 | lalai 40% punya 1-4 bulan; bayar-saat-butuh 85% punya 3-18 bulan |
| K18 | Jeda masuk rawat inap terjadwal | gamma (rata-rata ±24 hari) |
| K19 | Lama rawat inap | IGD 1 + Poisson(3); terjadwal 1 + Poisson(2) |
| K20 | Lama pengobatan seri | 12-26 kunjungan mingguan |
| K21 | Bayar-saat-butuh tetap membayar sesudah layanan terakhir | 20 hari |
| K22 | Cakupan DTSEN dan peluang tercatat desil 1-5 | cakupan 92%; tidak mampu 85% (sesudah guncangan sebelum snapshot) atau 20%; lainnya 8-15% |
| K23 | Tanggal pemutakhiran DTSEN | 1 Jan 2025 |
| K24 | Kemiskinan 40 wilayah | Beta(2, 7) |
| K25 | Porsi PBPU dan BP | 85 / 15% |
| K26 | Segmen di luar cakupan | PPU 50%, PBI 35%, Pemda 15%; 10% PPU nonaktif karena pemberi kerja |

Perilaku lima jenis kasus jujur (`bukti/kasus_jujur.py`) juga karangan tim, dan tidak
dihitung di atas.

## Seberapa angka bergantung pada karangan

| Perubahan | Angka | Sumber |
|---|---|---|
| Bayar-saat-butuh 1% peserta, bukan 10% (ditambah kasus jujur pengecoh) | presisi rute verifikasi 98,0% -> 60,0% (selang 55,7-63,8) | `bukti/hasil/ringkasan_n06_jalur.txt` |
| Generator dikalibrasi ke Data Sampel BPJS 2024 (`sampel2024`) | presisi rute verifikasi 98,0% -> 89,4%; patuh/tidak mampu di rute verifikasi 18 -> 76; AUC peringatan dini 0,854 -> 0,815 | `hasil_kalibrasi/ringkasan.txt`, `hasil_kalibrasi/early_warning_ringkasan.txt` |
