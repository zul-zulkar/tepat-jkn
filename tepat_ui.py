"""Bagian bersama aplikasi TEPAT: baca app_data/, label bahasa manusia, format angka Indonesia, gaya.

Aplikasi hanya MEMBACA app_data/ (dibuat siapkan_app.py). Tidak ada pelatihan model di sini.
evaluasi_label.parquet sengaja tidak dibaca di modul ini: label hanya boleh muncul di halaman Evaluasi.
"""
from __future__ import annotations

import ast
import html
import json
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import streamlit as st

from ikon import ikon

APP_DATA = Path(__file__).parent / "app_data"


def _konstanta(nama_file: str, *nama: str) -> list:
    """Baca konstanta dari skrip pipeline tanpa meng-import-nya. Import cek_sinyal ikut memuat
    matplotlib (±140 MB), terlalu mahal untuk batas memori Streamlit Community Cloud."""
    pohon = ast.parse((Path(__file__).parent / nama_file).read_text(encoding="utf-8"))
    nilai = {n.targets[0].id: ast.literal_eval(n.value) for n in pohon.body
             if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Name) and n.targets[0].id in nama}
    return [nilai[x] for x in nama]


# satu sumber aturan "klaim besar": konstanta yang sama dengan cek_sinyal.py
KLAIM_BESAR, JEDA_KAIT = _konstanta("cek_sinyal.py", "KLAIM_BESAR", "JEDA_KAIT")
HALAMAN_DAFTAR = "halaman/daftar_kerja.py"
HALAMAN_PROFIL = "halaman/profil_peserta.py"
HALAMAN_KEBIJAKAN = "halaman/kebijakan.py"
HALAMAN_KEADILAN = "halaman/keadilan.py"

# ---------------------------------------------------------------- label dan warna
# Palet deck proposal TEPAT; sama dengan .streamlit/config.toml.
WARNA = dict(tinta="#12302A", tinta2="#3D4B46", tinta3="#5E6B66", garis="#DCDFD7", permukaan="#ECEBE4",
             kartu="#FCFCF9", utama="#17704D", utama_lembut="#E1EEE6", mint="#9FD8BC")

RUTE = {  # urutan = urutan tampil. ikon = Lucide (HTML), mi = Material Symbols (widget Streamlit)
    "verifikasi_pola_reaktivasi": dict(
        nama="Verifikasi pola reaktivasi", pendek="Verifikasi", warna="#9A3F12", lembut="#F6E4D6",
        ikon="search-check", mi=":material/fact_check:",
        arti="Aktif kembali tak lama sebelum klaim besar, berulang. Petugas memeriksa riwayatnya "
             "sebelum menindaklanjuti. Rute ini bukan tuduhan."),
    "rujuk_cek_kelayakan_PBI": dict(
        nama="Rujuk cek kelayakan PBI", pendek="Cek PBI", warna="#2F5D8C", lembut="#DCE6F1",
        ikon="hand-heart", mi=":material/volunteer_activism:",
        arti="Menunggak dan tercatat di DTSEN desil 1–5. Peserta dirujuk untuk dicek "
             "kelayakannya sebagai penerima bantuan iuran."),
    "pengingat_autodebet_REHAB": dict(
        nama="Pengingat, autodebet, REHAB", pendek="Pengingat", warna="#17704D", lembut="#E1EEE6",
        ikon="bell-ring", mi=":material/notifications_active:",
        arti="Sering nonaktif lalu melunasi sendiri, dan jarang terkait klaim. Cukup pengingat, "
             "tawaran autodebet, atau cicilan REHAB."),
    "nonaktif_lama_tanpa_sinyal": dict(
        nama="Nonaktif lama", pendek="Nonaktif lama", warna="#5E6B66", lembut="#E6E4DC",
        ikon="hourglass", mi=":material/hourglass_empty:",
        arti="Menunggak lama tanpa pernah aktif kembali dan tanpa sinyal lain. "
             "Kemampuan bayarnya perlu diverifikasi."),
    "tanpa_tindakan": dict(
        nama="Tanpa tindakan", pendek="", warna="#8F9993", lembut="#ECEBE4",
        ikon="circle-check-big", mi=":material/check_circle:",
        arti="Tidak ada pola pembayaran yang memerlukan tindakan."),
}
RUTE_AKSI = [r for r in RUTE if r != "tanpa_tindakan"]

