# Evaluasi TEPAT: pra-registrasi, target T1-T8, dan hasilnya

Kondisi per 30 Oktober 2026 (commit `f194054`). Sumber utama: `bukti/preregistration.md`,
`bukti/hasil/ringkasan_n06.md`, `bukti/hasil/sensitivitas_keadilan.txt`.

## Apa itu pra-registrasi di proyek ini

Pra-registrasi adalah dokumen yang menetapkan target dan cara menilai **sebelum** hasil dilihat.
Jam push di GitHub menjadi bukti bahwa target tidak disesuaikan dengan hasil. Susunannya mengikuti
template di `healthkathon-eval-kit` milik panitia (github.com/Luche/healthkathon-eval-kit).

Riwayat:
- **24 Okt 2026, commit `bfb3c54` (Zenda):** target T1-T8 dan hipotesis penilai. Bagian lain masih
  template kosong, dan `bukti/kasus_jujur.py` di commit itu kosong.
- **28 Okt 2026, commit `5b7b632`:** bagian 0-3 dan 5-8 dilengkapi; kode kasus jujur, skor urutan,
  dan penilai dikunci. Target T1-T8 dan hipotesis tidak berubah. Aturan IGD ditetapkan Zul.
- **28 Okt 2026, commit `601a1d8`:** menambah bagian 3a, cara skor dipakai (min(k, isi jalur),
  pemecah seri). Ditambahkan sebelum penilaian berlabel apa pun.
- **28 Okt 2026, 17.50-18.10 WITA:** penilaian T1-T8 dijalankan (hasil di commit `227984b`).

### Keterbukaan yang ditulis sendiri oleh tim (bagian 0 pra-registrasi)

- Aturan, generator, kasus jujur, skor, dan penilai ditulis Zul bersama asisten AI Claude.
  Penilaian dijalankan Claude dalam sesi bersama Zul, **bukan oleh Zenda**. Penulis detektor dan
  penilai **tidak independen**.
- Penulis generator sama dengan penulis aturan dan mengenal aturannya saat menulis generator.
- Dua rancangan kasus jujur diubah setelah cek perilaku generator (tanpa menjalankan triase).
- Hasil profil `sampel2024` (presisi 89,4%, 76 tidak mampu di jalur) sudah terlihat sebelum
  pra-registrasi dilengkapi; profil itu tidak dipakai untuk target.

## Kondisi uji

- Data dasar: `generate_data.py --n 20000 --seed 2026` (profil `asumsi`).
- Kasus jujur: 2.500 orang, 500 per jenis (lihat sumber 03).
- Dial konsentrasi: bayar-saat-butuh hanya di W01-W05.
- Kapasitas k jalur verifikasi: 0,5%, 1%, 2% (100, 200, 400 dari 20.000). **Angka utama 1%.**
- Prevalensi bayar-saat-butuh di generator 10% (karangan). Untuk T1, prevalensi diturunkan lewat
  undian acak (200 undian, seed 7).

## Target dan hasil

| Kode | Yang diukur | Target | Hasil | Status |
|---|---|---|---|---|
| T1 | Presisi jalur verifikasi pada k 1%, prevalensi 1%, data dasar + kasus jujur | batas bawah selang 95% ≥ 50% | 60,0% (55,7-63,8%); diperiksa 125 orang dari kapasitas 202 karena isi jalur lebih kecil dari k. Cara bawaan eval-kit: 38,1% (32,2-44,1%) | **Lulus, hanya dengan aturan bagian 3a.** Dengan cara bawaan eval-kit, meleset |
| T2 | Presisi jalur verifikasi pada k 1%, data dasar (prevalensi 10%) | batas bawah IK95% per wilayah ≥ 80% | 98,0% (96,0-99,5%), 196 dari 200 | **Lulus** |
| T3 | Porsi kasus jujur yang masuk jalur verifikasi | ≤ 5% per jenis; jatuh_miskin_sakit ≤ 1% | jatuh_miskin_sakit 32 dari 500 (**6,4%**); tiga jenis jujur lain 0 | **Meleset** |
| T4 | Beban peserta jujur per kelompok (kelas, kemiskinan wilayah, usia, jenis kelamin) | tidak ada kelompok > 2x rata-rata; dinilai bila ≥ 30 orang jujur di jalur | hanya 18 orang jujur di jalur | **Terlalu sedikit untuk dinilai** (rasio tertinggi, sekadar info: kelas 3, 1,64x) |
| T5 | Recall jenis yang ditahan (baru_berhenti_cepat) | tanpa ambang | 35 dari 500 (7,0%) | Lemah |
| T6 | Lift peringatan dini pada k 1%, peserta yang belum pernah nonaktif | ≥ 3x | 8,6x (presisi 52,3% vs dasar 6,0%), per bulan 8,0-9,3x | **Lulus** (sudah diketahui sebelumnya) |
| T7 | Ablasi: aturan sederhana vs aturan + model | tanpa ambang | Semua peserta: aturan 94,8% vs model 93,3% (selisih −1,5 poin, p 0,03). Belum pernah nonaktif: aturan 5,1% (= acak) vs model 51,7% (+46,6 poin, p < 0,01) | Model hanya berguna untuk yang belum pernah nonaktif |
| T8 | Presisi pada data konsentrasi | tanpa ambang | 98,0% (IK95% per wilayah 92,0-99,5%, lebih lebar dari T2); W01-W05 100%; 4 wilayah lain masing-masing 1 orang jujur | Isi jalur tidak berubah; hanya selangnya melebar |

