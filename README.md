# TEPAT: Triase Peserta Tertunggak

Prototipe untuk **BPJS Kesehatan Healthkathon 2026**, kategori **Efisiensi Risiko pada Peserta**.

**Tim:**
1. Muhammad Zulkarnain
2. Zenda Oka Briantiko

> **Semua data di repositori ini sintetis.** Tidak ada data peserta JKN atau data DTSEN asli.
> Parameter perilaku dan biaya **ilustratif** (bukan tarif INA-CBG) dan wajib dikalibrasi bersama BPJS Kesehatan.

## Masalah

Per Februari 2026, 63,4 juta peserta JKN nonaktif. Tunggakan iuran mencapai Rp26,47 triliun, dan Rp22,29 triliun di antaranya berasal dari peserta mandiri (PBPU). Orang-orang ini punya alasan menunggak yang berbeda, tapi saat ini semuanya mendapat perlakuan yang sama:

- **tidak mampu**: rutin membayar sampai terkena guncangan ekonomi;
- **lalai**: mampu, tapi sering bolong lalu melunasi;
- **reaktivasi saat butuh**: melunasi hanya ketika akan memakai layanan mahal, lalu berhenti lagi.

Sudah ada aturan untuk pola ketiga, yaitu masa tunggu 14 hari dan denda pelayanan rawat inap ≤45 hari setelah reaktivasi. Tapi batas 45 hari bisa diakali dengan **menunda rawat inap terjadwal** sampai lewat hari ke-45.

## Pendekatan

TEPAT **tidak membuat sanksi baru**. Tiap peserta yang menunggak diarahkan ke intervensi yang sudah ada, lengkap dengan alasan yang bisa dibaca petugas:

| Rute | Untuk siapa | Intervensi yang sudah ada |
|---|---|---|
| `rujuk_cek_kelayakan_PBI` | Flag DTSEN desil 1–5, **atau** pola "rutin lalu berhenti" saat DTSEN belum diperbarui | Verifikasi pengalihan ke PBI / PBPU Pemda |
| `pengingat_autodebet_REHAB` | Sering nonaktif lalu melunasi, tidak terkait klaim | Pengingat, autodebet, cicilan REHAB |
| `verifikasi_pola_reaktivasi` | Reaktivasi berulang yang diikuti klaim besar | Prioritas verifikasi petugas |
| `nonaktif_lama_tanpa_sinyal` | Menunggak ≥12 bulan tanpa aktivitas | Verifikasi kemampuan bayar |

Prinsip yang dipakai:
1. **Indikasi miskin selalu menang.** Peserta dengan flag DTSEN 1–5 tidak pernah masuk rute verifikasi.
2. **Manusia yang memutuskan.** Keluaran sistem adalah prioritas dan alasan, bukan vonis.
3. **Tidak ada peserta yang kehilangan manfaat** karena skor.

Selain triase per peserta, ada **uji bunching** di hari ke-45 setelah reaktivasi. Uji ini menjadi bukti kebijakan apakah batas denda sedang diakali.

## Menjalankan

```bash
pip install -r requirements.txt
python generate_data.py --n 20000 --seed 2026 --out data   # ±20 detik
python cek_sinyal.py --data data --out hasil                # ±5 detik
```

Folder `data/` tidak di-commit karena ukurannya sekitar 45 MB. Buat ulang dengan perintah di atas: seed yang sama menghasilkan data yang identik. Untuk sekadar melihat struktur tabel, buka `data_sampel/` (500 peserta).

## Struktur

```
generate_data.py   generator 7 tabel sintetis (Jan 2023 – Des 2025)
cek_sinyal.py      uji bunching, fitur perilaku, triase, validasi ke label
data_sampel/       contoh 500 peserta (seed 2026)
hasil/             ringkasan.txt, bunching_hari45.png
```

## Aturan JKN yang dimodelkan (disederhanakan)

- Iuran porsi peserta: K1 Rp150.000, K2 Rp100.000, K3 Rp42.000.
- Peserta baru: bayar iuran pertama ≥14 hari setelah daftar, aktif sejak bayar.
- Nonaktif bila ada bulan sebelum bulan berjalan yang belum dibayar.
- Reaktivasi: lunasi tunggakan (maksimal 24 bulan terakhir ditagih), aktif hari itu juga.
- Denda pelayanan: rawat inap ≤45 hari sejak reaktivasi = 5% × biaya × min(bulan tertunggak, 12), maksimal Rp30 juta (Perpres 64/2020).

## Tabel

| Tabel | Kolom utama |
|---|---|
| `peserta` | id_peserta (pseudonim), tgl_daftar, kelas, iuran_bulanan, usia_2023, jenis_kelamin, kode_wilayah, autodebet |
| `pembayaran` | tgl_bayar, periode_awal, periode_akhir, jumlah_bulan_dibayar, nominal, kanal |
| `riwayat_status` | tgl_mulai, tgl_selesai, status (`aktif` / `nonaktif` / `masa_tunggu`) |
| `klaim` | id_episode, tgl_masuk, tgl_keluar, jenis_layanan (RJTL/RITL), cara_masuk, kelompok_layanan, biaya_klaim, denda_pelayanan |
| `dtsen_flag` | rentang_desil (`1-5` / `6-10`), tgl_pemutakhiran. Sengaja dibuat punya jeda pembaruan |
| `wilayah` | kode_wilayah, indeks_kemiskinan (40 wilayah fiktif) |
| `label_ground_truth` | segmen, pengakal_45, peserta_baru, tgl_guncangan. **Hanya untuk evaluasi** |

## Hasil pada data sintetis (seed 2026)

> Angka berikut **membuktikan bahwa metode dan pipeline berjalan**, bukan performa di data nyata. Pola ditanam di generator lalu dideteksi kembali.

- **Bunching:** 169 kasus rawat inap terjadwal berlebih di hari 46–60 (IK95% bootstrap 131–213). Estimasi denda yang terhindar Rp777 juta. Ada 62 kasus yang melunasi tunggakan tepat di hari masuk RS.
- **Triase** (tanpa label; label hanya dipakai untuk mengukur):

| Rute | Presisi | Recall |
|---|---|---|
| `verifikasi_pola_reaktivasi` | 98,0% | 44,3% |
| `rujuk_cek_kelayakan_PBI` | 86,3% | 70,5% |
| `pengingat_autodebet_REHAB` | 86,8% | 88,7% |

- 603 peserta tidak mampu tertangkap lewat pola bayar padahal flag DTSEN mereka belum 1–5.
- 18 peserta tidak mampu masuk rute verifikasi. Ini kesalahan yang paling ingin kami tekan.

![Bunching hari ke-45](hasil/bunching_hari45.png)

## Keterbatasan

1. **Sirkular**: pola sengaja ditanam di data sintetis. Validasi sesungguhnya butuh data BPJS.
2. **Unit perorangan**: di JKN, PBPU didaftarkan per keluarga. Bagian ini disederhanakan.
3. **Estimator bunching sederhana** (polinomial, jendela tetap). Untuk data nyata, pakai estimator dengan batasan integrasi (Chetty dkk. 2011; Kleven 2016).
4. **Flag DTSEN** diasumsikan tersedia lewat integrasi data antarlembaga resmi.
5. **Recall rute verifikasi rendah**: sebagian peserta belum butuh layanan selama jendela observasi (tersensor).
6. **Belum mengukur efek intervensi.** Langkah berikutnya adalah uji coba terkontrol per rute.

## Lisensi

MIT, lihat [LICENSE](LICENSE).
