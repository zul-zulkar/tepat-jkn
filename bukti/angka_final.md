# Angka final untuk naskah video (N10)

Dibuat 30 Okt 2026. Satu baris untuk satu angka yang tampil atau diucapkan di 12 slide utama
deck video ("Bahan Ajar_Full_TEPAT Healthkathon 2026", Google Slides) dan di demo. Semua angka
kinerja berasal dari data sintetis, profil `asumsi`, seed 2026, kecuali disebut lain.

Status: **cek** = cocok dengan berkas di kolom sumber; **turunan** = dihitung ulang dari angka lain
dan cocok; **luar repo** = dari sumber publik yang dikutip di slide 12, tidak ada di repo;
**TIDAK COCOK** = jangan diucapkan sebelum diperbaiki.

## Rencana waktu (maks. 10 menit; panduan panitia 0,5/1/1,5/1,5/3/1,5/1)

| Slide | Isi wajib | Durasi saran |
|---|---|---|
| 01 Sampul | judul, deskripsi, tujuan | 0:30 |
| 02 Tim | tim + foto semua anggota | 0:25 |
| 03 Tunggakan terpusat | latar | 0:40 |
| 04 Dampak tiga skenario | dampak | 0:40 |
| 05 TEPAT dalam 30 detik | alur proses | 0:25 |
| 06 Alur kerja petugas | alur proses | 0:50 |
| 07 Demo | demo aplikasi berjalan | 3:00 |
| 08 Triase empat rute | fitur | 0:40 |
| 09 Peringatan dini | fitur | 0:35 |
| 10 Rapor jujur | tambahan | 0:35 |
| 11 Asal parameter | tambahan | 0:20 |
| 12 Penutup | tambahan | 0:10 |
| **Total** | | **±8:50** (sisa ±1 menit untuk jeda dan transisi) |

## Angka per slide

