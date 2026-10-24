"""Halaman Daftar kerja: dua daftar (triase pola bayar, peringatan dini), filter wilayah, rute, kapasitas k."""
import numpy as np
import pandas as pd
import streamlit as st

import tepat_ui as ui

FILTER = dict(f_wilayah=[], f_daftar="triase", f_rute=list(ui.RUTE_AKSI), f_nonaktif=False, f_k=5)
ui.pertahankan(*FILTER)
for k, v in FILTER.items():
    st.session_state.setdefault(k, v)

T = ui.tabel_peserta()

ui.kepala("Daftar kerja",
          "Siapa yang ditangani bulan ini, lewat jalur apa, dan kenapa. "
          "Pilih satu baris untuk membuka profil peserta.")

# ---------------------------------------------------------------- filter bersama
wilayah = st.multiselect("Wilayah", sorted(T["kode_wilayah"].unique()), key="f_wilayah",
                         placeholder="Semua wilayah")
T_w = T[T["kode_wilayah"].isin(wilayah)] if wilayah else T

ew_list, n_ew_dinilai = ui.daftar_ew(T, wilayah, st.session_state["f_k"])
ew_list = ew_list.assign(urut=np.arange(1, len(ew_list) + 1))  # peringkat risiko di daftar k
ew_ids = set(ew_list["id_peserta"])

# satu peserta, satu tindakan (tepat_ui.PRIORITAS)
T_w = T_w.assign(utama=ui.tindakan_utama(T_w["rute"], T_w["id_peserta"].isin(ew_ids)))
triase_w = T_w[T_w["utama"].isin(ui.RUTE_AKSI)]
ew_utama = ew_list[ew_list["id_peserta"].isin(T_w.loc[T_w["utama"] == ui.PERINGATAN_DINI, "id_peserta"])]
n_triase, n_ew = len(triase_w), len(ew_utama)

pilihan = st.segmented_control(
    "Daftar", ["triase", "ew"], key="f_daftar", label_visibility="collapsed",
    format_func=lambda x: (f"Triase pola bayar  {ui.angka(n_triase)}" if x == "triase"
                           else f"{ui.EW_NAMA}  {ui.angka(n_ew)}"))
pilihan = pilihan or "triase"


def tabel_pilih(view: pd.DataFrame, kunci: str, unduh: pd.DataFrame, nama_file: str,
                column_config: dict) -> None:
    """Baris aksi (jumlah, Buka profil, Unduh CSV) di atas tabel yang bisa dipilih satu baris."""
    if "Keputusan" in view.columns:  # taruh di sebelah ID supaya terlihat tanpa menggeser tabel
        kol = [c for c in view.columns if c != "Keputusan"]
        kol.insert(kol.index("ID peserta") + 1, "Keputusan")
        view = view[kol]
    sel = st.session_state.get(kunci)
    pid = None
    if sel is not None and sel.selection.rows:
        i = sel.selection.rows[0]
        if i < len(view):
            pid = view.iloc[i]["ID peserta"]

    a, b, c = st.columns([6, 1.6, 1.4], vertical_alignment="center")
    if pid:
        a.markdown(f"{ui.angka(len(view))} peserta. Terpilih **{pid}**.")
    else:
        a.markdown(f"{ui.angka(len(view))} peserta. Pilih satu baris untuk membuka profilnya.")
    if b.button("Buka profil", type="primary", disabled=pid is None, width="stretch",
                key=f"{kunci}_buka"):
        st.switch_page(ui.HALAMAN_PROFIL, query_params={"id": pid})
    c.download_button("Unduh CSV", unduh.to_csv(index=False).encode("utf-8-sig"), nama_file,
                      "text/csv", on_click="ignore", width="stretch", key=f"{kunci}_unduh")
    st.html('<div style="height:.9rem" aria-hidden="true"></div>')  # ruang untuk toolbar tabel
    st.dataframe(view, key=kunci, on_select="rerun", selection_mode="single-row", hide_index=True,
                 height=min(600, 38 + 35 * max(len(view), 1)), column_config=column_config)


