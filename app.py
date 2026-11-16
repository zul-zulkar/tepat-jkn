"""Aplikasi TEPAT (Streamlit). Jalankan:  streamlit run app.py

Hanya membaca app_data/ (dibuat siapkan_app.py), kecuali halaman Keadilan yang juga membaca
bukti/hasil/skor_verifikasi.csv dan beban_strata.csv (tanpa label). Tidak melatih model saat dibuka.
Tema dan font: .streamlit/config.toml. Bagian bersama: tepat_ui.py. Logo: static/logo/.
"""
import streamlit as st

import akun
import tepat_ui as ui

st.set_page_config(page_title="TEPAT", page_icon="static/logo/tepat-mark.svg", layout="wide",
                   initial_sidebar_state="collapsed")
st.logo("static/logo/tepat-logo.svg", size="large")
ui.pasang_gaya()

# ---------------------------------------------------------------- akun demo (tanpa kata sandi)
# tautan langsung untuk juri: ?akun=pusat atau ?akun=cabang_a
_langsung = st.query_params.get("akun")
if _langsung is not None:
    if akun.kunci_aktif() is None and _langsung in akun.AKUN:
        akun.masuk(_langsung)
    del st.query_params["akun"]

if akun.kunci_aktif() is None:
    daftar = [st.Page(ui.HALAMAN_MASUK, title="Masuk", icon=":material/login:", url_path="masuk", default=True)]
else:
    daftar = [
        st.Page(ui.HALAMAN_DAFTAR, title="Daftar kerja", icon=":material/checklist:",
                url_path="daftar-kerja", default=True),
        st.Page(ui.HALAMAN_PROFIL, title="Profil peserta", icon=":material/person:",
                url_path="profil"),
    ]
    if akun.adalah_pusat():  # kantor cabang hanya mendapat dua halaman kerja
        daftar += [
            st.Page(ui.HALAMAN_KEBIJAKAN, title="Kebijakan", icon=":material/gavel:", url_path="kebijakan"),
            st.Page(ui.HALAMAN_KEADILAN, title="Keadilan", icon=":material/balance:", url_path="keadilan"),
        ]
halaman = st.navigation(daftar, position="top")
akun.pita()
halaman.run()
