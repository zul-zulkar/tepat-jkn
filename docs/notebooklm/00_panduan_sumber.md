# Panduan sumber NotebookLM: proyek TEPAT

Dokumen ini daftar isi untuk kumpulan sumber tentang proyek TEPAT (Triase Peserta Tertunggak).
Sumber-sumber ini dibuat supaya Zenda Oka Briantiko bisa bertanya tentang kondisi proyek lewat
NotebookLM.

- **Kondisi per:** 30 Oktober 2026, commit `f194054` di repo `zul-zulkar/tepat-jkn`.
- **Cara dibuat:** dirangkum dari kode, README, pra-registrasi, dan berkas hasil di repo. Angka
  kanonik sudah dijalankan ulang pada 30 Okt 2026 dan cocok 58 dari 58 (`cocokkan_angka.py`);
  uji lapisan AI lulus 37 dari 37 (`uji_llm.py`).
- **Batas:** sumber ini hanya tahu isi repo. Isi deck proposal, naskah video, tenggat lomba, dan
  alamat aplikasi yang sudah di-deploy **tidak tercatat di repo**, jadi tidak ada di sini. Kalau
  NotebookLM menjawab soal itu, jawabannya karangan.

## Daftar sumber

| File | Isi | Pakai untuk pertanyaan seperti |
|---|---|---|
| `01_ringkasan_proyek.md` | Apa itu TEPAT, masalah, tim, tiga komponen, pengaman, status singkat | "TEPAT itu apa?", "Apa yang sudah jadi?" |
| `02_cara_kerja_metode.md` | Aturan triase (ambang persis), skor urutan, peringatan dini, uji lonjakan hari ke-45 | "Kenapa peserta X masuk jalur verifikasi?", "Fitur model apa saja?" |
| `03_data_sintetis_dan_kalibrasi.md` | Generator data, segmen laten, tabel, aturan JKN yang ditiru, kalibrasi ke Data Sampel BPJS 2024 | "Datanya dari mana?", "Seberapa mirip dengan data nyata?" |
| `04_hasil_dan_angka_kunci.md` | Semua angka utama, stabilitas 5 seed, daya uji | "Berapa presisi jalur verifikasi?", "Berapa AUC?" |
| `05_evaluasi_praregistrasi.md` | Pra-registrasi, target T1-T8, hasilnya (lulus/meleset), temuan eksploratif | "Target mana yang gagal?", "Apa hipotesis Zenda dan hasilnya?" |
| `06_aplikasi_api_dan_ai.md` | Aplikasi Streamlit (4 halaman), API, lapisan AI draf pesan dan pengamannya | "Halaman Keadilan menunjukkan apa?", "AI boleh melakukan apa?" |
| `07_keterbatasan_dan_pertanyaan_juri.md` | Keterbatasan, risiko, pertanyaan terbuka ke BPJS, latihan tanya-jawab juri | "Apa kelemahan terbesar TEPAT?", "Bagaimana menjawab kalau juri bilang datanya sintetis?" |
| `08_riwayat_dan_status_pekerjaan.md` | Linimasa commit, pembagian peran, status tiap pekerjaan, yang belum beres | "Siapa mengerjakan apa?", "Apa yang masih tertunda?" |
| `09_glosarium.md` | Istilah JKN, statistik, dan istilah internal proyek | "Apa itu lompatan?", "Apa beda PBPU dan BP?" |

## Cara memasukkan ke NotebookLM

1. Buat notebook baru.
2. Tambahkan kesepuluh sumber sebagai sumber terpisah. Ada dua cara:
   - **Google Docs:** di NotebookLM pilih "Google Drive", lalu centang kesepuluh dokumen di folder
     "TEPAT - Sumber NotebookLM (30 Okt 2026)". Kalau dokumennya diubah, tekan sinkronkan di
     NotebookLM supaya isinya ikut terbarui.
   - **File Markdown:** unggah kesepuluh file `.md` di folder `docs/notebooklm/` repo. Kalau
     unggahan `.md` ditolak, ganti ekstensinya ke `.txt`; isinya tetap terbaca.
3. Opsional: tambahkan `bukti/preregistration.md` apa adanya. Itu dokumen yang dikunci sebelum
   penilaian, jadi berguna kalau perlu kutipan kata per kata. `README.md` tidak perlu ditambahkan:
   isinya sudah tercakup, dan sebagian bagiannya sudah usang (lihat sumber 08).
4. Selalu cek kutipan sumber yang ditunjukkan NotebookLM. Angka tanpa kutipan jangan dipakai di
   presentasi.

## Pertanyaan pembuka yang disarankan untuk Zenda

1. Jelaskan TEPAT dalam tiga kalimat, tanpa istilah teknis.
2. Apa empat rute triase, dan apa syarat persis tiap rute?
3. Kenapa peserta DTSEN desil 1-5 tidak pernah masuk jalur verifikasi?
4. Apa itu uji lonjakan hari ke-45 dan kenapa perlu plasebo IGD?
5. Target pra-registrasi mana yang meleset, dan kenapa?
6. Hipotesis IGD yang ditulis Zenda: apa isinya dan apa hasilnya?
7. Di bagian mana model peringatan dini lebih baik dari aturan sederhana, dan di bagian mana tidak?
8. Apa yang berubah ketika data dibuat lebih mirip Data Sampel BPJS 2024?
9. Apa tiga kelemahan terbesar yang paling mungkin diserang juri?
10. Apa yang masih tertunda per 30 Oktober 2026?