# ---------------------------------------------------------------- triase pola bayar
if pilihan == "triase":
    hitung = triase_w["rute"].value_counts()
    st.html(ui.strip_rute({r: int(hitung.get(r, 0)) for r in ui.RUTE_AKSI}))
    pindah = int(((T_w["rute"] == "pengingat_autodebet_REHAB") & (T_w["utama"] == ui.PERINGATAN_DINI)).sum())
    st.html('<p class="tp-ket">Rute per 31 Desember 2025, dihitung aturan dari riwayat bayar, status, '
            'dan klaim sejak Januari 2023. Satu peserta hanya mendapat satu tindakan: '
            f'{ui.angka(pindah)} peserta rute pengingat yang juga berisiko menunggak ditangani di '
            f'daftar {ui.EW_NAMA}. Keputusan tetap di petugas.</p>')

    c1, c2 = st.columns([5, 2], vertical_alignment="center")
    rute = c1.pills("Rute", ui.RUTE_AKSI, selection_mode="multi", key="f_rute",
                    format_func=lambda r: ui.RUTE[r]["nama"], label_visibility="collapsed")
    hanya_nonaktif = c2.toggle("Hanya yang sedang nonaktif", key="f_nonaktif",
                               help="Status per 31 Desember 2025.")

    if not rute:
        st.markdown("Pilih minimal satu rute untuk menampilkan peserta.")
    else:
        d = triase_w[triase_w["rute"].isin(rute)]
        if hanya_nonaktif:
            d = d[d["status_akhir"] == "nonaktif"]
        d = d.sort_values(["urut_rute", "tunggakan_rp", "id_peserta"], ascending=[True, False, True])
        view = pd.DataFrame({
            "ID peserta": d["id_peserta"],
            "Rute": d["rute"].map(lambda r: ui.RUTE[r]["pendek"]),
            "Alasan": d["alasan"].map(ui.alasan_rapi),
            "Status": d["status_akhir"].map(ui.STATUS),
            "Tunggakan": d["tunggakan_bulan"].astype(int),
            "Wilayah": d["kode_wilayah"],
            "DTSEN": d["rentang_desil"].map(ui.DESIL),
            "Juga di": np.where(d["id_peserta"].isin(ew_ids), ui.EW_NAMA, ""),
            "Keputusan": d["id_peserta"].map(ui.label_keputusan),
        })
        unduh = d[["id_peserta", "rute", "alasan", "status_akhir", "tunggakan_bulan", "tunggakan_rp",
                   "kode_wilayah", "rentang_desil"]].assign(
            juga_berisiko_menunggak=d["id_peserta"].isin(ew_ids), tindakan_utama=d["utama"],
            keputusan=d["id_peserta"].map(ui.label_keputusan))
        if not ui.keputusan():
            view = view.drop(columns="Keputusan")
        kunci = "tbl_triase_" + str(abs(hash((tuple(wilayah), tuple(sorted(rute)), hanya_nonaktif))))
        tabel_pilih(view, kunci, unduh, "tepat_triase.csv", {
            "ID peserta": st.column_config.TextColumn(width=88, pinned=True),
            "Rute": st.column_config.TextColumn(width=104, help=" | ".join(
                f"{ui.RUTE[r]['pendek']}: {ui.RUTE[r]['nama']}" for r in ui.RUTE_AKSI)),
            "Alasan": st.column_config.TextColumn(width=420),
            "Status": st.column_config.TextColumn(width=78),
            "Tunggakan": st.column_config.NumberColumn(format="%d bulan", width=88,
                                                       help="Bulan iuran tertunggak per 31 Des 2025"),
            "Wilayah": st.column_config.TextColumn(width=66),
            "DTSEN": st.column_config.TextColumn(width=92),
            "Juga di": st.column_config.TextColumn(
                width=110, help="Juga memenuhi daftar lain, tetapi ditangani lewat rute ini"),
            "Keputusan": st.column_config.TextColumn(width=88, help="Keputusan petugas di sesi ini"),
        })

