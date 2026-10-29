#!/usr/bin/env python3
"""
api.py - API tipis TEPAT: triase 1-50 peserta PBPU/BP mandiri dari riwayatnya.

Tidak ada logika baru. Rute, alasan, dan fitur dari cek_sinyal.py (saring_cakupan,
tabel_reaktivasi, fitur_peserta, triase); skor urutan dari bukti/skor_verifikasi.py.
Hasil per peserta sama dengan app_data/daftar_kerja.parquet.

Pengaman: DTSEN desil 1-5 tidak pernah di rute verifikasi (diperiksa di setiap permintaan;
bila terlanggar, API menjawab 500 tanpa hasil). Tanpa label: kolom di luar skema ditolak.
Tanpa LLM. Tanggal potong tetap 31 Des 2025 (cek_sinyal.AKHIR).

Jalankan dari folder utama repo (paket: requirements.txt + requirements-api.txt):
    uvicorn api:app --port 8000        # lalu buka http://127.0.0.1:8000/docs
"""
import importlib.util
import io
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import Body, FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR))  # cek_sinyal.py ASLI di folder utama, bukan salinan di bukti/
import cek_sinyal as cs  # noqa: E402

if Path(cs.__file__).resolve().parent != AKAR:
    raise ImportError(f"cek_sinyal terbaca dari {cs.__file__}, bukan dari {AKAR}")

# bukti/ bukan paket: dimuat dari path supaya salinan lama di bukti/ tidak masuk sys.path.
# Efek samping yang disengaja: skor_verifikasi memblokir pd.read_csv atas label_ground_truth.
_spek = importlib.util.spec_from_file_location("skor_verifikasi",
                                               AKAR / "bukti" / "skor_verifikasi.py")
sv = importlib.util.module_from_spec(_spek)
_spek.loader.exec_module(sv)

JALUR = sv.JALUR                     # "verifikasi_pola_reaktivasi"
TANGGAL_POTONG = cs.AKHIR.date()     # 31 Des 2025, tetap
if TANGGAL_POTONG != date(2025, 12, 31):
    raise ImportError(f"tanggal potong cek_sinyal berubah: {TANGGAL_POTONG}")
MAKS_PESERTA = 50
MAKS_BARIS = 5_000                   # per tabel; 50 peserta x 36 bulan jauh di bawahnya
KOLOM_LABEL = {"segmen", "pengakal_45", "peserta_baru", "tgl_guncangan"}  # = siapkan_app
RUTE = Literal["verifikasi_pola_reaktivasi", "rujuk_cek_kelayakan_PBI",
               "pengingat_autodebet_REHAB", "nonaktif_lama_tanpa_sinyal", "tanpa_tindakan"]
BULAN = r"^\d{4}-(0[1-9]|1[0-2])$"


# ---------------------------------------------------------------- skema masukan
# Urutan dan nama kolom = header CSV di data/. Kolom yang tidak dipakai triase boleh kosong.
class _Baris(BaseModel):
    model_config = ConfigDict(extra="forbid")  # kolom asing, termasuk kolom label, ditolak


class Peserta(_Baris):
    """Satu baris peserta.csv. Dipakai triase: id_peserta, tgl_daftar, iuran_bulanan,
    segmen_kepesertaan. iuran_bulanan wajib untuk PBPU/BP."""
    id_peserta: str = Field(min_length=1, max_length=40)
    tgl_daftar: date
    kelas: Optional[Literal[1, 2, 3]] = None
    iuran_bulanan: Optional[int] = Field(None, ge=0)
    usia_2023: Optional[int] = None
    jenis_kelamin: Optional[Literal["L", "P"]] = None
    kode_wilayah: Optional[str] = None
    autodebet: Optional[bool] = None
    segmen_kepesertaan: Literal["PBPU", "BP", "PPU", "PBI", "PBPU_BP_Pemda"]
    pembayar_iuran: Optional[str] = None


class RiwayatStatus(_Baris):
    """Satu baris riwayat_status.csv. Minimal satu baris per peserta."""
    id_peserta: str
    tgl_mulai: date
    tgl_selesai: date
    status: Literal["aktif", "nonaktif", "masa_tunggu"]