### T1 di lima tingkat prevalensi (k 1%, 200 undian)

| Prevalensi | Diperiksa / k | Presisi (selang 95%) | Cara bawaan eval-kit | Lift |
|---|---|---|---|---|
| 0,5% | 87 / 201 | 42,5% (35,9-48,5) | 18,9% | 85x |
| 1% | 125 / 202 | 60,0% (55,7-63,8) | 38,1% | 60x |
| 2% | 201 / 204 | 75,1% (72,8-76,5) | 74,0% | 38x |
| 5% | 211 / 211 | 82,9% (82,5-84,4) | 82,9% | 17x |
| 10% | 223 / 223 | 93,3% (92,8-93,3) | 93,3% | 9x |

Bacaan: makin jarang perilaku bayar-saat-butuh di populasi, makin turun presisinya. Kalau prevalensi
nyata di bawah 1%, sekitar separuh atau lebih orang di daftar periksa adalah orang jujur. Ini alasan
kuat kenapa jalur ini harus tetap "daftar periksa", bukan dasar sanksi.

### Soal T1 "lulus dengan syarat"

Eval-kit bawaan mengisi kursi kosong dengan peserta di luar jalur. Bagian 3a pra-registrasi
menetapkan bahwa kursi kosong tidak diisi, sehingga presisi dihitung atas min(k, isi jalur).
Bagian 3a ditambahkan 28 Okt 2026 **sebelum penilaian berlabel**, dan jamnya tercatat (commit
`601a1d8` 17.46 WITA, di-push 17.48 WITA menurut `ringkasan_n06.md`; penilaian mulai 17.50 WITA).
Jaraknya hanya beberapa menit. Tetap saja, juri bisa membaca ini sebagai mengubah
aturan main menjelang penilaian. Jawaban yang jujur: kedua angka dilaporkan berdampingan, dan
dengan cara bawaan T1 meleset.

## Kenapa T3 meleset

Peserta `jatuh_miskin_sakit` yang ikut masuk jalur tertangkap lewat **rawat jalan lanjutan ≥ Rp1
juta** sesudah aktif lagi, bukan lewat rawat inap IGD. Orang yang jatuh sakit berat lalu bolak-balik
berobat terlihat persis seperti pola "aktif lagi, lalu klaim besar". Ini kelemahan nyata aturan,
bukan kebetulan. Sesuai pra-registrasi, aturan tidak diubah untuk menutupinya; kelemahan ini wajib
ditulis di slide bukti bagian titik lemah.

## Aturan asli (A) vs tanpa IGD (B), dan hipotesis Zenda

| | A (dipakai) | B (tanpa IGD) |
|---|---|---|
| Jalur verifikasi, data dasar | 909 | 683 |
| Presisi / recall, data dasar | 98,0% / 44,3% | 98,8% / 33,5% |
| Peserta jujur di jalur, data dasar | 18 | 8 |
| jatuh_miskin_sakit di jalur | 32 (6,4%) | 32 (6,4%) |
| baru_berhenti_cepat di jalur | 35 (7,0%) | 35 (7,0%) |

**Hipotesis penilai (ditulis Zenda, 24 Okt, sebelum hasil):**
- jumlah orang jujur yang ikut masuk jalur verifikasi akan: **bertambah**;
- ketepatan sasaran: jalur periksa akan menjadi tepat sasaran;
- alasan: wawancara petugas BPJS bisa menggali alasan peserta tidak rutin membayar sebelum klaim.

**Hasil:** hipotesis "orang jujur bertambah" **tidak terbukti**. Membuang IGD justru menurunkan
orang jujur di data dasar dari 18 ke 8, dan tidak mengubah apa pun di kasus jujur. Tetapi membuang
IGD juga menurunkan recall dari 44,3% ke 33,5%. Keputusan tetap memakai A, sesuai yang dikunci
sebelum penilaian.

