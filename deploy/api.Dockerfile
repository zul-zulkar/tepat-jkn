# API triase (POST /triase, FastAPI) sebagai image sendiri.
# Dibangun dari folder utama repo:  docker build -f deploy/api.Dockerfile -t tepat-api .
# Stateless: tiap permintaan membawa riwayat pesertanya, jadi boleh banyak instance dan skala ke nol.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpl
WORKDIR /app
# hanya yang dipakai api.py -> cek_sinyal.py; tanpa streamlit dan scikit-learn
COPY requirements-api.txt ./
# Proksi pemeriksa TLS: sertakan CA-nya dengan  --secret id=ca,src=/path/ca.crt  (tanpa itu, berjalan biasa)
RUN --mount=type=secret,id=ca \
    PIP_CERT=$(test -f /run/secrets/ca && echo /run/secrets/ca) \
    pip install --no-cache-dir "numpy>=1.24,<3" "pandas>=2.2,<4" "matplotlib>=3.7,<4" -r requirements-api.txt \
 && useradd -m -u 10001 tepat
COPY api.py cek_sinyal.py ./
COPY bukti/skor_verifikasi.py bukti/skor_verifikasi.py
USER tepat
ENV PORT=8000
EXPOSE 8000
# satu proses cukup: pekerjaan per permintaan kecil (1-50 peserta). Tambah instance, bukan worker.
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