class Pembayaran(_Baris):
    """Satu baris pembayaran.csv. Dipakai triase: id_peserta, tgl_bayar,
    jumlah_bulan_dibayar, nominal (wajib untuk PBPU/BP)."""
    id_bayar: Optional[str] = None
    id_peserta: str
    tgl_bayar: date
    periode_awal: Optional[str] = Field(None, pattern=BULAN)
    periode_akhir: Optional[str] = Field(None, pattern=BULAN)
    jumlah_bulan_dibayar: int = Field(ge=1)
    nominal: Optional[int] = Field(None, ge=0)
    kanal: Optional[str] = None


class Klaim(_Baris):
    """Satu baris klaim.csv. Dipakai triase: id_peserta, tgl_masuk, jenis_layanan,
    biaya_klaim."""
    id_klaim: Optional[str] = None
    id_peserta: str
    id_episode: Optional[str] = None
    tgl_masuk: date
    tgl_keluar: Optional[date] = None
    jenis_layanan: Literal["RITL", "RJTL"]
    cara_masuk: Optional[Literal["IGD", "poli", "terjadwal"]] = None
    kelompok_layanan: Optional[str] = None
    kelas_rawat: Optional[Literal[1, 2, 3]] = None
    biaya_klaim: int = Field(ge=0)
    denda_pelayanan: Optional[int] = Field(None, ge=0)


class Dtsen(_Baris):
    """Satu baris dtsen_flag.csv. Peserta tanpa baris DTSEN dianggap tidak_padan."""
    id_peserta: str
    rentang_desil: Literal["1-5", "6-10"]
    tgl_pemutakhiran: Optional[date] = None


class Permintaan(BaseModel):
    """Riwayat 1-50 peserta, satu daftar per file CSV di data/ (dtsen = dtsen_flag.csv)."""
    model_config = ConfigDict(extra="forbid")
    peserta: list[Peserta] = Field(min_length=1, max_length=MAKS_PESERTA)
    riwayat_status: list[RiwayatStatus] = Field(min_length=1, max_length=MAKS_BARIS)
    pembayaran: list[Pembayaran] = Field(default_factory=list, max_length=MAKS_BARIS)
    klaim: list[Klaim] = Field(default_factory=list, max_length=MAKS_BARIS)
    dtsen: list[Dtsen] = Field(default_factory=list, max_length=MAKS_BARIS)

    @model_validator(mode="after")
    def _konsisten(self):
        salah = []
        ids = [p.id_peserta for p in self.peserta]
        dikenal = set(ids)
        if kembar := sorted(i for i, n in Counter(ids).items() if n > 1):
            salah.append(f"id_peserta kembar di peserta: {kembar[:5]}")
        if khusus := sorted(i for i in dikenal if i.startswith("__")):
            salah.append(f"id_peserta berawalan '__' dipakai API: {khusus[:5]}")
        for nama in ("riwayat_status", "pembayaran", "klaim", "dtsen"):
            if asing := sorted({b.id_peserta for b in getattr(self, nama)} - dikenal):
                salah.append(f"{nama} memuat id_peserta yang tidak ada di peserta: {asing[:5]}")
        if tanpa := sorted(dikenal - {b.id_peserta for b in self.riwayat_status}):
            salah.append(f"peserta tanpa riwayat_status: {tanpa[:5]}")
        if kembar := sorted(i for i, n in Counter(b.id_peserta for b in self.dtsen).items()
                            if n > 1):
            salah.append(f"lebih dari satu baris dtsen untuk: {kembar[:5]}")
        mandiri = {p.id_peserta for p in self.peserta if p.segmen_kepesertaan in cs.CAKUPAN}
        if kosong := sorted(p.id_peserta for p in self.peserta
                            if p.id_peserta in mandiri and p.iuran_bulanan is None):
            salah.append(f"iuran_bulanan kosong untuk PBPU/BP: {kosong[:5]}")
        if kosong := sorted({b.id_peserta for b in self.pembayaran
                             if b.id_peserta in mandiri and b.nominal is None}):
            salah.append(f"nominal pembayaran kosong untuk PBPU/BP: {kosong[:5]}")
        if terbalik := sorted({b.id_peserta for b in self.riwayat_status
                               if b.tgl_mulai > b.tgl_selesai}):
            salah.append(f"tgl_mulai sesudah tgl_selesai: {terbalik[:5]}")
        lewat = sorted({b.id_peserta for b in self.peserta if b.tgl_daftar > TANGGAL_POTONG}
                       | {b.id_peserta for b in self.riwayat_status
                          if b.tgl_selesai > TANGGAL_POTONG}
                       | {b.id_peserta for b in self.pembayaran if b.tgl_bayar > TANGGAL_POTONG}
                       | {b.id_peserta for b in self.klaim if b.tgl_masuk > TANGGAL_POTONG})
        if lewat:
            salah.append(f"riwayat sesudah tanggal potong {TANGGAL_POTONG}: {lewat[:5]}")
        if salah:
            raise ValueError("; ".join(salah))
        return self


