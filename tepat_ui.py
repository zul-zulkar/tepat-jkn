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

# ---------------------------------------------------------------- label dan warna
# Warna sama dengan .streamlit/config.toml.
WARNA = dict(tinta="#17263A", tinta2="#4A5A6C", tinta3="#7A8897", garis="#D9E0E7",
             permukaan="#F2F5F7", utama="#0B6E68")

RUTE = {  # urutan = urutan tampil
    "verifikasi_pola_reaktivasi": dict(
        nama="Verifikasi pola reaktivasi", pendek="Verifikasi", warna="#B4650E",
        arti="Aktif kembali tak lama sebelum klaim besar, berulang. Petugas memeriksa riwayatnya "
             "sebelum menindaklanjuti. Rute ini bukan tuduhan."),
    "rujuk_cek_kelayakan_PBI": dict(
        nama="Rujuk cek kelayakan PBI", pendek="Cek PBI", warna="#2C5C9E",
        arti="Menunggak dan tercatat di DTSEN desil 1–5. Peserta dirujuk untuk dicek "
             "kelayakannya sebagai penerima bantuan iuran."),
    "pengingat_autodebet_REHAB": dict(
        nama="Pengingat, autodebet, REHAB", pendek="Pengingat", warna="#3D7D44",
        arti="Sering nonaktif lalu melunasi sendiri, dan jarang terkait klaim. Cukup pengingat, "
             "tawaran autodebet, atau cicilan REHAB."),
    "nonaktif_lama_tanpa_sinyal": dict(
        nama="Nonaktif lama", pendek="Nonaktif lama", warna="#6A7785",
        arti="Menunggak lama tanpa pernah aktif kembali dan tanpa sinyal lain. "
             "Kemampuan bayarnya perlu diverifikasi."),
    "tanpa_tindakan": dict(
        nama="Tanpa tindakan", pendek="", warna="#A9B3BE",
        arti="Tidak ada pola pembayaran yang memerlukan tindakan."),
}
RUTE_AKSI = [r for r in RUTE if r != "tanpa_tindakan"]

SARAN = {
    "pengingat_H-5_dan_tawaran_autodebet": "Pengingat H-5 dan tawaran autodebet",
    "cek_kelayakan_PBI": "Cek kelayakan PBI",
    "pengingat_saldo_autodebet": "Pengingat saldo autodebet",
}
WARNA_EW = "#6B4C9A"

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
    besar = besar[["tgl_masuk"]].sort_values("tgl_masuk")
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
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding-top: 4.6rem; padding-bottom: 4rem; }
h1, h2, h3 { letter-spacing: -0.01em; }
p, li { font-feature-settings: "tnum" 1; }

