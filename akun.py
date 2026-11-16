"""Akun demo TEPAT: peran Pusat dan Cabang. Tanpa kata sandi, semua data sintetis.

Untuk pilot, masuk lewat SSO BPJS (di luar prototipe ini). Akun tersimpan di st.session_state["_akun"]
(kunci akun). Keputusan petugas ada di st.session_state["_keputusan"] dan TIDAK terhapus saat ganti akun.
"""
import streamlit as st

KUNCI = "_akun"

# Pembagian wilayah ilustratif, data sintetis. Peserta demo P-002329 (W06), P-005882 (W29), P-004192 (W36)
# ada di Kantor Cabang A. Empat cabang membagi 40 wilayah (W01..W40), masing-masing 10.
_CABANG_A = ["W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08", "W29", "W36"]
_CABANG_B = ["W09", "W10", "W11", "W12", "W13", "W14", "W15", "W16", "W17", "W18"]
_CABANG_C = ["W19", "W20", "W21", "W22", "W23", "W24", "W25", "W26", "W27", "W28"]
_CABANG_D = ["W30", "W31", "W32", "W33", "W34", "W35", "W37", "W38", "W39", "W40"]
SEMUA_WILAYAH = [f"W{i:02d}" for i in range(1, 41)]
assert sorted(_CABANG_A + _CABANG_B + _CABANG_C + _CABANG_D) == SEMUA_WILAYAH

AKUN = {
    "pusat": dict(nama="Kantor Pusat · Manajemen Kolektibilitas", peran="pusat", wilayah=SEMUA_WILAYAH),
    "cabang_a": dict(nama="Kantor Cabang A (contoh)", peran="cabang", wilayah=_CABANG_A),
    "cabang_b": dict(nama="Kantor Cabang B (contoh)", peran="cabang", wilayah=_CABANG_B),
    "cabang_c": dict(nama="Kantor Cabang C (contoh)", peran="cabang", wilayah=_CABANG_C),
    "cabang_d": dict(nama="Kantor Cabang D (contoh)", peran="cabang", wilayah=_CABANG_D),
}
PERAN = {"pusat": "Pusat", "cabang": "Cabang"}


def kunci_aktif() -> str | None:
    k = st.session_state.get(KUNCI)
    return k if k in AKUN else None


def aktif() -> dict | None:
    k = kunci_aktif()
    return AKUN[k] if k else None


def adalah_pusat() -> bool:
    a = aktif()
    return bool(a) and a["peran"] == "pusat"


def adalah_cabang() -> bool:
    a = aktif()
    return bool(a) and a["peran"] == "cabang"


def nama_akun() -> str:
    a = aktif()
    return a["nama"] if a else ""


def wilayah_akun() -> list[str]:
    a = aktif()
    return list(a["wilayah"]) if a else []


def wilayah_efektif(pilihan: list[str]) -> list[str]:
    """Wilayah yang dipakai menyaring data. Pusat: pilihan apa adanya (kosong = semua). Cabang: pilihan
    yang masih di wilayahnya; kosong = semua wilayah cabang itu."""
    if adalah_cabang():
        sah = [w for w in pilihan if w in set(wilayah_akun())]
        return sah or wilayah_akun()
    return list(pilihan)


def boleh_peserta(kode_wilayah: str) -> bool:
    return adalah_pusat() or kode_wilayah in set(wilayah_akun())


def masuk(kunci: str) -> None:
    """Mulai sesi sebagai akun `kunci`. Pilihan filter akun sebelumnya dibuang supaya tidak bocor antar akun;
    keputusan yang sudah disimpan dan kapasitas k tetap."""
    st.session_state[KUNCI] = kunci
    for k in ("f_wilayah", "_pid_terakhir", "cari_id"):
        st.session_state.pop(k, None)
    st.session_state["f_wilayah"] = []


def keluar() -> None:
    st.session_state[KUNCI] = None


def pita() -> None:
    """Pita di atas setiap halaman: nama akun, peran, tombol Ganti akun."""
    a = aktif()
    if not a:
        return
    if a["peran"] == "pusat":
        ket = "Semua wilayah"
    else:
        ket = f"{len(a['wilayah'])} wilayah: {', '.join(a['wilayah'])}"
    c1, c2 = st.columns([6, 1.5], vertical_alignment="center")
    c1.html(f'<div class="tp-pita"><span class="tp-chip tp-peran-{a["peran"]}">{PERAN[a["peran"]]}</span>'
            f'<b>{_e(a["nama"])}</b><span class="ket">{_e(ket)}</span></div>')
    c2.button("Ganti akun", icon=":material/switch_account:", key="ganti_akun", on_click=keluar,
              width="stretch")


def _e(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
