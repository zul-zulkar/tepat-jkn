#!/usr/bin/env bash
# Build rilis TEPAT: antarmuka Next.js + data ditanam ke satu berkas program per sistem operasi.
# Hasil di server/rilis/. Jalan di Linux, macOS, atau Git Bash di Windows. Butuh Node.js 20+ dan Go 1.26+.
#
#   cd server && ./rilis.sh
set -euo pipefail
cd "$(dirname "$0")"
AKAR=..
ASET=internal/aset

echo "1/4 antarmuka (next build)"
(cd "$AKAR/web" && npm ci --no-audit --no-fund && npm run build)

echo "2/4 salin data dan antarmuka ke $ASET"
rm -rf "$ASET/data" "$ASET/bukti" "$ASET/web"
mkdir -p "$ASET/data" "$ASET/bukti"
# label ground truth sengaja tidak ikut: hanya untuk halaman Evaluasi
for f in "$AKAR"/app_data/*.parquet "$AKAR/app_data/manifest.json"; do
  [ "$(basename "$f")" = evaluasi_label.parquet ] || cp "$f" "$ASET/data/"
done
cp "$AKAR/bukti/hasil/skor_verifikasi.csv" "$AKAR/bukti/hasil/beban_strata.csv" "$ASET/bukti/"
cp -r "$AKAR/web/out" "$ASET/web"

echo "3/4 uji"
go vet ./...
go test ./...

echo "4/4 build"
mkdir -p rilis
for target in windows/amd64 linux/amd64 darwin/arm64; do
  os=${target%/*}; arch=${target#*/}; ext=""
  [ "$os" = windows ] && ext=".exe"
  GOOS=$os GOARCH=$arch CGO_ENABLED=0 go build -tags rilis -trimpath -ldflags "-s -w" \
    -o "rilis/tepat-jkn-$os-$arch$ext" ./cmd/tepat
done
ls -lh rilis