PERINGATAN_DINI = "peringatan_dini"

# Satu peserta, satu tindakan (disepakati 24 Okt 2026): verifikasi > cek PBI > peringatan dini > pengingat.
# Nonaktif lama diletakkan setelah cek PBI; tidak pernah bentrok dengan peringatan dini karena
# peringatan dini hanya untuk peserta aktif. Dihitung saat aplikasi berjalan karena isi daftar
# peringatan dini bergantung pada kapasitas k dan filter wilayah.
PRIORITAS = ["verifikasi_pola_reaktivasi", "rujuk_cek_kelayakan_PBI", "nonaktif_lama_tanpa_sinyal",
             PERINGATAN_DINI, "pengingat_autodebet_REHAB"]


def tindakan_utama(rute: pd.Series, masuk_ew: pd.Series) -> pd.Series:
    """Tindakan utama tiap peserta menurut PRIORITAS. masuk_ew: True bila masuk daftar peringatan dini."""
    hasil = pd.Series("tanpa_tindakan", index=rute.index)
    for t in reversed(PRIORITAS):  # prioritas tertinggi ditulis terakhir supaya menang
        kena = masuk_ew if t == PERINGATAN_DINI else rute.eq(t)
        hasil = hasil.mask(kena.astype(bool).values, t)
    return hasil


# Istilah untuk pengguna internal BPJS (disepakati 24 Okt): daftar hasil model peringatan dini disebut
# "berisiko menunggak 3 bulan ke depan". Tidak dipakai di pesan ke peserta.
EW_NAMA = "Berisiko menunggak"
EW_NAMA_PANJANG = "Berisiko menunggak 3 bulan ke depan"


def nama_tindakan(t: str) -> str:
    return "Pencegahan untuk peserta berisiko menunggak" if t == PERINGATAN_DINI else RUTE[t]["nama"]


SARAN = {
    "pengingat_H-5_dan_tawaran_autodebet": "Pengingat H-5 dan tawaran autodebet",
    "cek_kelayakan_PBI": "Cek kelayakan PBI",
    "pengingat_saldo_autodebet": "Pengingat saldo autodebet",
}
WARNA_EW, EW_LEMBUT, EW_IKON, EW_MI = "#9A5F0E", "#F5E6C8", "trending-up", ":material/trending_up:"

STATUS = {"aktif": "Aktif", "nonaktif": "Nonaktif", "masa_tunggu": "Masa tunggu"}
DESIL = {"1-5": "Desil 1–5", "6-10": "Desil 6–10", "tidak_padan": "Tidak padan"}

FITUR_EW = {
    "bulan_nonaktif_12": ("Bulan nonaktif dalam 12 bulan terakhir", "{:.0f} bulan"),
    "n_reaktivasi_12": ("Aktif kembali dalam 12 bulan terakhir", "{:.0f} kali"),
    "bulan_telat_dibayar_12": ("Iuran telat yang dilunasi, 12 bulan terakhir", "{:.0f} bulan"),
    "log_rasio_klaim_iuran_12": ("Rasio klaim terhadap iuran, 12 bulan terakhir", None),
    "log_masa_kepesertaan": ("Masa kepesertaan", None),
    "pernah_nonaktif": ("Pernah nonaktif", "ya/tidak"),
    "aktif_kembali_3bln": ("Baru aktif kembali dalam 3 bulan", "ya/tidak"),
    "klaim_besar_bulan_lalu": ("Klaim besar bulan lalu", "ya/tidak"),
    "klaim_besar_2_3bln": ("Klaim besar 2–3 bulan lalu", "ya/tidak"),
    "klaim_besar_4_12bln": ("Klaim besar 4–12 bulan lalu", "ya/tidak"),
    "autodebet": ("Memakai autodebet", "ya/tidak"),
    "kelas_1": ("Kelas 1", "ya/tidak"),
    "kelas_2": ("Kelas 2", "ya/tidak"),
}

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
                 "September", "Oktober", "November", "Desember"]


