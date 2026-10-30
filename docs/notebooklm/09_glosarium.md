# Glosarium proyek TEPAT

Kondisi per 30 Oktober 2026. Istilah diurutkan per kelompok.

## Istilah JKN dan BPJS Kesehatan

| Istilah | Arti di proyek ini |
|---|---|
| JKN | Jaminan Kesehatan Nasional, dikelola BPJS Kesehatan. |
| PBPU | Pekerja Bukan Penerima Upah (peserta mandiri). Fokus utama TEPAT. |
| BP | Bukan Pekerja. Ikut cakupan TEPAT bila membayar iuran sendiri. Di data nyata, BP hampir tidak pernah nonaktif karena premi (0,3%), karena sebagian besar penerima pensiun. |
| PPU | Pekerja Penerima Upah. Iuran dibayar pemberi kerja; dikeluarkan dari analisis. |
| PBI | Penerima Bantuan Iuran; iuran dibayar pemerintah. Dikeluarkan dari analisis; juga tujuan rute cek kelayakan. |
| PBPU/BP-Pemda | Peserta PBPU/BP yang iurannya dibayar Pemda. Dikeluarkan dari analisis. |
| Nonaktif | Jaminan berhenti sementara karena ada iuran bulan sebelumnya yang belum dibayar sampai akhir bulan (Perpres 59/2024 Ps. 42 ayat 1). |
| Reaktivasi / aktif lagi | Peserta melunasi tunggakan (maks 24 bulan) dan iuran bulan berjalan, lalu aktif kembali (Ps. 42 ayat 3). |
| Denda pelayanan | Denda untuk satu kali rawat inap dalam 45 hari setelah aktif lagi: 5% × biaya × bulan tertunggak (maks 12), maks Rp20 juta (Ps. 42 ayat 5-6). |
| Masa tunggu | Jeda antara daftar dan aktif untuk peserta baru (di generator 14 hari; dasar hukumnya belum diverifikasi). |
| RITL / RJTL | Rawat Inap Tingkat Lanjutan / Rawat Jalan Tingkat Lanjutan (di rumah sakit). |
| IGD | Instalasi Gawat Darurat. Rawat inap lewat IGD dianggap tidak bisa ditunda. |
| Rawat inap terjadwal (elektif) | Rawat inap yang direncanakan, sehingga waktunya bisa ditunda. |
| INA-CBG | Tarif paket klaim rumah sakit JKN. Prototipe **belum** memakainya; biaya klaim sintetis. |
| DTSEN | Data Tunggal Sosial dan Ekonomi Nasional. Di prototipe berupa flag desil 1-5 (miskin) atau 6-10, dengan satu tanggal pemutakhiran yang sengaja terlambat. |
| Desil | Pembagian penduduk ke 10 kelompok kesejahteraan; desil 1-5 = separuh terbawah. |
| REHAB / REHAB 3.0 | Program cicilan tunggakan untuk satu keluarga. Tim mengetahuinya dari berita; diperlakukan sebagai praktik administrasi BPJS. Pesan wajib menulis "REHAB 3.0". |
| Autodebet | Pembayaran iuran otomatis dari rekening. |
| VA | Virtual Account, nomor pembayaran iuran. Apakah per peserta atau per KK masih pertanyaan terbuka. |
| KK | Kartu Keluarga. Tagihan PBPU/BP dihitung per KK; generator masih per peserta. |
| Care Center 165 | Nomor layanan BPJS Kesehatan; satu-satunya angka di pesan yang tidak berasal dari data peserta. |

## Istilah internal TEPAT

