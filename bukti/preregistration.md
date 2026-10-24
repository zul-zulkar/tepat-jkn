# Pre-registration of evaluation targets

Fill this in and commit it before you run the evaluation. The commit timestamp
shows the targets were set before the results were known.

    git add templates/preregistration.md
    git commit -m "preregister targets"

## Record

- Date:
- Commit hash of the detector being tested:
- Commit hash of the generator being used:
- Who wrote the generator, and did they see the detector?

## Test conditions

- Benchmark (who wrote it, how it differs from your own generator, which modus is held out):
- Data source (synthetic / public sample / pilot / real deployment):
- Distributions calibrated to public sources (list them) and distributions invented:
- Audit capacity k (count or share, and where the number comes from):
  - verifiers x cases per verifier per day x working days =
- Seed(s):

## Targets

| Metric | Threshold | Benchmark or condition | Why this threshold |
|---|---|---|---|
| precision@k, lower end of the 95% CI (resampled by group) | | | |
| lift over random at k | | | |
| rupiah recall@k | | | |
| share of honest groups audited, per stratum | | | |
| recall@k per modus (list the modus types) | | | |
| expert review: suspicious rate, flagged minus random | | | |

## What counts as failure

- A target is missed if:
- We will report a missed target by:

## Stress tests we commit to running

- [ ] ablation with a paired test between consecutive variants
- [ ] placebo: the same cut-off on a fraud-free version of the data
- [ ] label permutation test
- [ ] leakage scan
- [ ] blind expert review: top 20 flagged plus 20 random cases
- [ ] share of honest groups audited by stratum (list strata):

## Sign-off

| Name | Role | Date |
|---|---|---|
| | | |

2. ISI 2 Bertambah
3. ISI 3 Jalur periksa akan menjadi tepat sasaran
4. ISI 4 Alasannya adalah wawancara petugas BPJS dapat menggali informasi untuk mengetahui lebih dalam alasan konsumen BPJS tidak rutin membayar sebelum klaim atau langsung melunasi tunggakan demi dapat klaim BPJS

Kode	Yang diukur	Lulus bila	Kondisi
T1	Presisi jalur diperiksa pada k 1%	batas bawah selang 95% (200 undian) >= 50%	prevalensi 1%; data dasar + kasus jujur sebagai pengecoh
T2	Presisi jalur diperiksa pada k 1%	batas bawah IK95%, resampling per wilayah, >= 80%	data dasar apa adanya (prevalensi 10%); pembanding
T3	Porsi kasus jujur yang masuk jalur diperiksa	<= 5% per jenis; jatuh_miskin_sakit <= 1% (paling banyak 5 dari 500)	kasus jujur, aturan asli
T4	Porsi peserta jujur yang masuk jalur diperiksa, per kelompok: kelas; kemiskinan wilayah (3 kelompok); usia (<=35, 36-55, >55); jenis kelamin	tidak ada kelompok > 2x rata-rata	data dasar; dinilai hanya bila >= 30 peserta jujur masuk jalur, kalau kurang ditulis "terlalu sedikit untuk dinilai"
T5	Recall jenis yang ditahan: porsi baru_berhenti_cepat yang masuk jalur diperiksa	tanpa ambang	kasus jujur
T6	Lift peringatan dini pada k 1%	>= 3x	peserta yang belum pernah nonaktif; uji Jan-Sep 2025, gabungan bulan
T7	Ablasi berpasangan: aturan sederhana vs aturan + model, peringatan dini	tanpa ambang	semua peserta, dan yang belum pernah nonaktif
T8	Presisi jalur diperiksa pada k 1% dan rentang per wilayah	tanpa ambang	data konsentrasi, dibanding T2