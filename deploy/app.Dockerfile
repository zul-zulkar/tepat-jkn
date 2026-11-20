# TEPAT (antarmuka Next.js + API Go + data) dalam satu image kecil.
# Dibangun dari folder utama repo:  docker build -f deploy/app.Dockerfile -t tepat-jkn .
# Data sintetis dan antarmuka tertanam di berkas program; tanpa Python, Node, atau internet saat jalan.

# 1) antarmuka: next build -> web/out
FROM node:22-alpine AS web
WORKDIR /src
COPY static ./static
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
# Jaringan dengan proksi pemeriksa TLS (kantor, CI): sertakan CA-nya dengan  --secret id=ca,src=/path/ca.crt
# Tanpa secret itu, langkah ini berjalan biasa.
RUN --mount=type=secret,id=ca \
    NODE_EXTRA_CA_CERTS=$(test -f /run/secrets/ca && echo /run/secrets/ca) npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# 2) server: tanam data + antarmuka, build statis
FROM golang:1.26-alpine AS go
WORKDIR /src/server
COPY server/go.mod server/go.sum ./
RUN --mount=type=secret,id=ca \
    SSL_CERT_FILE=$(test -f /run/secrets/ca && echo /run/secrets/ca || echo /etc/ssl/certs/ca-certificates.crt) go mod download
COPY server/ ./
# label ground truth tidak ikut (evaluasi_label.parquet dikeluarkan lewat .dockerignore)
COPY app_data/ internal/aset/data/
COPY bukti/hasil/skor_verifikasi.csv bukti/hasil/beban_strata.csv internal/aset/bukti/
COPY --from=web /src/web/out internal/aset/web
RUN go vet -tags rilis ./... \
 && CGO_ENABLED=0 go build -tags rilis -trimpath -ldflags "-s -w" -o /out/tepat ./cmd/tepat

# 3) jalan: alpine kecil, pengguna biasa
FROM alpine:3.22
RUN adduser -D -u 10001 tepat
# sertifikat akar untuk memanggil API AI lewat HTTPS; zona waktu tertanam di program (time/tzdata)
COPY --from=go /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
ENV TZ=Asia/Jakarta
COPY --from=go /out/tepat /usr/local/bin/tepat
USER tepat
# Cloud Run dan Render mengisi PORT; bila kosong, server memakai 127.0.0.1:8080 jadi -addr wajib di sini.
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD wget -qO- http://127.0.0.1:${PORT}/healthz || exit 1
# Kunci AI hanya lewat variabel lingkungan saat run (GEMINI_API_KEY / ANTHROPIC_API_KEY), tidak pernah di image.
ENTRYPOINT ["tepat", "-buka=false"]
