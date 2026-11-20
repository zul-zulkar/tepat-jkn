# Menjalankan TEPAT di production (Next.js + Go) dan membukanya dari web

Satu proses Go menyajikan API dan antarmuka Next.js (static export) di satu port. Tidak ada server Node saat
jalan. Data dan antarmuka tertanam di berkas program, jadi satu image Docker (±41 MB) atau satu berkas `.exe`
sudah cukup.

```
peramban ──HTTPS──► [Caddy / Cloud Run / Render]  ──HTTP──►  tepat (Go, :8080)
                     sertifikat dan domain                     /            antarmuka (HTML statis)
                                                               /api/*       JSON, sesi lewat kuki
                                                               /healthz     untuk pemeriksa kesehatan
```

## Pilih jalur dulu

| Keperluan | Jalur | Catatan |
|---|---|---|
| **Final offline 25 Nov** | `tepat-jkn-windows-amd64.exe` di laptop | Tanpa internet, tanpa cold start. Ini jalur utama. |
| Tautan untuk juri atau pembaca proposal | Docker di VPS, atau Cloud Run | Hanya cadangan. Jangan jadikan satu-satunya jalur demo. |
| API triase (`POST /triase`) | `deploy/api.Dockerfile` | Layanan terpisah, lihat bagian bawah. |

## 1. Bangun image

Dari folder utama repo:

```bash
docker build -f deploy/app.Dockerfile -t tepat-jkn .
docker run --rm -p 8080:8080 tepat-jkn          # buka http://localhost:8080/?akun=pusat
```

`evaluasi_label.parquet` (kunci jawaban sintetis) tidak ikut ke image: dikeluarkan lewat
`deploy/app.Dockerfile.dockerignore`, dan `data_sampel/` tidak pernah masuk konteks build.

Jaringan dengan proksi pemeriksa TLS (kantor, CI) membuat `npm ci` dan `go mod download` gagal dengan
"unknown authority". Sertakan CA-nya, tanpa mematikan verifikasi:

```bash
docker build --secret id=ca,src=/path/ca.crt -f deploy/app.Dockerfile -t tepat-jkn .
```

## 2. Variabel lingkungan

| Variabel | Fungsi |
|---|---|
| `PORT` | Port yang didengar (diisi otomatis Cloud Run dan Render). Bawaan image: 8080. |
| `GEMINI_API_KEY` atau `ANTHROPIC_API_KEY` | Menghidupkan tombol "Tulis ulang dengan AI". Tanpa kunci, aplikasi memakai template dan tetap jalan. |
| `TEPAT_LLM_PROVIDER` | `gemini` atau `anthropic`, bila dua kunci terpasang. |
| `TEPAT_AI` | `off` mematikan lapisan AI sepenuhnya. |
| `TZ` | Zona waktu catatan keputusan. Bawaan image: `Asia/Jakarta`. |

Kunci API hanya lewat variabel lingkungan atau secret manager platform. Jangan masukkan ke image, repo, atau
`docker build --build-arg`.

## 3a. VPS sendiri (Docker + Caddy), HTTPS otomatis

Butuh satu VPS (Oracle Always Free, atau yang berbayar kecil) dan satu domain yang A-recordnya mengarah ke VPS.

```bash
docker run -d --name tepat --restart unless-stopped -p 127.0.0.1:8080:8080 \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" tepat-jkn
```

`/etc/caddy/Caddyfile`:

```
tepat.contoh.id {
    encode gzip
    reverse_proxy 127.0.0.1:8080
}
```

Caddy mengurus sertifikat Let's Encrypt. Server Go membaca `X-Forwarded-Proto` dari Caddy, jadi kuki sesi ditandai
`Secure` dan header HSTS dipasang. Belum diuji dengan domain sungguhan di sesi ini.

## 3b. Google Cloud Run

Dorong image sendiri, karena `gcloud run deploy --source .` mencari `Dockerfile` di folder utama, bukan di `deploy/`:

```bash
docker tag tepat-jkn asia-southeast2-docker.pkg.dev/PROYEK/tepat/tepat-jkn:1
docker push asia-southeast2-docker.pkg.dev/PROYEK/tepat/tepat-jkn:1
gcloud run deploy tepat --image asia-southeast2-docker.pkg.dev/PROYEK/tepat/tepat-jkn:1 --region asia-southeast2 \
  --port 8080 --memory 512Mi --max-instances 1 --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=gemini-key:latest
```

Perintah ini belum dijalankan di sesi ini (butuh akun Google Cloud dan kartu). Poin penting:

- **`--max-instances 1` wajib.** Sesi login dan keputusan petugas disimpan di memori proses. Dua instance berarti
  pengguna yang login di instance A mendapat 401 di instance B.
- Skala ke nol membuat permintaan pertama setelah sepi menunggu container naik dan data dimuat (±1 detik muat
  data ditambah cold start). Sebelum tampil: `--min-instances 1`, atau buka sekali beberapa menit sebelumnya.
- Memori sesi hilang saat deploy ulang atau instance diganti. Itu wajar untuk demo, bukan untuk pemakaian nyata.

## 3c. Render

Web Service jenis Docker, `Dockerfile Path` = `deploy/app.Dockerfile`, tanpa perintah start (ENTRYPOINT sudah
ada). Paket gratis tidur setelah 15 menit tanpa lalu lintas; bangun kembali 30–60 detik.

## 4. API triase (`POST /triase`)

Terpisah dari aplikasi: stateless, tiap permintaan membawa riwayat pesertanya.

```bash
docker build -f deploy/api.Dockerfile -t tepat-api .
docker run --rm -p 8000:8000 tepat-api        # http://localhost:8000/docs
```

Karena stateless, berbeda dari aplikasi di atas, ia boleh banyak instance dan skala ke nol tanpa masalah sesi.
Diuji: 4 peserta contoh bawaan menghasilkan rute yang sama dengan `app_data/daftar_kerja.parquet`. Image ±530 MB
karena pandas dan matplotlib (dipakai `cek_sinyal.py`).

**Peringatan:** endpoint ini menerima riwayat per individu dan tidak punya autentikasi (`/docs` terbuka demi
demo). Untuk data nyata BPJS, pasang di jaringan internal atau di belakang gerbang yang mewajibkan kunci API.

## 5. Yang sudah dikeraskan di server Go

- Sesi di memori kedaluwarsa 12 jam tanpa aktivitas, dibatasi 5.000 sesi (yang paling lama tidak dipakai dibuang).
- Header: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP (tanpa sumber
  luar), HSTS di belakang HTTPS. Respons API `no-store`, aset ber-hash `immutable`, HTML `no-cache`.
- `/healthz` tidak membuat sesi, jadi aman dipanggil pemeriksa kesehatan tiap beberapa detik.
- SIGTERM (Docker, Cloud Run, systemd) menutup server dengan rapi, memberi 8 detik untuk permintaan berjalan.
- Batas waktu baca/tulis/diam dan ukuran header; badan JSON dibatasi 64 KB.

## 6. Yang belum ada (jujur)

- Keputusan petugas tidak disimpan permanen: hilang saat proses berhenti.
- Tidak ada login sungguhan; akun Pusat dan Cabang adalah akun demo. Jangan buka ke internet dengan data nyata.
- Tidak ada pembatasan laju (rate limit). Panggilan AI memakai kuota kunci yang sama untuk semua pengunjung.
- Docker tidak diuji di Windows. Exe Windows belum dijalankan di Windows.