| Istilah | Arti |
|---|---|
| Triase | Memilah peserta menunggak ke salah satu dari empat rute bantuan. |
| Rute / jalur | `verifikasi_pola_reaktivasi`, `rujuk_cek_kelayakan_PBI`, `pengingat_autodebet_REHAB`, `nonaktif_lama_tanpa_sinyal`, atau `tanpa_tindakan`. |
| Jalur diperiksa / jalur verifikasi | Rute `verifikasi_pola_reaktivasi`. Daftar periksa untuk petugas, bukan vonis. |
| Bayar saat butuh / reaktivasi saat butuh (RSB) | Segmen yang baru melunasi ketika mau berobat mahal, lalu berhenti lagi. |
| Pengakal_45 | Bagian segmen bayar-saat-butuh (45% di generator) yang menunda rawat inap terjadwal sampai lewat hari ke-45. |
| Klaim besar | Rawat inap apa pun, atau rawat jalan ≥ Rp1 juta. |
| Reaktivasi terkait klaim | Reaktivasi yang diikuti klaim besar dalam 90 hari. |
| Pola rutin lalu berhenti | Rutin aktif ≥ 9 bulan, lalu nyaris tidak aktif ≥ 4 bulan sampai akhir data; tanda jatuh miskin. |
| Jeda DTSEN | Peserta yang tertangkap sebagai tidak mampu lewat pola padahal DTSEN-nya belum desil 1-5. |
| Skor urutan | Skor untuk mengurutkan peserta di dalam jalur verifikasi (rumus di sumber 02). Bukan peluang, bukan bukti. |
| Peringatan dini (early warning, EW) | Model yang menebak peluang peserta aktif menunggak dalam 3 bulan. |
| Berisiko menunggak | Nama daftar peringatan dini di aplikasi. |
| Segmen laten | Kelompok perilaku sebenarnya (patuh, lalai, tidak mampu, bayar saat butuh); hanya diketahui di data sintetis. |
| Label / kunci jawaban / ground truth | Segmen laten yang disimpan generator; hanya untuk mengukur hasil, tidak pernah untuk menentukan rute. |
| Profil `asumsi` | Parameter generator karangan tim; dasar semua angka proposal. |
| Profil `sampel2024` | Parameter generator yang dikalibrasi ke Data Sampel BPJS 2024; pembanding. |
| Kasus jujur | Data uji berisi orang jujur yang polanya mirip curang (sumber 03). |
| Jenis yang ditahan (hold-out) | Jenis curang yang sengaja tidak dikenali aturan (`baru_berhenti_cepat`), untuk menguji recall. |
| Dial konsentrasi | Data uji di mana bayar-saat-butuh hanya ada di 5 wilayah. |
| Angka kanonik | Angka seed 2026 yang tertulis di proposal; dijaga oleh `cocokkan_angka.py`. |
| Aturan A / B | A: rawat inap IGD dihitung sebagai klaim besar (dipakai). B: tidak dihitung (pembanding). |
| N03, N04, N05, N06, N11, Z09 | Kode pekerjaan internal (lihat sumber 08). |
| Eval-kit | `healthkathon-eval-kit` milik panitia; dipakai untuk menghitung presisi, selang, ablasi, dan kartu bukti. |

## Istilah statistik dan evaluasi

| Istilah | Arti |
|---|---|
| Data sintetis | Data buatan yang meniru struktur data nyata, tanpa orang sungguhan. |
| Seed | Angka awal pengacak; seed sama → data sama persis. |
| Presisi | Dari yang ditandai, berapa persen yang benar sasarannya. |
| Recall | Dari semua sasaran, berapa persen yang tertandai. |
| Prevalensi | Porsi sasaran di populasi. Presisi turun bila prevalensi turun. |
| k / kapasitas | Berapa peserta yang sanggup ditangani petugas per bulan, dinyatakan sebagai persen peserta. |
| Presisi@k | Presisi di antara k peserta teratas. |
| Lift | Presisi dibagi tingkat dasar; berapa kali lebih baik dari memilih acak. |
| AUC | Seberapa baik model mengurutkan dari yang paling berisiko; 0,5 = acak, 1 = sempurna. |
| Brier score | Rata-rata kuadrat selisih peluang tebakan dan kenyataan; makin kecil makin baik. |
| Kalibrasi (model) | Apakah peluang tebakan cocok dengan kejadian nyata. |
| Kalibrasi (generator) | Menyesuaikan parameter generator supaya angka agregatnya mirip data nyata. |
| Regresi logistik | Model statistik untuk peluang kejadian ya/tidak. |
| Rasio odds | Pengali peluang (dalam odds) per perubahan satu fitur; > 1 menaikkan risiko. |
| Validasi waktu | Latih di masa lalu, uji di masa sesudahnya, tanpa tumpang tindih. |
| Ablasi | Membandingkan sistem dengan dan tanpa satu komponen (di sini: aturan saja vs aturan + model). |
| IK95% / selang 95% | Rentang ketidakpastian; di sini dari bootstrap atau undian. |
| Bootstrap | Mengambil ulang sampel secara acak untuk memperkirakan ketidakpastian. |
| Resampling per wilayah | Bootstrap dengan mengambil ulang wilayah, bukan orang; selang jadi lebih lebar dan jujur. |
| Bunching / uji lonjakan | Mendeteksi penumpukan kejadian tepat sesudah sebuah batas aturan (di sini hari ke-45). |
| Kontrafaktual | Perkiraan kondisi "kalau tidak ada yang menunda" (kurva polinomial). |
| Kelebihan | Kasus aktual di atas kurva di hari 46-60; perkiraan jumlah kasus yang ditunda. |
| Kekurangan | Kasus aktual di bawah kurva di hari 31-45. |
| Lompatan | Kelebihan + kekurangan; ukuran uji lonjakan. Bukan jumlah kasus yang ditunda. |
| Plasebo | Kelompok pembanding yang seharusnya tidak menunjukkan efek (di sini rawat inap IGD). |
| Daya uji | Peluang uji mendeteksi efek yang memang ada. |
| MDE | Minimum Detectable Effect, efek terkecil yang terdeteksi dengan daya 80%. |
| Pra-registrasi | Menetapkan target dan cara menilai sebelum hasil diketahui, dibuktikan dengan jam commit. |
| Uji buta | Penilai tidak tahu mana kasus yang ditandai sistem (dipakai di review pakar N11). |
| SHA-256 | Sidik jari berkas; membuktikan berkas tidak diubah setelah dicatat. |