# ---------------------------------------------------------------- skema keluaran
class Fitur(BaseModel):
    """Fitur perilaku per tanggal potong. Nama dan isi = kolom app_data/daftar_kerja.parquet."""
    jeda_dtsen: bool
    rentang_desil: Literal["1-5", "6-10", "tidak_padan"]
    tunggakan_bulan: int
    tunggakan_rp: int
    n_reaktivasi: int
    n_reakt_terkait_klaim: int
    porsi_reakt_terkait: float
    rasio_hari_aktif: float
    rasio_klaim_iuran: Optional[float] = Field(description="Kosong bila belum pernah membayar.")
    klaim_rp: float
    iuran_rp: float
    skor_patah: float
    pola_rutin_lalu_berhenti: bool
    bulan_berhenti: Optional[str]
    baru_klaim_lalu_berhenti: bool


class HasilPeserta(BaseModel):
    id_peserta: str
    rute: RUTE
    alasan: str = Field(description="Kosong untuk tanpa_tindakan.")
    skor_urutan: Optional[float] = Field(description=(
        "Urutan pemeriksaan di dalam rute verifikasi (rumus pra-registrasi, "
        "bukti/skor_verifikasi.py): makin tinggi, makin dulu diperiksa. Null di rute lain: "
        "skor hanya bermakna di dalam rute verifikasi dan tidak dipakai memilih siapa yang "
        "diperiksa. Belum terbukti: penilaian berlabel N06 (eksploratif) memberi AUC 0,40 "
        "di dalam jalur."))
    fitur: Fitur


class DiLuarCakupan(BaseModel):
    id_peserta: str
    segmen_kepesertaan: str
    alasan: str


class Jawaban(BaseModel):
    tanggal_potong: date
    jumlah_dinilai: int
    hasil: list[HasilPeserta] = Field(description="Urutan sama dengan daftar peserta masukan.")
    di_luar_cakupan: list[DiLuarCakupan]


FITUR = list(Fitur.model_fields)


# ---------------------------------------------------------------- hitung
def _tabel(baris, model, tgl):
    """Baris (dict) -> DataFrame lewat CSV di memori, supaya tipe kolom sama persis dengan
    cs.muat / sv.muat_tanpa_label yang membaca file CSV di data/."""
    teks = pd.DataFrame(baris, columns=list(model.model_fields)).to_csv(index=False)
    return pd.read_csv(io.StringIO(teks), parse_dates=tgl)


def _pengaman(p):
    """Aturan produk yang tidak boleh dilanggar. Sengaja `raise AssertionError`, bukan
    pernyataan `assert`, supaya tetap berlaku bila Python dijalankan dengan -O."""
    bocor = p["rute"].eq(JALUR) & p["rentang_desil"].eq("1-5")
    if bocor.any():
        raise AssertionError(f"{int(bocor.sum())} peserta DTSEN 1-5 masuk rute verifikasi")
    if not p.loc[p["rentang_desil"].eq("1-5"), "skor"].eq(0).all():
        raise AssertionError("skor urutan peserta DTSEN 1-5 bukan 0")
    if bocor := KOLOM_LABEL & set(p.columns):
        raise AssertionError(f"kolom label {sorted(bocor)} ada di hasil")


def _py(v):
    if isinstance(v, np.generic):
        v = v.item()
    return None if isinstance(v, float) and math.isnan(v) else v