# ---------------------------------------------------------------- format Indonesia
def angka(x, desimal: int = 0) -> str:
    s = f"{x:,.{desimal}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def rp(x) -> str:
    return "Rp" + angka(round(float(x)))


def persen(x, desimal: int = 1) -> str:
    return angka(100 * x, desimal) + "%"


def tgl(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def bulan_tahun(periode: str) -> str:
    """'2025-12' -> 'Des 2025'."""
    th, bl = periode.split("-")
    return f"{BULAN[int(bl) - 1]} {th}"


def alasan_rapi(s: str) -> str:
    """Hanya tampilan: '<=' jadi '≤', '1.48x' jadi '1,48×', 'bln' jadi 'bulan'. Data tidak diubah."""
    if not isinstance(s, str) or not s:
        return ""
    s = s.replace("<=", "≤").replace(">=", "≥")
    s = re.sub(r"(\d+)\.(\d+)x\b", r"\1,\2×", s)
    s = re.sub(r"\bbln\b", "bulan", s)
    return s[:1].upper() + s[1:]


def kecil(s: str) -> str:
    """Huruf pertama kecil saja, supaya singkatan seperti H-5 dan PBI tetap utuh di tengah kalimat."""
    return s[:1].lower() + s[1:] if s else s


KANAL = {"autodebet": "Autodebet", "va_bank": "VA bank", "minimarket": "Minimarket",
         "mobile_jkn": "Mobile JKN"}


def e(s) -> str:
    return html.escape(str(s))


# ---------------------------------------------------------------- data
def _baca(nama: str) -> pd.DataFrame:
    """Tidak di-cache: yang di-cache adalah tabel turunannya, supaya data tidak tersimpan dua kali."""
    if nama == "evaluasi_label":
        raise ValueError("Label hanya untuk halaman Evaluasi.")
    return pd.read_parquet(APP_DATA / f"{nama}.parquet")


@st.cache_resource(show_spinner=False)
def manifest() -> dict:
    return json.loads((APP_DATA / "manifest.json").read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Membaca data…")
def tabel_peserta() -> pd.DataFrame:
    """Satu baris per peserta mandiri: atribut, status per 31 Des 2025, rute triase, posisi peringatan dini."""
    p = _baca("peserta")
    dk = _baca("daftar_kerja").drop(columns=["rentang_desil"])
    ew = _baca("ew_daftar")
    st_ = _baca("linimasa_status").sort_values(["id_peserta", "tgl_mulai"])
    akhir = st_.groupby("id_peserta").tail(1).set_index("id_peserta")["status"]

    t = p.merge(dk, on="id_peserta", how="left", validate="1:1")
    t["status_akhir"] = t["id_peserta"].map(akhir).fillna("nonaktif")
    e_ = ew[["id_peserta", "peringkat", "skor", "masuk_daftar", "alasan", "saran_intervensi"]].rename(
        columns={"peringkat": "ew_peringkat", "skor": "ew_skor", "masuk_daftar": "ew_daftar_kanonik",
                 "alasan": "ew_alasan", "saran_intervensi": "ew_saran"})
    t = t.merge(e_, on="id_peserta", how="left", validate="1:1")
    t["urut_rute"] = t["rute"].map({r: i for i, r in enumerate(RUTE)})
    pa.default_memory_pool().release_unused()
    return t


@st.cache_resource(show_spinner=False)
def _indeks(nama: str) -> pd.DataFrame:
    d = _baca(nama)
    d["id_peserta"] = d["id_peserta"].astype("category")
    d = d.set_index("id_peserta").sort_index()
    pa.default_memory_pool().release_unused()
    return d


def linimasa(nama: str, pid: str) -> pd.DataFrame:
    d = _indeks(nama)
    if pid not in d.index:
        return d.iloc[0:0].reset_index()
    return d.loc[[pid]].reset_index()


@st.cache_resource(show_spinner=False)
def bunching() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(harian, ringkasan) uji lonjakan hari-45. Ringkasan berindeks cara_masuk: 'terjadwal', 'IGD'."""
    return _baca("bunching_harian"), _baca("bunching_ringkasan").set_index("cara_masuk")


@st.cache_resource(show_spinner=False)
def ew_baris() -> pd.DataFrame:
    return _baca("ew_daftar").set_index("id_peserta")


def daftar_ew(t: pd.DataFrame, wilayah: list[str], k_persen: float) -> pd.DataFrame:
    """Peserta aktif yang dinilai model, di wilayah terpilih, urut skor, dipotong ke k% (aturan k sama
    dengan siapkan_app.py: max(1, round(n * k / 100)))."""
    d = t[t["ew_peringkat"].notna()]
    if wilayah:
        d = d[d["kode_wilayah"].isin(wilayah)]
    d = d.sort_values("ew_peringkat")
    k = max(1, int(round(len(d) * k_persen / 100))) if len(d) else 0
    return d.head(k), len(d)


def pasangan_reaktivasi_klaim(reakt: pd.DataFrame, klaim: pd.DataFrame) -> pd.DataFrame:
    """Tiap reaktivasi dipasangkan dengan klaim besar PERTAMA pada/sesudah tanggal reaktivasi,
    sama dengan cek_sinyal.fitur_peserta (merge_asof forward). terkait = jarak <= JEDA_KAIT hari."""
    if reakt.empty:
        return pd.DataFrame(columns=["tgl_reakt", "tgl_masuk", "hari", "terkait"])
    besar = klaim[(klaim["jenis_layanan"] == "RITL") | (klaim["biaya_klaim"] >= KLAIM_BESAR)]
    besar = besar[["tgl_masuk", "jenis_layanan", "cara_masuk"]].sort_values("tgl_masuk")
    r = pd.merge_asof(reakt[["tgl_reakt", "bulan_tertunggak"]].sort_values("tgl_reakt"), besar,
                      left_on="tgl_reakt", right_on="tgl_masuk", direction="forward")
    r["hari"] = (r["tgl_masuk"] - r["tgl_reakt"]).dt.days
    r["terkait"] = r["hari"].le(JEDA_KAIT)
    return r


# ---------------------------------------------------------------- keputusan petugas (sesi)
def keputusan() -> dict:
    """{id_peserta: dict(...)} keputusan terakhir per peserta, hanya untuk sesi ini."""
    return st.session_state.setdefault("_keputusan", {})


def label_keputusan(pid: str) -> str:
    k = keputusan().get(pid)
    return "" if not k else ("Disetujui" if k["keputusan"] == "setuju" else "Ditolak")


def pertahankan(*kunci: str) -> None:
    """Nilai widget tetap ada saat pindah halaman (Streamlit menghapus state widget yang tidak tampil)."""
    for k in kunci:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def normalkan_id(s: str) -> str:
    s = (s or "").strip().upper().replace(" ", "")
    if re.fullmatch(r"\d{1,6}", s):
        return f"P-{int(s):06d}"
    if re.fullmatch(r"P-?\d{1,6}", s):
        return f"P-{int(s.replace('P', '').replace('-', '')):06d}"
    return s


# ---------------------------------------------------------------- tampilan
CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding-top: 4.4rem; padding-bottom: 4rem; }
[data-testid="stHeader"] { background: #F6F5F0; border-bottom: 1px solid #DCDFD7; }
h1, h2, h3 { letter-spacing: -0.015em; }
p, li { font-feature-settings: "tnum" 1; }
.tp-ikon { flex: none; vertical-align: -3px; }

.tp-kepala { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem .7rem; margin: .1rem 0 1.1rem; }
.tp-kepala h1 { font-size: 1.85rem; font-weight: 800; color: #12302A; margin: 0; padding: 0; line-height: 1.15; }
.tp-chip { display: inline-flex; align-items: center; gap: .35rem; font-size: .78rem; font-weight: 600;
           padding: .28rem .7rem; border-radius: 999px; background: #ECEBE4; color: #3D4B46; white-space: nowrap; }

.tp-info { display: inline-block; position: relative; vertical-align: middle; }
.tp-info > summary { list-style: none; cursor: pointer; display: inline-grid; place-items: center;
                     width: 28px; height: 28px; border-radius: 50%; color: #5E6B66; }
.tp-info > summary::-webkit-details-marker { display: none; }
.tp-info > summary:hover, .tp-info[open] > summary { background: #E1EEE6; color: #17704D; }
.tp-info > summary:focus-visible { outline: 2px solid #17704D; outline-offset: 2px; }
.tp-info > div { position: absolute; z-index: 60; top: 34px; left: 0; width: min(380px, 78vw);
                 padding: .75rem .9rem; background: #FCFCF9; border: 1px solid #DCDFD7; border-radius: 12px;
                 box-shadow: 0 8px 24px rgba(18, 48, 42, .12); font-size: .86rem; font-weight: 400;
                 line-height: 1.55; color: #3D4B46; text-align: left; white-space: normal; }
.tp-info.kanan > div { left: auto; right: 0; }

.tp-kartu-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: .7rem; margin: .2rem 0 1rem; }
.tp-kartu { background: #FCFCF9; border: 1px solid #DCDFD7; border-radius: 14px; padding: .8rem .95rem;
            display: flex; gap: .75rem; align-items: center; transition: opacity .15s; }
.tp-kartu.mati { opacity: .4; }
.tp-bulat { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center;
            background: var(--l); color: var(--c); flex: none; }
.tp-kartu .n { font-size: 1.4rem; font-weight: 700; color: #12302A; line-height: 1.1; }
.tp-kartu .l { font-size: .8rem; color: #5E6B66; margin-top: .12rem; line-height: 1.3; }

.tp-id { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem .7rem; margin: .3rem 0 1rem; }
.tp-id h1 { font-size: 2.1rem; font-weight: 700; margin: 0; padding: 0; color: #12302A; line-height: 1.1; }

.tp-fakta { padding: 0; margin: 0 0 1.2rem; display: grid; gap: .6rem; grid-template-columns: repeat(6, minmax(0, 1fr)); }
.tp-fakta > div { background: #FCFCF9; border: 1px solid #DCDFD7; border-radius: 12px; padding: .7rem .8rem; }
.tp-fakta .dt { display: flex; align-items: center; gap: .35rem; font-size: .76rem; color: #5E6B66; margin: 0 0 .25rem; }
.tp-fakta .dd { margin: 0; font-size: 1.02rem; font-weight: 700; color: #12302A; }
.tp-fakta .dd small { display: block; font-weight: 400; color: #5E6B66; font-size: .78rem; margin-top: .1rem; }
@media (max-width: 900px) { .tp-fakta { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

.tp-tindakan { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem .8rem; padding: .75rem 1rem;
               border-radius: 14px; background: var(--l); margin: 0 0 1rem; color: #12302A; }
.tp-tindakan .tp-bulat { background: #FCFCF9; }
.tp-tindakan .lbl { font-size: .78rem; color: #3D4B46; }
.tp-tindakan .isi { font-size: 1.05rem; font-weight: 700; color: var(--c); }
.tp-tindakan .lain { font-size: .8rem; color: #3D4B46; }

.tp-panel { background: #FCFCF9; border: 1px solid #DCDFD7; border-radius: 14px; padding: .95rem 1.05rem; margin: 0 0 1rem; }
.tp-panel.tp-sekunder { opacity: .55; }
.tp-panel .atas { display: flex; align-items: center; gap: .7rem; margin: 0 0 .55rem; }
.tp-panel .sumber { font-size: .76rem; color: #5E6B66; margin: 0; }
.tp-panel .nama { font-size: 1.08rem; font-weight: 700; color: var(--c); margin: 0; line-height: 1.25; }
.tp-panel .atas .tp-info { margin-left: auto; }
.tp-panel .alasan { font-size: .95rem; color: #12302A; margin: 0 0 .55rem; line-height: 1.45; }
.tp-angka { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0; }
.tp-catatan { display: flex; gap: .5rem; align-items: flex-start; font-size: .85rem; color: #8A3B14;
              background: #F6E4D6; border-radius: 10px; padding: .55rem .7rem; margin: .65rem 0 0; line-height: 1.45; }

.tp-kontrib { margin: .65rem 0 0; display: grid; gap: .4rem; }
.tp-kontrib div { display: grid; grid-template-columns: 1fr 110px; gap: .8rem; align-items: center; font-size: .82rem; color: #3D4B46; }
.tp-kontrib s { display: block; height: 6px; border-radius: 3px; background: #9A5F0E; text-decoration: none; }

.tp-judul { display: flex; align-items: center; gap: .5rem; margin: 1.2rem 0 .4rem; }
.tp-judul h3 { font-size: 1.1rem; font-weight: 700; margin: 0; padding: 0; color: #12302A; }
.tp-legenda-lini { display: flex; flex-wrap: wrap; gap: .3rem 1.1rem; font-size: .78rem; color: #5E6B66; margin: .1rem 0 1.2rem; }
.tp-legenda-lini span { display: inline-flex; align-items: center; gap: .35rem; }
.tp-legenda-lini i { display: inline-block; }

/* halaman Kebijakan: panel grafik (st.container dengan key berawalan tpgrafik) */
[class*="st-key-tpgrafik"] { background: #FCFCF9; border-radius: 14px !important; padding: .95rem 1.05rem .7rem !important; }
.tp-grafik-kepala { display: flex; align-items: center; gap: .7rem; margin: 0 0 .1rem; }
.tp-grafik-kepala .nama { font-size: 1.02rem; font-weight: 700; color: var(--c); margin: 0; line-height: 1.25; }
.tp-grafik-kepala .sumber { font-size: .76rem; color: #5E6B66; margin: 0; }
.tp-grafik-kepala .vonis { margin-left: auto; }
.tp-jendela { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: .2rem 0 .3rem; }
.tp-jendela > div { border-radius: 10px; padding: .5rem .65rem; background: #F3F2EC; font-size: .8rem; color: #3D4B46; line-height: 1.4; }
.tp-jendela b { display: block; font-size: .95rem; color: #12302A; }
.tp-jendela .naik { color: #17704D; } .tp-jendela .turun { color: #9A3F12; }
.tp-catatan-kecil { font-size: .78rem; color: #5E6B66; margin: .2rem 0 0; line-height: 1.45; }
.tp-baca { margin: .2rem 0 0; padding: 0 0 0 1.1rem; color: #3D4B46; font-size: .92rem; line-height: 1.55; }
.tp-baca li { margin: 0 0 .35rem; }

/* halaman Keadilan: baris beban per kelompok. Batang = seluruh jalur, belah ketupat = yang diperiksa. */
.tp-beban { margin: .55rem 0 0; }
.tp-beban-r, .tp-beban-ax { display: grid; grid-template-columns: minmax(92px, 140px) minmax(0, 1fr) 104px; gap: .7rem; align-items: center; }
.tp-beban-r { padding: .42rem 0; border-top: 1px solid #ECEBE4; }
.tp-beban-r:first-child { border-top: 0; }
.tp-beban-r .nm { font-size: .86rem; font-weight: 600; color: #12302A; line-height: 1.25; }
.tp-beban-r .nm small { display: block; font-weight: 400; color: #5E6B66; font-size: .74rem; }
.tp-beban-r .nm .tp-chip { margin-top: .3rem; font-size: .7rem; padding: .18rem .5rem; white-space: normal; }
.tp-trek { position: relative; height: 28px; background: #F3F2EC; border-radius: 6px; }
.tp-trek .g { position: absolute; top: -3px; bottom: -3px; width: 0; border-left: 1.5px solid #8F9993; }
.tp-trek .g2 { border-left: 1.5px dashed #9A3F12; }
.tp-trek .br { position: absolute; left: 0; top: 6px; height: 16px; border-radius: 0 4px 4px 0; background: var(--wj); }
.tp-trek .dm { position: absolute; top: 50%; width: 13px; height: 13px; margin: -6.5px 0 0 -6.5px; transform: rotate(45deg);
               background: var(--wp); border: 2px solid #12302A; box-sizing: border-box; }
.tp-beban-r .ang { font-size: .8rem; line-height: 1.4; color: #3D4B46; text-align: right; }
.tp-beban-r .ang span { display: block; }
.tp-beban-r .ang small { font-size: .7rem; color: #5E6B66; }
.tp-beban-r .ang b { font-size: .95rem; font-weight: 700; }
.tp-beban-r .bagi { grid-column: 1 / -1; font-size: .74rem; line-height: 1.4; color: #5E6B66; margin-top: -.1rem; }
.tp-beban-r .bagi b { color: #3D4B46; font-weight: 600; }
.tp-beban-r .bagi em { font-style: normal; color: #9A3F12; }
.tp-trek-ax { position: relative; height: 1.2rem; font-size: .7rem; color: #5E6B66; }
.tp-trek-ax i { position: absolute; top: .15rem; transform: translateX(-50%); font-style: normal; white-space: nowrap; }
.tp-trek-ax i:first-child { transform: none; }
@media (max-width: 640px) { .tp-beban-r, .tp-beban-ax { grid-template-columns: minmax(80px, 110px) minmax(0, 1fr) 88px; gap: .45rem; } }
</style>
"""


def pasang_gaya() -> None:
    st.html(CSS)


def info(teks: str, kanan: bool = False, label: str = "Penjelasan") -> str:
    """Ikon info yang membuka/menutup penjelasan (HTML details, tanpa JavaScript). teks sudah aman/escaped."""
    return (f'<details class="tp-info{" kanan" if kanan else ""}"><summary aria-label="{e(label)}" '
            f'title="{e(label)}">{ikon("info", 18, "#5E6B66")}</summary><div>{teks}</div></details>')


def chip(teks: str, nama_ikon: str | None = None, warna: str | None = None, latar: str | None = None) -> str:
    gaya = (f' style="{f"color:{warna};" if warna else ""}{f"background:{latar};" if latar else ""}"'
            if (warna or latar) else "")
    return (f'<span class="tp-chip"{gaya}>{ikon(nama_ikon, 14, warna or "#3D4B46") if nama_ikon else ""}'
            f'{e(teks)}</span>')


def chip_data() -> str:
    m = manifest()
    return (chip("Data sintetis", "flask-conical")
            + info(f'Data buatan untuk prototipe, bukan data peserta asli. Triase per '
                   f'{tgl(m["triase_per_tanggal"])}; risiko menunggak dihitung untuk '
                   f'{BULAN_PANJANG[int(m["ew_bulan_operasional"][5:]) - 1]} {m["ew_bulan_operasional"][:4]}.',
                   kanan=True, label="Tentang data"))


def kepala(judul: str, penjelasan: str) -> None:
    st.html(f'<div class="tp-kepala"><h1>{e(judul)}</h1>{info(e(penjelasan))}'
            f'<span style="margin-left:auto;display:inline-flex;align-items:center;gap:.2rem">{chip_data()}</span></div>')


def kartu(item: list[dict]) -> str:
    """item: dict(ikon, c, l, n, label, mati=False)."""
    isi = "".join(
        f'<div class="tp-kartu{" mati" if k.get("mati") else ""}" style="--c:{k["c"]};--l:{k["l"]}">'
        f'<div class="tp-bulat">{ikon(k["ikon"], 20, k["c"])}</div>'
        f'<div><div class="n">{e(k["n"])}</div><div class="l">{e(k["label"])}</div></div></div>'
        for k in item)
    return f'<div class="tp-kartu-grid">{isi}</div>'


def judul_bagian(teks: str, nama_ikon: str, penjelasan: str | None = None) -> None:
    st.html(f'<div class="tp-judul">{ikon(nama_ikon, 20, WARNA["utama"])}<h3>{e(teks)}</h3>'
            + (info(e(penjelasan)) if penjelasan else "") + "</div>")