| Slide | Angka | Arti (satu kalimat) | Sumber | Status |
|---|---|---|---|---|
| 03 | Rp26,47 T | Total piutang iuran JKN, Feb 2026 | Bisnis.com 11 Feb 2026 (sumber [3] di slide 12); `README.md` | luar repo |
| 03 | Rp22,29 T | Piutang iuran yang berasal dari PBPU Mandiri | idem | luar repo |
| 03 | 84,20% | Porsi piutang dari PBPU Mandiri (22,29 / 26,47) | turunan dari dua angka di atas | turunan |
| 04 | ±349 ribu peserta per bulan | Daftar k 2% x 17.464.328 PBPU Mandiri aktif | `hasil/early_warning_ringkasan.txt` (setara_nasional 349.287) | cek |
| 04 | 6.986 / 20.957 / 55.886 | Peserta tidak jadi kehilangan penjaminan per bulan, skenario rendah/sedang/tinggi | 349.287 x presisi x efek kontak (40%x5%, 60%x10%, 80%x20%) | turunan |
| 04 | Rp3,5 / 21,1 / 84,5 miliar | Iuran yang tetap masuk setahun | peserta di atas x Rp42.000 x bulan iuran (1/2/3) x 12 | turunan |
| 04 | Rp0 / ±Rp125 jt / ±Rp375 jt | Denda lolos per 1.000 rawat inap terjadwal pasca-reaktivasi | proposal; rumusnya tidak ada di repo | luar repo |
| 04 | efek kontak 5/10/20% | Asumsi tanpa sumber, diukur di pilot | karangan (slide sudah memberi label "belum bersumber") | karangan |
| 08 | 909 | Peserta di rute verifikasi pola reaktivasi | `hasil/ringkasan.txt`; `cocokkan_angka.py` | cek |
| 08 | 2.133 | Peserta di rute cek kelayakan PBI | idem | cek |
| 08 | 5.059 | Peserta di rute pengingat/autodebet/REHAB | idem | cek |
| 08 | 224 | Peserta di rute verifikasi kemampuan bayar | idem | cek |
| 08 | 11.675 | Peserta tanpa tindakan | idem | cek |
| 09 | 1%: model 90,6-93,4% vs sederhana 93,6-95,0% | Presisi daftar 1% teratas, semua peserta aktif | `hasil/stabilitas_ringkasan.txt` (5 seed, bukan 3 seperti tulisan slide) | cek, label seed salah |
| 09 | 2%: 86,6-88,2% vs 87,2-89,4% | Presisi daftar 2% teratas | tidak ada di repo; seed 2026 saja: 88,2% vs 89,4% (`hasil/early_warning_ringkasan.txt`) | **TIDAK COCOK** |
| 09 | 5%: 79,4-80,1% vs 79,2-79,6% | Presisi daftar 5% teratas | repo 5 seed: model 78,9-80,1%, sederhana 78,6-79,6% | **TIDAK COCOK** |
| 09 | 52-56% | Presisi daftar 1% pilihan model pada yang belum pernah menunggak | repo 5 seed: 49,3-55,7%; seed 2026: 52,2% | **TIDAK COCOK** |
| 09 | ±5% | Presisi bila dipilih acak atau cara sederhana | base rate 6,0%; aturan pada subset 5,1-5,6% (`bukti/hasil/ringkasan_n06_ew.txt`) | cek (pembulatan) |
| 10 | 98,0% (96,0-99,5) | T2: presisi rute verifikasi, prevalensi 10% | `bukti/hasil/ringkasan_n06_jalur.txt` | cek |
| 10 | 60,0% (55,7-63,8); 38,1% | T1: presisi di prevalensi 1%, aturan 3a; angka eval-kit bawaan | idem | cek |
| 10 | 8,6x | T6: lift peringatan dini pada yang belum pernah menunggak | `bukti/hasil/ringkasan_n06_ew.txt` | cek |
| 10 | 6,4% (32 dari 500) | T3: orang jatuh miskin lalu sakit yang ikut masuk rute verifikasi; target <= 1% | `bukti/hasil/ringkasan_n06.md` | cek |
| 10 | 18 | T4: orang jujur di rute verifikasi; terlalu sedikit untuk dinilai | idem | cek |
| 10 | 42,5% | Presisi di prevalensi 0,5% | idem | cek |
| 10 | AUC 0,40 | Skor urutan di dalam jalur (eksploratif) | idem | cek |
| 10 | 20.000 + 2.500 | Peserta data dasar + kasus jujur | `bukti/preregistration.md` bagian 2 | cek |
| 11 | 6 / 2 / 0 / 26 | Parameter dari regulasi / belum diverifikasi / statistik publik / karangan | `bukti/asal_parameter.md` | cek |
| 11 | 98,0% -> 60,0% | Presisi bila bayar-saat-butuh 1% peserta | `bukti/hasil/ringkasan_n06_jalur.txt` | cek |
| 11 | 98,0% -> 89,4%; 18 -> 76; 0,854 -> 0,815 | Profil `sampel2024` dibanding `asumsi` | `hasil_kalibrasi/ringkasan.txt`, `hasil_kalibrasi/early_warning_ringkasan.txt`, `hasil/ringkasan.txt` | cek |

## Angka yang mungkin diucapkan saat demo

| Halaman | Angka | Arti | Sumber | Status |
|---|---|---|---|---|
| Daftar kerja | 7.788 | Peserta dengan satu tindakan bulan ini (k 5%) | aplikasi; CLAUDE.md bagian 7 | tidak dihitung ulang di sesi ini |
| Daftar kerja | 650 | Peserta "berisiko menunggak (3 bulan ke depan)" | idem | tidak dihitung ulang di sesi ini |
| Kebijakan | 169 (IK 131-213) | Kelebihan rawat inap terjadwal hari 46-60 = perkiraan yang ditunda | `hasil/ringkasan.txt` | cek |
| Kebijakan | 227 (IK 185-274) | Lompatan, ukuran uji (bukan jumlah yang ditunda) | idem | cek |
| Kebijakan | Rp745 juta | Denda terhindar, biaya sintetis | idem | cek |
| Kebijakan | 4 (IK -24 s.d. 31) | Plasebo IGD: tidak ada lompatan | idem | cek |
| Peringatan dini | AUC 0,854 (aturan 0,822) | Ketepatan urutan model peringatan dini | `hasil/early_warning_ringkasan.txt` | cek |

## Kalimat yang dilarang di naskah

- "Presisi 98%" tanpa "di data buatan kami" dan tanpa menyebut 60% di prevalensi 1%.
- "227 rawat inap ditunda": 227 adalah ukuran uji. Yang ditunda diperkirakan 169.
- "AI menandai pasien IGD" atau kata "curang".
- "Model lebih baik dari aturan" untuk semua peserta: untuk semua peserta aktif, model kalah 1,5 poin (T7).
