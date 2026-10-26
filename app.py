"""Aplikasi TEPAT (Streamlit). Jalankan:  streamlit run app.py

Hanya membaca app_data/ (dibuat siapkan_app.py). Tidak melatih model saat dibuka.
Tema dan font: .streamlit/config.toml. Bagian bersama: tepat_ui.py. Logo: static/logo/.
"""
import streamlit as st

import tepat_ui as ui

st.set_page_config(page_title="TEPAT", page_icon="static/logo/tepat-mark.svg", layout="wide",
                   initial_sidebar_state="collapsed")
st.logo("static/logo/tepat-logo.svg", size="large")
ui.pasang_gaya()

halaman = st.navigation(
    [
        st.Page(ui.HALAMAN_DAFTAR, title="Daftar kerja", icon=":material/checklist:",
                url_path="daftar-kerja", default=True),
        st.Page(ui.HALAMAN_PROFIL, title="Profil peserta", icon=":material/person:",
                url_path="profil"),
        st.Page(ui.HALAMAN_KEBIJAKAN, title="Kebijakan", icon=":material/gavel:",
                url_path="kebijakan"),
    ],
    position="top",
)
halaman.run()
