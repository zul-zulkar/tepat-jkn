# TEPAT: layanan Go + antarmuka Next.js

Aplikasi TEPAT versi produksi-awal. Angka, rute, dan skor **tidak dihitung ulang** di sini: semuanya datang dari
pipeline Python (`generate_data.py` → `cek_sinyal.py` / `early_warning.py` → `siapkan_app.py` → `app_data/`).
Layanan Go membaca `app_data/` yang sama dengan aplikasi Streamlit, jadi angkanya identik.

```
pipeline Python (batch)  ──►  app_data/*.parquet  ──►  server Go (API JSON)  ──►  web Next.js (static export)
                               bukti/hasil/*.csv        satu berkas program, data dan antarmuka ditanam
```

| Folder | Isi |
|---|---|
| `server/cmd/tepat` | program utama: API + berkas antarmuka dalam satu proses |
| `server/internal/data` | baca parquet dan CSV ke memori (label evaluasi tidak dibaca) |
| `server/internal/triase` | satu peserta satu tindakan, daftar berisiko menunggak pada kapasitas k, pasangan reaktivasi-klaim |
| `server/internal/keadilan` | panel keadilan (port `halaman/keadilan.py`), termasuk pemecah seri pra-registrasi 3a |
| `server/internal/acaknp` | `numpy.random.default_rng(...).random()` bit demi bit (SeedSequence + PCG64) |
| `server/internal/pesan` | template pesan dan lapisan AI dengan penjaga aturan (port `pesan_template.py` dan `llm.py`) |
| `server/internal/akun` | akun demo Pusat dan Cabang; pembatasan wilayah dijaga di server |
| `server/internal/api` | rute HTTP, sesi (kuki), keputusan petugas |
| `server/uji` | `setara.py` (API Go vs perhitungan Streamlit), `korpus_pesan.py` (korpus uji penjaga AI) |
| `web/` | Next.js 16 (App Router, static export), Tailwind 4 + komponen shadcn/ui (Radix), animasi UI dengan motion dan animasi grafik SVG dengan anime.js |
| `deploy/` | Dockerfile app dan API triase, panduan production ([deploy/README.md](../deploy/README.md)) |

## Menjalankan

Rilis (tanpa Python, Node, atau internet): jalankan berkas program, peramban terbuka sendiri di
`http://127.0.0.1:8080`. Tautan langsung: `http://127.0.0.1:8080/?akun=pusat` atau `?akun=cabang_a`.

```
tepat-jkn-windows-amd64.exe            # Windows
./tepat-jkn-linux-amd64 -addr 127.0.0.1:9000 -buka=false
```

Draf pesan AI memakai kunci dari variabel lingkungan, sama dengan `llm.py` (`GEMINI_API_KEY`,
`ANTHROPIC_API_KEY`, `TEPAT_AI=off`, `TEPAT_AI_TIMEOUT`, ...). Tanpa kunci atau tanpa internet, draf tetap dari
template. Contoh PowerShell: `$env:GEMINI_API_KEY = "..."; .\tepat-jkn-windows-amd64.exe`. Jangan menulis kunci ke
berkas.

Pengembangan (dua terminal, dari folder repo):

```
cd server && go run ./cmd/tepat -buka=false     # API di :8080, membaca ../app_data
cd web && npm install && npm run dev             # antarmuka di :3000, /api diteruskan ke :8080
```

Build rilis untuk Windows, Linux, dan macOS: `cd server && ./rilis.sh` (Git Bash di Windows). Hasil di
`server/rilis/` (tidak di-commit).

## Uji

```
cd server && go test ./...                                    # unit + korpus penjaga AI + angka kanonik
python server/uji/setara.py --url http://127.0.0.1:8080       # API Go vs tepat_ui.py / halaman/*.py
python server/uji/korpus_pesan.py                             # buat ulang korpus bila llm.py berubah
```

`setara.py` membandingkan 10 skenario daftar kerja (Pusat dan Cabang, k 1–20, filter wilayah), 150+ profil,
panel keadilan, dan uji lonjakan. Korpus penjaga AI berisi semua panggilan selama `uji_llm.py` berjalan ditambah
variasi buatan (kata terlarang, angka, kata menempel, karakter Unicode); Go harus memberi jawaban yang sama persis.

## Catatan port

- Regex Go (RE2) tidak punya lookaround dan memakai `\b`/`\w`/`\d` versi ASCII. Pola dari `llm.py` dijalankan pada
  proyeksi ASCII teks (`pesan/teks.go`), dan pola berlookaround ditulis sebagai pemindai biasa (`pesan/rapikan.go`).
- Pembulatan meniru Python (setengah ke genap): kapasitas k (`round(n * k / 100)`), rupiah, dan persen di layar.
- Bila `llm.py`, `pesan_template.py`, atau konstanta `cek_sinyal.py` berubah, buat ulang korpus dan jalankan
  `go test`; uji gagal bila Go tertinggal.
