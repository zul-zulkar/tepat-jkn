# Keterbatasan, risiko, dan latihan pertanyaan juri

Kondisi per 30 Oktober 2026 (commit `f194054`). Bagian 1-3 berisi fakta dari repo. Bagian 4 berisi
**saran jawaban** untuk latihan presentasi; saran ini disusun dari fakta di repo, bukan pernyataan
resmi tim.

## 1. Keterbatasan yang ditulis tim sendiri (README)

1. **Berputar di data sendiri.** Pola ditanam di data buatan, lalu ditemukan lagi. Pembuktian
   sebenarnya butuh data BPJS.
2. **Masih per orang.** Tagihan PBPU/BP dihitung bersama untuk satu KK (Peraturan BPJS 5/2018
   Ps. 12 ayat 4; Ps. 14 ayat 4), sedangkan penghentian jaminan dan denda berlaku per peserta
   (Perpres 59/2024 Ps. 42 ayat 1 dan 5). Generator baru menghitung per peserta. Tim tidak menganggap
   satu KK sama dengan satu nomor VA.
3. **Uji lonjakan masih sederhana** (polinomial, rentang hari tetap). Untuk data asli perlu metode
   dengan batasan integrasi (Chetty dkk. 2011; Kleven 2016).
4. **Data DTSEN** dianggap bisa didapat lewat kerja sama data resmi antarlembaga.
5. **Recall jalur verifikasi rendah** (44,3%): sebagian peserta belum perlu berobat selama masa
   pengamatan.
6. **Belum mengukur dampak tindakan.** Peringatan dini menebak siapa yang *akan* menunggak, bukan
   siapa yang *bisa dicegah* menunggak lewat pengingat. Untuk itu butuh uji coba terkontrol per jalur.
7. **Peringatan dini belum punya tanda awal orang jatuh miskin** (autodebet gagal, turun kelas, bayar
   makin mepet tanggal 10). Di generator, orang yang rutin bayar selalu bayar tanggal 1-10.

## 2. Kelemahan dari hasil evaluasi (bukti/)

1. **T3 meleset.** 6,4% orang jujur jenis "jatuh miskin karena sakit" masuk jalur verifikasi (target
   ≤ 1%). Mereka tertangkap lewat rawat jalan lanjutan ≥ Rp1 juta sesudah aktif lagi.
2. **Di data yang lebih realistis (profil sampel2024)**, orang tidak mampu di jalur verifikasi naik
   dari 18 ke 76, presisi jalur verifikasi turun dari 98% ke 89%, presisi jalur pengingat turun ke
   58,6%.
3. **Presisi sangat bergantung pada prevalensi.** Pada prevalensi 1%, presisi 60% (hanya dengan aturan
   pra-registrasi 3a); pada 0,5%, 42,5%. Prevalensi nyata perilaku bayar-saat-butuh tidak diketahui.
4. **T1 lulus dengan syarat.** Dengan cara bawaan eval-kit, T1 meleset (38,1%).
5. **Skor urutan belum terbukti berguna.** Di dalam jalur, AUC 0,40 (di bawah acak); tidak menambah
   presisi di T2.
6. **Skor urutan mendahulukan kelas 3** (1,40x di daftar yang diperiksa) karena penyebut iuran.
7. **Model peringatan dini tidak mengalahkan aturan sederhana** untuk semua peserta pada kapasitas
   kecil; hanya berguna untuk peserta yang belum pernah menunggak.
8. **Profil asumsi jauh dari data nyata** (hanya 7 dari 34 ukuran dalam selisih 20% dari Data Sampel
   BPJS 2024), padahal semua angka proposal memakai profil ini.
9. **Tidak independen.** Penulis aturan = penulis generator = penulis kasus jujur. Penilaian
   dijalankan asisten AI di sesi bersama Zul. Kasus jujur adalah uji kesulitan, bukan uji buta.
10. **Review pakar buta (N11) belum ada hasilnya.**

## 3. Pertanyaan yang belum terjawab (akan dicek ke BPJS)

1. Nomor VA diberikan per peserta atau per KK, dan apakah nomornya tetap? Peraturan BPJS 5/2018
   memakai "nomor Virtual Account" dan "VA Peserta"; Peraturan BPJS 6/2018 Ps. 23 ayat 2 memakai
   "VA keluarga".
2. Apakah anggota KK baru aktif lagi setelah seluruh tunggakan satu KK lunas?
3. Berapa bagian iuran K3 yang ditagih untuk bulan tertunggak? (Perpres 64/2020 Ps. 34 ayat 4)
4. Apa dasar hukum masa tunggu 14 hari untuk peserta baru?
5. Apakah sudah ada penetapan iuran setelah 1 Juli 2025? (Perpres 59/2024 Ps. 103B ayat 8)

Di luar itu, angka resmi kapasitas petugas per bulan juga belum ada, sehingga k masih asumsi.
REHAB (cicilan tunggakan satu keluarga) diketahui tim dari berita; tim tidak menemukannya di Perpres
atau Peraturan BPJS yang dibaca, sehingga diperlakukan sebagai praktik administrasi BPJS.

## 4. Latihan pertanyaan juri dan saran jawaban