## Temuan eksploratif (tidak dipra-registrasi, jangan dipakai sebagai uji)

1. **Skor urutan menaruh orang jujur di atas.** Di dalam jalur (data dasar + kasus jujur, 976 orang,
   50 jujur), AUC skor untuk membedakan curang dari jujur **0,40**, di bawah acak. Rata-rata skor
   jatuh_miskin_sakit 1,79, bayar-saat-butuh 1,44. Di T2, presisi 200 teratas (98,0%) sama dengan
   presisi seluruh jalur (98,0%): skor tidak menambah apa-apa. Rumus tidak diubah setelah melihat ini.
   Implikasinya: skor ini belum layak dijual sebagai "prioritas yang lebih pintar".
2. **Beban tanpa label** (`beban_strata.csv`, seluruh jalur): usia > 55 tahun masuk jalur 1,66x
   rata-rata, usia ≤ 35 tahun 0,6x. Kelas, kemiskinan wilayah, dan jenis kelamin 0,9-1,1x.
3. **Bug eval-kit:** kartu bukti berhenti dengan ValueError bila tidak ada kelompok jujur (semua 40
   wilayah data dasar punya peserta bayar-saat-butuh). Kartu data dasar memakai peserta sebagai
   kelompok (`bukti_dasar_per_peserta.html`).

## Analisis sensitivitas keadilan (`bukti/sensitivitas_keadilan.py`, 29 Okt 2026)

Pertanyaan: apakah kemiringan di halaman Keadilan berasal dari asumsi data buatan? Empat varian
(profil asumsi/sampel2024, masing-masing asli dan "usia netral") × 5 seed, tanpa label.

Temuan:
- **Usia.** Di profil asumsi, usia > 55 masuk jalur 1,68x; dengan usia netral 1,56x (masih tinggi,
  karena di profil asumsi segmen bayar-saat-butuh dibuat lebih tua: rata-rata 48 vs 42 tahun). Di
  profil sampel2024, 1,22x menjadi 0,97x dengan usia netral. Kesimpulan: kemiringan usia sebagian
  besar berasal dari asumsi tim (faktor usia pada laju layanan dan usia segmen), bukan dari aturan.
- **Kelas, di daftar yang diperiksa (k 1%).** Kelas 3 diperiksa 1,40x rata-rata di profil asumsi
  (porsi 47,6% di populasi → 66,7% di yang diperiksa); kelas 1 hanya 0,51x. Bila penyebut iuran di
  skor disamakan untuk semua orang, porsinya kembali normal (47,6% → 47,8%). **Kemiringan kelas
  berasal dari rumus skor**: iuran kelas 3 paling kecil, jadi rasio klaim/iuran-nya paling besar.
  Artinya skor yang dikunci secara struktural mendahulukan peserta kelas 3, yang cenderung lebih
  miskin. Ini kontradiksi dengan semangat "tanda miskin selalu menang" dan perlu diakui.
- **Kemiskinan wilayah (sampel2024):** wilayah kemiskinan rendah diperiksa 1,22-1,24x, wilayah
  kemiskinan tinggi 0,83x.
- Tidak ada kelompok yang melewati ambang 2x di varian mana pun.

Halaman Keadilan di aplikasi memakai ambang 2x dari pra-registrasi. Ambang "perlu perhatian"
(≥ 1,25x dengan batas bawah selang di atas 1x) dan "jarang diperiksa" (≤ 0,8x) **ditambahkan sesudah
hasil dilihat**, bukan pra-registrasi, dan tidak dikoreksi untuk pengujian berganda. Ini ditulis
terbuka di kode halaman.

## Yang belum dijalankan

- **N11, review pakar buta:** lembar untuk pakar sudah dibuat 28 Okt 2026 (20 kasus skor teratas +
  20 kasus acak, seed 0) dan sidik jari SHA-256 dicatat di `bukti/hasil/n11_sha256.txt` sebelum
  dikirim. File kunci disimpan di luar repo. Penilai `bukti/nilai_n11.py` sudah siap. **Hasil dari
  pakar belum ada di repo** per 30 Okt 2026. Dilaporkan tanpa ambang bila dijalankan.
- Plasebo data tanpa kecurangan untuk jalur verifikasi (butuh generator ketiga; tidak cukup waktu).
- Uji permutasi label dan pemindaian kebocoran (alasan di pra-registrasi bagian 7).
- Daftar centang di bagian 7 pra-registrasi masih kosong walaupun uji-ujinya sudah dijalankan
  (administratif, belum diperbarui).
