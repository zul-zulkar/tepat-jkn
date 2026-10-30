# Aplikasi, API, dan lapisan AI TEPAT

Kondisi per 30 Oktober 2026 (commit `f194054`).

## 1. Aplikasi Streamlit (`app.py`)

Jalankan dengan `streamlit run app.py`. Aplikasi **tidak menghitung apa pun saat dibuka**: semua
hasil dihitung sekali oleh `siapkan_app.py` dan disimpan di `app_data/` (sekitar 3,6 MB, batas
20 MB, ikut di-commit). Memori aplikasi sudah dipangkas dari sekitar 550 MB ke 435 MB supaya muat di
batas Streamlit Community Cloud. Alamat aplikasi yang sudah di-deploy tidak tercatat di repo.

Tampilan: palet dan font sama dengan deck proposal (Plus Jakarta Sans untuk huruf, JetBrains Mono
untuk angka; keduanya lisensi OFL). Logo TEPAT di `static/logo/`, ikon Lucide di `ikon.py`.

Empat halaman:

### a. Daftar kerja (halaman utama)
"Siapa yang ditangani bulan ini, lewat jalur apa, dan kenapa."
- Dua daftar: **triase pola bayar** (peserta yang sudah menunggak) dan **berisiko menunggak**
  (dari model peringatan dini, 3 bulan ke depan).
- Filter: wilayah, rute, kapasitas k (slider 1-20% peserta aktif, bawaan 5%).
- Satu peserta hanya mendapat satu tindakan: verifikasi > cek PBI > berisiko menunggak > pengingat.
  Pada k 5%: triase 7.788 peserta, berisiko menunggak 650.
- Bagian verifikasi diurutkan menurut skor urutan, tetapi petugas hanya melihat peringkat dan
  alasan, bukan angka skor.
- Memilih satu baris membuka profil peserta.

### b. Profil peserta
- Bisa dibuka langsung lewat alamat `/profil?id=P-002329`.
- Isi: ringkasan, tindakan bulan ini, rute dan alasan, linimasa 3 tahun (bayar, status, klaim,
  aktif lagi), keputusan petugas, draf pesan.
- Sorotan "klaim besar ≤ 90 hari setelah aktif kembali" memakai konstanta yang sama dengan
  `cek_sinyal.py`. Bila bukti seseorang hanya rawat inap IGD, petugas diberi tahu.
- **Keputusan petugas:** setuju atau tolak. Alasan menolak yang tersedia:
  "Data tidak sesuai kondisi di lapangan", "Peserta sudah melunasi atau sudah ditangani",
  "Peserta tidak mampu, lebih tepat dirujuk cek PBI", "Ada penjelasan lain yang wajar, misalnya
  sakit atau kerja musiman", "Lainnya". Keputusan hanya tersimpan selama sesi dan **tidak mengubah
  rute** (belum ada basis data).
- **Draf pesan:** dari lapisan AI bila aktif, atau dari template bila tidak (lihat bagian 3).

### c. Kebijakan
Uji lonjakan hari ke-45: rawat inap terjadwal dibanding plasebo IGD, untuk unit kebijakan. Halaman
menjaga dua aturan tafsir: ukuran ujinya **lompatan**, bukan kelebihan saja; dan lompatan bukan
jumlah rawat inap yang ditunda (perkiraannya adalah kelebihan di hari 46-60).

### d. Keadilan ("Panel keadilan dan bukti")
- Menjawab pertanyaan "apakah sistem berat sebelah?": kelompok mana (kelas, kemiskinan wilayah,
  usia, jenis kelamin) paling sering masuk jalur verifikasi dibanding rata-rata.
- Dihitung **tanpa label**, jadi mencakup semua peserta di jalur, bukan hanya yang jujur.
- Dua ukuran: seluruh jalur verifikasi, dan yang diperiksa (min(k, isi jalur) dengan skor
  tertinggi, k = 1%).