# ---------------------------------------------------------------- peringatan dini
else:
    ke_rute = len(ew_list) - n_ew
    st.html('<p class="tp-ket">Peserta yang masih aktif pada Desember 2025 dan berisiko menunggak dalam '
            '3 bulan ke depan menurut model peringatan dini, diurutkan dari peluang tertinggi. '
            'Yang masuk hanya sebanyak kapasitas petugas; angka kanonik '
            'proposal adalah 5% dari seluruh peserta aktif, yaitu 712 orang. Satu peserta hanya mendapat '
            f'satu tindakan: {ui.angka(ke_rute)} di antaranya juga ada di rute verifikasi, jadi ditangani '
            'lewat verifikasi.</p>')
    c1, c2 = st.columns([3, 4], vertical_alignment="bottom")
    c1.slider("Kapasitas petugas bulan ini", 1, 20, key="f_k", format="%d%% peserta aktif")
    saran = ew_utama["ew_saran"].value_counts()
    rincian = ", ".join(f"{ui.angka(saran[s])} {ui.kecil(ui.SARAN[s])}" for s in ui.SARAN if s in saran)
    c2.markdown(f"**{ui.angka(n_ew)}** ditangani di sini, dari {ui.angka(len(ew_list))} peserta "
                f"teratas di antara {ui.angka(n_ew_dinilai)} peserta aktif"
                f"{' di wilayah terpilih' if wilayah else ''}. Saran: {rincian}.")

    d = ew_utama
    view = pd.DataFrame({
        "Peringkat": d["urut"].values,
        "ID peserta": d["id_peserta"].values,
        # dibulatkan ke bawah: skor 0,9975 tampil 99%, bukan 100% yang terkesan pasti
        "Peluang menunggak": np.floor(100 * d["ew_skor"].values),
        "Alasan": d["ew_alasan"].map(ui.alasan_rapi).values,
        "Saran": d["ew_saran"].map(ui.SARAN).values,
        "Wilayah": d["kode_wilayah"].values,
        "Juga di": d["rute"].map(lambda r: ui.RUTE[r]["pendek"]).values,
        "Keputusan": d["id_peserta"].map(ui.label_keputusan).values,
    })
    unduh = d[["ew_peringkat", "id_peserta", "ew_skor", "ew_alasan", "ew_saran", "kode_wilayah",
               "rute", "urut"]].rename(columns={"urut": "peringkat_di_daftar"}).assign(
        keputusan=d["id_peserta"].map(ui.label_keputusan))
    if not ui.keputusan():
        view = view.drop(columns="Keputusan")
    kunci = "tbl_ew_" + str(abs(hash((tuple(wilayah), st.session_state["f_k"]))))
    tabel_pilih(view, kunci, unduh, "tepat_berisiko_menunggak.csv", {
        "Peringkat": st.column_config.NumberColumn(
            format="%d", width=76, pinned=True,
            help="Peringkat risiko di daftar kapasitas. Nomor yang tidak muncul ditangani lewat rute verifikasi."),
        "ID peserta": st.column_config.TextColumn(width=88, pinned=True),
        "Peluang menunggak": st.column_config.ProgressColumn(
            format="%.0f%%", min_value=0, max_value=100, width=150,
            help="Peluang menunggak dalam 3 bulan menurut model (data sintetis)"),
        "Alasan": st.column_config.TextColumn(width=360),
        "Saran": st.column_config.TextColumn(width=200),
        "Wilayah": st.column_config.TextColumn(width=66),
        "Juga di": st.column_config.TextColumn(
            width=98, help="Juga memenuhi rute triase ini, tetapi ditangani lewat daftar ini"),
        "Keputusan": st.column_config.TextColumn(width=88),
    })
