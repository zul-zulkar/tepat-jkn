# Riwayat proyek, pembagian peran, dan status pekerjaan

Kondisi per 30 Oktober 2026 (commit `f194054`, cabang `main`). Linimasa disusun dari riwayat commit
Git. Jam commit memakai zona waktu laptop pembuatnya (WIB +07, WITA +08, atau UTC).

## Pembagian peran yang tercatat

| Orang | Peran yang tercatat di repo |
|---|---|
| Muhammad Zulkarnain (Zul) | Penulis aturan triase, generator data, model peringatan dini, aplikasi, API, lapisan AI. Menetapkan aturan IGD (28 Okt). Hampir semua commit. Bekerja bersama asisten AI Claude. |
| Zenda Oka Briantiko | Mengunggah versi pertama pra-registrasi (commit `bfb3c54`, 24 Okt 2026) dan menulis hipotesis penilai soal IGD. Satu commit di repo. |
| Claude (asisten AI, Anthropic) | Menulis kasus jujur, skor urutan, dan penilai; menjalankan penilaian T1-T8 di sesi bersama Zul (pra-registrasi bagian 8). |

Catatan: peran Zenda di luar repo (misalnya deck, naskah video, riset regulasi) tidak tercatat di
Git, jadi tidak tercermin di tabel ini.

## Linimasa

| Tanggal | Commit | Kejadian |
|---|---|---|
| 7 Okt 2026 | `ee105e1`, `33c6162` | Laporan ringkasan awal; daftar anggota tim di README. |
| 10 Okt | `e53b6d2` | Generator data versi yang menjadi dasar semua angka proposal. |
| 11 Okt | `e06f918`, `9c8613c`, `091dcdd` | Model peringatan dini dan keluarannya; uji stabilitas 5 seed. `091dcdd` = versi aturan triase yang diuji di pra-registrasi. |
| 23 Okt | `1e26db0`, `bff0d1d`, `84c654c` | Pemeriksa angka kanonik (`cocokkan_angka.py`); `siapkan_app.py` dan `app_data/`; README direvisi. |
| 24 Okt | `ddabd4b` s.d. `4fc4fd3` | Aplikasi Streamlit (Daftar kerja, Profil); hemat memori; satu tindakan per peserta; nama "Berisiko menunggak"; tanda bukti hanya IGD; palet deck, logo, ikon. |
| 24 Okt | `bfb3c54` (Zenda) | Pra-registrasi versi pertama: target T1-T8 dan hipotesis IGD. |
| 26 Okt | `5298f7f` | Halaman Kebijakan (uji lonjakan vs plasebo IGD). |
| 28 Okt | `fd02b41` | Kalibrasi ke Data Sampel BPJS 2024; profil `sampel2024`. |
| 28 Okt | `5b7b632`, `601a1d8` | Pra-registrasi dilengkapi dan kode uji dikunci; bagian 3a (cara pakai skor). |
| 28 Okt | `227984b` | Skrip dan hasil penilaian T1-T8 (N06). |
| 29 Okt | `b22d9b3` | API (`api.py`) dan persiapan review pakar buta N11. |
| 29 Okt | `eedc8fa`, `baeec58`, `d1d2647` | Halaman Keadilan; agregat usia × rawat inap di target kalibrasi; analisis sensitivitas keadilan. |
| 30 Okt | `bcb1ff6` | Lapisan AI draf pesan dengan cadangan template. |
| 30 Okt | `062392d`, `11b4a8b`, `e31b52b`, `f194054` | Penolakan kata penguat kepastian; "kelayakan PBI" wajib di ringkasan rute PBI; perbaikan spasi. |

## Kode pekerjaan yang muncul di repo

| Kode | Isi | Status per 30 Okt 2026 |
|---|---|---|
| N03 | Kasus jujur dan jenis yang ditahan (T3, T5) | Selesai; T3 meleset |
| N04 | Dial konsentrasi (T8) | Selesai |
| N05 | Skor urutan jalur verifikasi | Selesai; skor tidak terbukti membantu (eksploratif) |
| N06 | Penilaian T1-T8 | Selesai 28 Okt |
| N11 | Review pakar buta | **Tertunda**: lembar dan sidik jari siap, hasil pakar belum ada |
| Z09 | Lapisan AI draf pesan | Selesai; 37/37 uji lulus |

Kode lain (N01, N02, dan seterusnya) tidak muncul di repo; daftar pekerjaan lengkapnya kemungkinan
ada di luar repo.

## Kondisi teknis per 30 Okt 2026

- Angka kanonik: dijalankan ulang 30 Okt 2026 di Python 3.13 dengan paket terbaru dari
  `requirements.txt`; `cocokkan_angka.py` **58/58 cocok**.
- Uji lapisan AI: `uji_llm.py` **37/37 lulus**.
- Ukuran `app_data/`: 3,61 MB dari batas 20 MB; manifest menyatakan cek kanonik lolos.

## Dokumen yang sudah usang atau belum sinkron

Ini kondisi nyata repo yang perlu dibereskan sebelum dinilai juri:

1. **README menyebut aplikasi punya "dua halaman"**, padahal sekarang ada empat (Daftar kerja,
   Profil peserta, Kebijakan, Keadilan).
2. **README menulis draf pesan "nanti menjadi jalur cadangan lapisan AI"**, padahal lapisan AI
   (`llm.py`) sudah ada sejak 30 Okt.
3. **Bagian "Isi folder" di README** belum memuat `api.py`, `llm.py`, `uji_llm.py`,
   `requirements-api.txt`, dan halaman Kebijakan/Keadilan.
4. **README belum memuat hasil evaluasi T1-T8**, termasuk T3 yang meleset dan temuan skor AUC 0,40.
   Hasil itu hanya ada di `bukti/hasil/ringkasan_n06.md`.
5. **README menyebut `evaluasi_label.parquet` untuk halaman Evaluasi**, padahal halaman Evaluasi tidak
   ada di aplikasi.
6. **Daftar centang bagian 7 pra-registrasi** masih kosong walaupun uji-ujinya sudah dijalankan.

## Yang masih bisa dikerjakan (dari keterbatasan dan catatan di repo)

- Hasil review pakar buta N11.
- Tagihan per KK sebagai lapisan terpisah.
- Tanda awal jatuh miskin di generator (autodebet gagal, turun kelas, bayar mepet tanggal 10).
- Metode uji lonjakan dengan batasan integrasi untuk data asli.
- Halaman Evaluasi (bila memang direncanakan) atau hapus rujukannya.
- Sinkronkan README dengan kondisi sekarang.
