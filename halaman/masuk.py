"""Halaman Masuk: pilih akun demo (tanpa kata sandi). Satu-satunya halaman sebelum ada akun."""
import streamlit as st

import akun
import tepat_ui as ui

# kapasitas dan filter tetap ada walau halaman lain tidak tampil (widgetnya hilang saat pindah halaman)
ui.pertahankan("f_k", "f_daftar", "f_rute", "f_nonaktif")

ui.kepala("Masuk", "Pilih akun demo. Pusat melihat semua wilayah dan menetapkan kapasitas; kantor cabang "
          "bekerja di wilayahnya dan mencatat keputusan.")

_, tengah, _ = st.columns([1, 2.2, 1])
with tengah:
    with st.container(border=True):
        ui.judul_bagian("Akun demo", "user-round")
        kunci = st.radio("Akun", list(akun.AKUN), key="pilih_akun",
                         format_func=lambda k: f'{akun.AKUN[k]["nama"]}'
                         + ("" if akun.AKUN[k]["peran"] == "pusat" else f' · {len(akun.AKUN[k]["wilayah"])} wilayah'),
                         label_visibility="collapsed")
        if st.button("Masuk", icon=":material/login:", type="primary", width="stretch", key="tombol_masuk"):
            akun.masuk(kunci)
            st.rerun()
        st.caption("Akun demo tanpa kata sandi, data sintetis. Untuk pilot: login lewat SSO BPJS.")