- Ambang 2x dari pra-registrasi. Ambang "perlu perhatian" (≥ 1,25x) dan "jarang diperiksa"
  (≤ 0,8x) ditambahkan sesudah hasil dilihat dan tidak dikoreksi untuk pengujian berganda.
- Halaman ini satu-satunya yang juga membaca `bukti/hasil/skor_verifikasi.csv` dan
  `beban_strata.csv`, lalu mencocokkannya baris demi baris; bila beda, halaman memberi peringatan.

### Pengaman di data aplikasi
`siapkan_app.py` menolak menyimpan bila: angka utama beda dari angka proposal; ada peserta DTSEN
1-5 di jalur verifikasi; kolom kunci jawaban muncul di luar `evaluasi_label.parquet`; atau ukuran
lebih dari 20 MB. `evaluasi_label.parquet` disiapkan untuk halaman Evaluasi, tetapi **halaman
Evaluasi belum ada** di aplikasi; keempat halaman tidak membaca label.

## 2. API triase (`api.py`)

- FastAPI. Jalankan: `uvicorn api:app --port 8000`, lalu buka `/docs`.
- Satu endpoint: `POST /triase` untuk **1-50 peserta** PBPU/BP mandiri, dengan riwayat status,
  pembayaran, klaim, dan DTSEN (paling banyak 5.000 baris per tabel). Tanggal potong tetap
  31 Des 2025.
- **Tidak ada logika baru:** memakai fungsi `cek_sinyal.py` dan skor dari
  `bukti/skor_verifikasi.py`. Hasil per peserta sama dengan `app_data/daftar_kerja.parquet`.
- Jawaban per peserta: rute, alasan, skor urutan (hanya di rute verifikasi; deskripsi API sendiri
  menulis bahwa skor ini "belum terbukti", AUC 0,40 di dalam jalur), dan fitur. Peserta di luar
  cakupan (PPU, PBI, Pemda) dilaporkan terpisah.
- Pengaman: kolom di luar skema ditolak (termasuk kolom label). DTSEN 1-5 dicek di setiap
  permintaan; bila ada yang masuk rute verifikasi, API menjawab galat 500 tanpa hasil. API tidak
  memakai AI.

## 3. Lapisan AI draf pesan (`llm.py`, pekerjaan Z09)

Prinsip: **AI hanya menulis ulang kata-kata template; petugas yang memutuskan.** Aturan dijaga oleh
kode, bukan hanya oleh permintaan di prompt. Jawaban AI yang melanggar dibuang, lalu template dipakai.

Aturan yang dijaga kode:
- Jalur tidak pernah berubah. AI diminta menyalin kode jalur; jawaban dibuang bila beda.
- Tanpa kata "curang" atau tuduhan terselubung (sengaja, pura-pura, menghindar, melanggar).
- Tanpa ancaman atau tekanan (denda, sanksi, hukuman, pelaporan, pemblokiran, "kesempatan terakhir").
- Wajib menyebut opsi yang sesuai jalur dengan nama persis: "REHAB 3.0", "autodebet", atau "PBI".
  "REHAB" tanpa "3.0" ditolak.
- Angka hanya yang ada di data peserta (jumlah bulan, nominal) ditambah 165 (Care Center).
- Tanpa skor, persen, peluang, model, AI, DTSEN, atau istilah internal di pesan ke peserta.
- AI tidak pernah menerima nomor peserta; pesan memakai `{ID}` yang diganti setelahnya.
- Tidak boleh menaikkan kepastian di atas template (ditambahkan 30 Okt 2026 setelah uji dengan model
  asli): template sengaja berhati-hati ("Keluarga Anda **mungkin** memenuhi syarat"); kata seperti
  "pasti", "dipastikan", "besar kemungkinan", "kemungkinan besar" ditolak.
- Rute verifikasi **tidak menghasilkan pesan ke peserta**, hanya catatan untuk petugas, jadi AI tidak
  dipanggil untuk rute itu.