def nilai_triase(req: Permintaan) -> dict:
    def tabel(nama, model, tgl):  # masukan + peserta pendamping (lihat PENDAMPING)
        return _tabel([b.model_dump() for b in getattr(req, nama)] + _PENDAMPING[nama],
                      model, tgl)

    D = dict(
        peserta=tabel("peserta", Peserta, []),
        bayar=tabel("pembayaran", Pembayaran, ["tgl_bayar"]),
        status=tabel("riwayat_status", RiwayatStatus, ["tgl_mulai", "tgl_selesai"]),
        klaim=tabel("klaim", Klaim, ["tgl_masuk", "tgl_keluar"]),
        dtsen=tabel("dtsen", Dtsen, []),
    )
    D, _ = cs.saring_cakupan(D)
    re = cs.tabel_reaktivasi(D["status"], D["bayar"])
    p = cs.triase(cs.fitur_peserta(D, re))
    p["skor"] = sv.skor_verifikasi(p)
    _pengaman(p)
    baris = {r["id_peserta"]: r for r in p.to_dict("records")}  # pendamping tidak dibaca

    hasil, luar = [], []
    for ps in req.peserta:
        r = baris.get(ps.id_peserta)
        if r is None:
            luar.append(dict(
                id_peserta=ps.id_peserta, segmen_kepesertaan=ps.segmen_kepesertaan,
                alasan="TEPAT hanya untuk PBPU/BP yang membayar iuran sendiri "
                       "(Perpres 59/2024 Ps. 42 ayat 7-8)"))
            continue
        hasil.append(dict(
            id_peserta=ps.id_peserta, rute=r["rute"], alasan=r["alasan"],
            skor_urutan=_py(r["skor"]) if r["rute"] == JALUR else None,
            fitur={f: _py(r[f]) for f in FITUR}))
    return dict(tanggal_potong=TANGGAL_POTONG, jumlah_dinilai=len(hasil), hasil=hasil,
                di_luar_cakupan=luar)


# ---------------------------------------------------------------- contoh (data sintetis)
# generate_data.py --n 20000 --seed 2026: satu peserta per rute, riwayat terpendek.
# P-014822 verifikasi (2 reaktivasi, keduanya diikuti bedah elektif terjadwal),
# P-000520 cek PBI (DTSEN 1-5), P-017030 pengingat, P-008627 tanpa tindakan.
_CONTOH = {
    "peserta": (Peserta, [
        ("P-014822", "2018-01-09", 2, 100000, 29, "L", "W23", False, "PBPU", "peserta"),
        ("P-000520", "2018-02-19", 1, 150000, 44, "L", "W09", False, "PBPU", "peserta"),
        ("P-017030", "2019-09-15", 3, 42000, 50, "L", "W01", False, "PBPU", "peserta"),
        ("P-008627", "2018-01-13", 3, 42000, 30, "L", "W22", False, "PBPU", "peserta"),
    ]),
    "riwayat_status": (RiwayatStatus, [
        ("P-014822", "2023-01-01", "2023-04-12", "nonaktif"),
        ("P-014822", "2023-04-13", "2023-06-30", "aktif"),
        ("P-014822", "2023-07-01", "2024-12-24", "nonaktif"),
        ("P-014822", "2024-12-25", "2025-03-31", "aktif"),
        ("P-014822", "2025-04-01", "2025-12-31", "nonaktif"),
        ("P-000520", "2023-01-01", "2025-12-31", "nonaktif"),
        ("P-017030", "2023-01-01", "2023-08-01", "nonaktif"),
        ("P-017030", "2023-08-02", "2023-09-30", "aktif"),
        ("P-017030", "2023-10-01", "2025-05-04", "nonaktif"),
        ("P-017030", "2025-05-05", "2025-06-30", "aktif"),
        ("P-017030", "2025-07-01", "2025-11-06", "nonaktif"),
        ("P-017030", "2025-11-07", "2025-12-31", "aktif"),
        ("P-008627", "2023-01-01", "2025-11-04", "nonaktif"),
        ("P-008627", "2025-11-05", "2025-12-31", "aktif"),
    ]),
    "pembayaran": (Pembayaran, [
        ("B-00364492", "P-014822", "2023-04-13", "2022-02", "2023-04", 15, 1500000, "minimarket"),
        ("B-00364493", "P-014822", "2023-05-07", "2023-05", "2023-05", 1, 100000, "mobile_jkn"),
        ("B-00364494", "P-014822", "2024-12-25", "2023-06", "2024-12", 19, 1900000, "va_bank"),
        ("B-00364495", "P-014822", "2025-01-07", "2025-01", "2025-01", 1, 100000, "va_bank"),
        ("B-00364496", "P-014822", "2025-02-01", "2025-02", "2025-02", 1, 100000, "minimarket"),
        ("B-00418619", "P-017030", "2023-08-02", "2022-02", "2023-08", 19, 798000, "mobile_jkn"),
        ("B-00418620", "P-017030", "2025-05-05", "2023-09", "2025-05", 21, 882000, "va_bank"),
        ("B-00418621", "P-017030", "2025-11-07", "2025-06", "2025-11", 6, 252000, "minimarket"),
        ("B-00212506", "P-008627", "2025-11-05", "2023-12", "2025-11", 24, 1008000, "va_bank"),
    ]),
    "klaim": (Klaim, [
        ("K-00050618", "P-014822", "E-0038145", "2023-05-13", "2023-05-17", "RITL", "terjadwal",
         "bedah_elektif", 2, 18649000, 11189400),
        ("K-00050619", "P-014822", "E-0038146", "2025-02-04", "2025-02-07", "RITL", "terjadwal",
         "bedah_elektif", 2, 12797000, 7678200),
    ]),
    "dtsen": (Dtsen, [
        ("P-000520", "1-5", "2025-01-01"),
        ("P-017030", "6-10", "2025-01-01"),
        ("P-008627", "6-10", "2025-01-01"),
    ]),
}
CONTOH = {nama: [dict(zip(model.model_fields, b)) for b in isi]
          for nama, (model, isi) in _CONTOH.items()}