**"Datanya sintetis. Apa buktinya ini bekerja di dunia nyata?"**
Belum ada buktinya, dan tim tidak mengklaim itu. Angka di data sintetis hanya membuktikan kode
bekerja. Yang sudah dilakukan untuk mendekati kenyataan: kalibrasi ke angka agregat Data Sampel BPJS
2024 (26 dari 33 ukuran dalam selisih 20%), dan hasilnya dilaporkan apa adanya, termasuk yang
memburuk. Langkah berikut yang diusulkan: menjalankan pipeline di data BPJS di lingkungan BPJS, lalu
uji coba terkontrol per jalur.

**"Bukankah ini menuduh peserta curang?"**
Tidak. Melunasi tunggakan sebelum berobat itu sah (Perpres 59/2024 Ps. 42 ayat 3). TEPAT hanya
memberi daftar periksa dan alasan; petugas yang memutuskan. Rute verifikasi tidak mengirim pesan ke
peserta. Skor tidak mengubah status atau manfaat. Kata "curang" dilarang di semua pesan, dan aturan
ini dijaga oleh kode.

**"Bagaimana Anda melindungi orang miskin?"**
Peserta DTSEN desil 1-5 tidak pernah masuk jalur verifikasi; ini diperiksa kode di pipeline, di
pembuatan data aplikasi, dan di setiap permintaan API. Untuk orang yang jatuh miskin tetapi DTSEN-nya
belum diperbarui, aturan "rutin lalu berhenti" mengarahkan mereka ke cek PBI (603 orang di data
dasar). Tetapi harus jujur: pengaman ini tidak sempurna. 18 orang tidak mampu masih masuk jalur
verifikasi di profil asumsi, dan 76 di profil yang lebih realistis.

**"Target mana yang gagal?"**
T3: orang jujur yang jatuh miskin karena sakit masuk jalur verifikasi 6,4%, target ≤ 1%. Aturan tidak
diubah untuk menutupinya, sesuai pra-registrasi. T1 hanya lulus dengan aturan pemakaian skor yang
ditambahkan sebelum penilaian; dengan cara bawaan eval-kit, meleset.

**"Kenapa pakai model kalau aturan sederhana sama bagusnya?"**
Untuk semua peserta, memang tidak lebih bagus, dan tim melaporkannya (T7). Model hanya bernilai untuk
peserta yang belum pernah menunggak, di mana aturan sederhana sama dengan menebak acak: presisi 1%
teratas 52% vs tingkat dasar 6% (lift 8,6x). Usulannya dua jalur: yang pernah menunggak diurutkan
dengan aturan, yang belum pernah diurutkan dengan model.

**"Uji lonjakan hari ke-45 itu apa gunanya?"**
Untuk kebijakan, bukan untuk menindak orang. Kalau rawat inap terjadwal menumpuk tepat sesudah hari
ke-45 sementara IGD tidak, itu tanda aturan denda 45 hari sedang diakali. Di data sintetis lompatannya
227 (IK95% 185-274) dan IGD 4 (mencakup 0). Dengan sekitar 1.200 kasus, uji butuh minimal sekitar 54
kasus tertunda untuk terdeteksi dengan daya 80%; data nasional jauh lebih besar, jadi ambangnya turun.

**"Berapa penghematan untuk BPJS?"**
Angka di repo hanya perkiraan denda yang lolos di data sintetis: Rp745 juta (rentang 5 seed Rp592-989
juta), memakai biaya sintetis, bukan paket INA-CBG. Ini **tidak boleh** dibaca sebagai proyeksi
nasional. Tim tidak menghitung "rupiah recall" karena kerugian per orang untuk tunggakan belum
didefinisikan.

**"Apakah sistem ini adil antar kelompok?"**
Tidak ada kelompok yang melewati 2x rata-rata. Tetapi ada kemiringan: usia > 55 tahun masuk jalur
1,66x (sebagian besar dari asumsi usia di generator), dan di daftar yang diperiksa kelas 3 1,40x
karena skor membagi klaim dengan iuran. Keduanya ditampilkan di halaman Keadilan.

**"AI-nya bisa salah tulis atau mengancam peserta?"**
AI hanya menulis ulang template. Kode membuang jawaban yang mengubah jalur, menuduh, mengancam,
mengarang angka, menyebut skor, atau menaikkan kepastian; lalu template dipakai. Petugas tetap
menyunting sebelum mengirim. Mutu bahasa model sungguhan belum diuji otomatis.

**"Data pribadi peserta dikirim ke AI?"**
Nomor peserta tidak pernah dikirim. Yang dikirim hanya jalur, alasan, angka tunggakan dan iuran, dan
draf template. Untuk penerapan nyata, flowchart tim menulis data anonim diproses di lingkungan BPJS
(UU PDP).

**"Siapa yang menilai? Bukankah Anda menilai diri sendiri?"**
Ya, dan itu ditulis di pra-registrasi bagian 0. Penulis aturan, generator, dan penilai tidak
independen. Pengimbangnya: target dikunci dan di-push sebelum penilaian, kegagalan dilaporkan, dan
review pakar buta (N11) disiapkan dengan sidik jari SHA-256 yang dicatat sebelum lembar dikirim.