- Ringkasan untuk petugas di rute PBI wajib menyebut "kelayakan PBI" (30 Okt 2026).
- Spasi yang rusak di jawaban AI dirapikan otomatis dan jumlah perbaikannya dicatat.

Cadangan ke template bila: kunci API kosong, API mati, timeout, JSON rusak, pelanggaran aturan,
kuota habis, batas harian tercapai (bawaan 300 panggilan per hari per proses), atau saklar
`TEPAT_AI=off`. Fungsi `susun()` tidak pernah melempar galat.

Penyedia: Anthropic (Messages API) atau Google Gemini (ada tier gratis). Pemilihan otomatis:
Anthropic bila kuncinya ada, selain itu Gemini; tanpa kunci, template. Model bawaan Gemini dipilih
dari uji panggilan nyata 29 Okt 2026 (`gemini-3.1-flash-lite`: 6/6 sukses, 2,7-6,7 detik, kecuali
panggilan pertama tiap sesi sekitar 25-31 detik). Batas tunggu per panggilan 45 detik.

Data yang keluar ke penyedia AI hanya: jalur, skor (hanya untuk daftar peringatan dini, dibulatkan),
alasan, fakta angka (bulan
tunggakan, nominal tunggakan, iuran bulanan, sudah autodebet atau belum), dan draf template dengan
nomor peserta diganti `{ID}`.

**Uji:** `uji_llm.py`, 37 uji, lulus 37/37 saat dicek 30 Okt 2026. Tanpa kunci API dan tanpa
internet (AI diganti klien tiruan, HTTP diuji lewat server lokal). Yang **tidak** bisa diuji di sana:
mutu bahasa jawaban model sungguhan; itu harus dilihat petugas.

### Contoh isi template (rute PBI)

"Yth. peserta JKN (nomor peserta {id}), iuran JKN Anda tercatat belum dibayar selama {n} bulan.
Keluarga Anda mungkin memenuhi syarat sebagai peserta yang iurannya dibayar pemerintah (PBI).
Silakan datang ke kantor desa atau kelurahan, atau Dinas Sosial setempat, untuk pengecekan data.
Petugas BPJS Kesehatan dapat membantu proses rujukannya. Informasi lebih lanjut: aplikasi Mobile
JKN atau BPJS Kesehatan Care Center 165."

### Catatan petugas untuk rute verifikasi (bukan untuk dikirim)

Berisi pola yang terlihat, lalu tiga langkah: cocokkan tanggal aktif kembali dengan tanggal klaim;
cek penjelasan lain yang wajar (jatuh miskin karena sakit, penyakit kronis, pembayar musiman; bila
klaimnya rawat inap IGD di hari pelunasan, kemungkinan karena darurat); bila peserta ternyata tidak
mampu, ubah tindak lanjut menjadi rujukan cek PBI. Ditutup dengan: jangan memakai kata yang menuduh.

## 4. Menjalankan seluruh pipeline

```
pip install -r requirements.txt
python generate_data.py --n 20000 --seed 2026 --out data   # ±20 detik
python cek_sinyal.py --data data --out hasil                # ±5 detik
python early_warning.py --data data --out hasil             # ±15 detik
python uji_stabilitas.py --seeds 2026 1 2 3 4 --out hasil   # ±3 menit
python daya_uji_bunching.py --data data --out hasil         # ±1 menit
python siapkan_app.py --data data --out app_data            # ±20 detik
streamlit run app.py
```

Sebelum commit yang mengubah skrip atau paket, jalankan ulang ke `hasil_cek/` lalu
`python cocokkan_angka.py --data data --hasil hasil_cek` (58 pemeriksaan; berhenti dengan kode 1
bila ada yang beda). Butuh Python 3.10+, pandas ≥ 2.2, scikit-learn ≥ 1.4 (versi 1.3 menggeser
angka peringatan dini), streamlit ≥ 1.66.
