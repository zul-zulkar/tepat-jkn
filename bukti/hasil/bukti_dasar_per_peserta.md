# Kartu bukti

## Kondisi pengujian

|  |  |
|---|---|
| Sumber data | sintetis |
| Tolok ukur | data dasar buatan tim sendiri (bukan benchmark independen); IK di kartu ini per peserta, IK per wilayah ada di t2_t8_presisi.csv |
| Generator ditulis oleh | Zul bersama asisten AI; penulis sama dengan penulis aturan |
| Dikalibrasi ke | regulasi saja (Perpres 64/2020, Perpres 59/2024); perilaku dan biaya dikarang |
| Seed | 2026 |
| Entitas yang dinilai | 20.000 |
| Prevalensi | 10,1% |
| Kapasitas audit k | 200 peserta (asumsi) |

## Hasil utama pada kapasitas k

|  |  |
|---|---|
| precision@k | 0,98 (IK 95% 0,96–0,99, resampling per peserta) |
| Lift dibanding acak | 9,7× |
| Persentase peserta jujur yang diaudit | 4 / 17.988 (0,0%) |

## Positif palsu tingkat entitas

4 dari 17.988 peserta jujur termasuk kasus yang ditandai (tingkat positif palsu 0,0%). Bukan metrik utama: pada kapasitas tetap angka ini selalu kecil. Persentase peserta jujur yang diaudit menunjukkan di mana bebannya jatuh.

## Recall@k per modus

| Modus | Kasus | Masuk k teratas | Recall |
|---|---|---|---|
| reaktivasi_saat_butuh | 2.012 | 196 | 0,10 (lemah) |

## Persentase peserta jujur yang diaudit, per strata

| Strata | Nilai | Jujur | Ditandai | Tingkat |
|---|---|---|---|---|
| kelas | kelas_1 | 3.733 | 0 | 0% |
| kelas | kelas_2 | 5.729 | 0 | 0% |
| kelas | kelas_3 | 8.526 | 4 | 0,0% |
| kemiskinan | rendah | 6.101 | 1 | 0,0% |
| kemiskinan | sedang | 5.796 | 1 | 0,0% |
| kemiskinan | tinggi | 6.091 | 2 | 0,0% |
| usia | 36-55 | 9.163 | 3 | 0,0% |
| usia | <=35 | 5.936 | 1 | 0,0% |
| usia | >55 | 2.889 | 0 | 0% |
| jk | L | 9.048 | 2 | 0,0% |
| jk | P | 8.940 | 2 | 0,0% |
| ukuran | besar | 6.002 | 3 | 0,0% |
| ukuran | sedang | 5.999 | 0 | 0% |
| ukuran | kecil | 5.987 | 1 | 0,0% |

## Keterbatasan

- Data sintetis; kinerja pada peserta nyata belum diukur.
- Lemah pada reaktivasi_saat_butuh (recall@k di bawah 0,30).
- Persentase peserta jujur yang diaudit untuk kelas kelas_3 sebesar 0,0%, lebih dari dua kali rata-rata 0,0%.
- Persentase peserta jujur yang diaudit untuk ukuran besar sebesar 0,0%, lebih dari dua kali rata-rata 0,0%.

## Untuk juri

Dari 200 peserta yang diaudit pada asumsi kapasitas kami (200), 196 (IK 95% 192–199) merupakan fraud pada data dasar buatan tim sendiri (bukan benchmark independen); IK di kartu ini per peserta, IK per wilayah ada di t2_t8_presisi.csv, 9,7× dibanding pemilihan acak. Dari 17.988 peserta yang jujur, 4 ikut diaudit.