Permintaan.model_validate(CONTOH)  # contoh harus selalu lolos skema

# Peserta pendamping. cek_sinyal.fitur_peserta memanggil Series.map dengan pemeta bertanggal
# (klaim besar pertama, status aktif pertama). pandas gagal bila pemeta itu kosong
# ("Cannot cast DatetimeArray to dtype float64"), yaitu bila tidak satu pun peserta dalam
# permintaan punya klaim besar atau status aktif. Di data penuh itu tidak pernah terjadi.
# Supaya cek_sinyal.py tidak diubah, setiap permintaan ditemani satu peserta pendamping
# tetap (riwayat P-014822 di atas, dengan id sendiri) yang hasilnya dibuang. Fitur satu
# peserta tidak bergantung pada peserta lain: diuji, 4 x 50 = 200 x 1 = daftar_kerja.parquet.
PENDAMPING = "__pendamping__"
_PENDAMPING = {nama: [{**b, "id_peserta": PENDAMPING} for b in isi
                      if b["id_peserta"] == "P-014822"] for nama, isi in CONTOH.items()}
_PENDAMPING["dtsen"] = [dict(id_peserta=PENDAMPING, rentang_desil="6-10",
                             tgl_pemutakhiran="2025-01-01")]


# ---------------------------------------------------------------- aplikasi
DESKRIPSI = f"""
Triase peserta **PBPU/BP mandiri** yang menunggak ke satu rute tindakan, dengan alasan
yang bisa dibaca petugas.

**Tanggal potong tetap 31 Desember 2025.** Tunggakan dan fitur dihitung per
tanggal itu. Riwayat bertanggal sesudahnya ditolak (422).

- Logika tidak ditulis ulang: rute, alasan, dan fitur dari `cek_sinyal.py`; skor urutan
  dari `bukti/skor_verifikasi.py`. Hasil per peserta sama dengan aplikasi
  (`app_data/daftar_kerja.parquet`).
- Tanpa label dan tanpa LLM. Kolom di luar skema, termasuk kolom label, ditolak.
- Peserta DTSEN desil 1-5 tidak pernah masuk rute verifikasi. Diperiksa di setiap
  permintaan; bila terlanggar, API berhenti dengan galat 500 tanpa hasil.
- Rute verifikasi adalah daftar periksa riwayat untuk petugas, bukan sanksi.
- PPU, PBI, dan PBPU/BP-Pemda di luar cakupan (Perpres 59/2024 Ps. 42 ayat 7-8) dan
  dilaporkan di `di_luar_cakupan`.
- 1-{MAKS_PESERTA} peserta per permintaan. Hasil satu peserta tidak bergantung pada peserta
  lain dalam permintaan yang sama.
- Contoh payload: data sintetis (`generate_data.py --seed 2026`), bukan data peserta nyata.
"""

app = FastAPI(
    title="TEPAT API", version="1.0", description=DESKRIPSI,
    # demo satu klik: endpoint terbuka, contoh sudah terisi, tinggal Execute
    swagger_ui_parameters={"tryItOutEnabled": True, "docExpansion": "full",
                           "defaultModelsExpandDepth": -1},
)


@app.get("/", include_in_schema=False)
def ke_docs():
    return RedirectResponse("/docs")


@app.post("/triase", response_model=Jawaban,
          summary=f"Triase 1-{MAKS_PESERTA} peserta per {TANGGAL_POTONG:%d-%m-%Y}")
def post_triase(permintaan: Permintaan = Body(openapi_examples={"data_sintetis": {
        "summary": "4 peserta data sintetis seed 2026, satu per rute", "value": CONTOH}})):
    return nilai_triase(permintaan)
