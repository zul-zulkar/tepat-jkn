# Kartu bukti

## Kondisi pengujian

|  |  |
|---|---|
| Sumber data | sintetis |
| Tolok ukur | data konsentrasi buatan tim sendiri (bukan benchmark independen) |
| Generator ditulis oleh | Zul bersama asisten AI; penulis sama dengan penulis aturan |
| Dikalibrasi ke | regulasi saja (Perpres 64/2020, Perpres 59/2024); perilaku dan biaya dikarang |
| Seed | 2026 |
| Entitas yang dinilai | 20.000 |
| Prevalensi | 10,1% |
| Kapasitas audit k | 200 peserta (asumsi) |

## Hasil utama pada kapasitas k

|  |  |
|---|---|
| precision@k | 0,98 (IK 95% 0,91–0,99, resampling per wilayah) |
| Lift dibanding acak | 9,7× |
| Persentase wilayah jujur yang diaudit | 4 / 35 (11,4%) |

## Positif palsu tingkat entitas

4 dari 17.988 peserta jujur termasuk kasus yang ditandai (tingkat positif palsu 0,0%). Bukan metrik utama: pada kapasitas tetap angka ini selalu kecil. Persentase wilayah jujur yang diaudit menunjukkan di mana bebannya jatuh.

## Recall@k per modus

| Modus | Kasus | Masuk k teratas | Recall |
|---|---|---|---|
| reaktivasi_saat_butuh | 2.012 | 196 | 0,10 (lemah) |

## Persentase wilayah jujur yang diaudit, per strata

| Strata | Nilai | Jujur | Ditandai | Tingkat |
|---|---|---|---|---|
| kelas | kelas_3 | 35 | 4 | 11,4% |
| kemiskinan | rendah | 13 | 1 | 7,7% |
| kemiskinan | sedang | 10 | 1 | 10% |
| kemiskinan | tinggi | 12 | 2 | 16,7% |
| usia | 36-55 | 35 | 4 | 11,4% |
| jk | L | 18 | 4 | 22,2% |
| jk | P | 17 | 0 | 0% |
| ukuran | besar | 8 | 2 | 25% |
| ukuran | sedang | 13 | 2 | 15,4% |
| ukuran | kecil | 14 | 0 | 0% |

## Keterbatasan

- Data sintetis; kinerja pada peserta nyata belum diukur.
- Lemah pada reaktivasi_saat_butuh (recall@k di bawah 0,30).
- Persentase wilayah jujur yang diaudit untuk ukuran besar sebesar 25%, lebih dari dua kali rata-rata 11,4%.

## Untuk juri

Dari 200 peserta yang diaudit pada asumsi kapasitas kami (200), 196 (IK 95% 182–199) merupakan fraud pada data konsentrasi buatan tim sendiri (bukan benchmark independen), 9,7× dibanding pemilihan acak. Dari 35 wilayah yang jujur, 4 ikut diaudit.