.tp-kepala { margin: 0 0 1.4rem; }
.tp-kepala h1 { font-size: 1.75rem; font-weight: 700; margin: 0 0 .35rem; padding: 0; line-height: 1.2; }
.tp-kepala p { color: #4A5A6C; margin: 0; max-width: 68ch; line-height: 1.5; }
.tp-cap { color: #7A8897; font-size: .82rem; margin-top: .45rem; }
.tp-cap b { color: #4A5A6C; font-weight: 600; }

.tp-strip { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #E4E9EE; margin: .2rem 0 .7rem; }
.tp-strip span { display: block; height: 100%; }
.tp-legenda { display: flex; flex-wrap: wrap; gap: .35rem 1.4rem; margin: 0 0 .9rem; font-size: .88rem; color: #4A5A6C; }
.tp-legenda span { display: inline-flex; align-items: baseline; gap: .45rem; }
.tp-legenda i { width: 9px; height: 9px; border-radius: 2px; display: inline-block; transform: translateY(1px); }
.tp-legenda b { color: #17263A; font-weight: 600; }

.tp-ket { color: #4A5A6C; font-size: .9rem; margin: 0 0 .8rem; max-width: 80ch; line-height: 1.5; }

.tp-id { font-size: 2rem; font-weight: 600; letter-spacing: -0.01em; line-height: 1.1; margin: .2rem 0 .3rem; }
.tp-ringkas { color: #4A5A6C; margin: 0 0 1.1rem; }
.tp-fakta { padding: 0; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0; margin: 0 0 1.6rem;
            border-top: 1px solid #D9E0E7; border-bottom: 1px solid #D9E0E7; }
.tp-fakta div { padding: .75rem .9rem .8rem 0; }
.tp-fakta div + div { padding-left: .9rem; border-left: 1px solid #E4E9EE; }
.tp-fakta dt { font-size: .78rem; color: #7A8897; margin: 0 0 .2rem; }
.tp-fakta dd { margin: 0; font-size: 1rem; font-weight: 600; color: #17263A; }
.tp-fakta dd small { display: block; font-weight: 400; color: #4A5A6C; font-size: .82rem; margin-top: .1rem; }
@media (max-width: 900px) {
  .tp-fakta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tp-fakta div, .tp-fakta div + div { padding: .65rem .6rem; border-left: 0; border-top: 1px solid #E4E9EE; }
}

.tp-rute { border-left: 3px solid var(--c); padding: .15rem 0 .2rem 1rem; margin: 0 0 1rem; }
.tp-rute .sumber { font-size: .8rem; color: #7A8897; margin: 0 0 .15rem; }
.tp-rute .nama { font-size: 1.15rem; font-weight: 650; color: var(--c); margin: 0 0 .3rem; }
.tp-rute .alasan { font-size: 1rem; color: #17263A; margin: 0 0 .35rem; line-height: 1.45; }
.tp-rute .arti { font-size: .88rem; color: #4A5A6C; margin: 0; line-height: 1.5; max-width: 76ch; }

.tp-angka { display: flex; flex-wrap: wrap; gap: .3rem 1.6rem; margin: .5rem 0 0; font-size: .88rem; color: #4A5A6C; }
.tp-angka b { color: #17263A; font-weight: 600; }

.tp-kontrib { margin: .6rem 0 0; display: grid; gap: .35rem; max-width: 560px; }
.tp-kontrib div { display: grid; grid-template-columns: 1fr 120px; gap: .8rem; align-items: center; font-size: .86rem; color: #4A5A6C; }
.tp-kontrib s { display: block; height: 6px; border-radius: 3px; background: #6B4C9A; text-decoration: none; }

.tp-legenda-lini { display: flex; flex-wrap: wrap; gap: .3rem 1.3rem; font-size: .82rem; color: #4A5A6C; margin: .1rem 0 1.4rem; }
.tp-legenda-lini span { display: inline-flex; align-items: center; gap: .4rem; }
.tp-legenda-lini i { display: inline-block; }

.tp-pagar { font-size: .82rem; color: #7A8897; margin: .4rem 0 0; }
</style>
"""


def pasang_gaya() -> None:
    st.html(CSS)


def kepala(judul: str, ket: str) -> None:
    m = manifest()
    st.html(
        f'<div class="tp-kepala"><h1>{e(judul)}</h1><p>{e(ket)}</p>'
        f'<div class="tp-cap"><b>Data sintetis.</b> Triase per {tgl(m["triase_per_tanggal"])}, '
        f'peringatan dini {BULAN_PANJANG[int(m["ew_bulan_operasional"][5:]) - 1]} '
        f'{m["ew_bulan_operasional"][:4]}.</div></div>')


def strip_rute(hitung: dict[str, int]) -> str:
    total = sum(hitung.values()) or 1
    seg = "".join(f'<span style="width:{100 * n / total:.3f}%;background:{RUTE[r]["warna"]}" '
                  f'title="{e(RUTE[r]["nama"])}"></span>' for r, n in hitung.items() if n)
    leg = "".join(f'<span><i style="background:{RUTE[r]["warna"]}"></i>{e(RUTE[r]["nama"])} '
                  f'<b>{angka(n)}</b></span>' for r, n in hitung.items())
    return f'<div class="tp-strip" aria-hidden="true">{seg}</div><div class="tp-legenda">{leg}</div>'
