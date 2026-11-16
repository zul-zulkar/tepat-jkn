"""Halaman Daftar kerja: dua daftar (triase pola bayar, berisiko menunggak), filter wilayah, rute, kapasitas k."""
import numpy as np
import pandas as pd
import streamlit as st

import akun
import tepat_ui as ui

FILTER = dict(f_wilayah=[], f_daftar="triase", f_rute=list(ui.RUTE_AKSI), f_nonaktif=False, f_k=5)
ui.pertahankan(*FILTER)
for k, v in FILTER.items():
    st.session_state.setdefault(k, v)

T = ui.tabel_peserta()
CABANG = akun.adalah_cabang()
if CABANG:  # kantor cabang hanya melihat peserta di wilayahnya
    T = T[T["kode_wilayah"].isin(akun.wilayah_akun())]

ui.kepala("Daftar kerja",
          "Siapa yang ditangani bulan ini, lewat jalur apa, dan kenapa. Satu peserta hanya mendapat satu "
          "tindakan. Pilih satu baris di tabel untuk membuka profilnya.")

# ---------------------------------------------------------------- filter bersama dan hitungan
c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
wilayah = c1.multiselect(":material/location_on: Wilayah",
                         akun.wilayah_akun() if CABANG else sorted(T["kode_wilayah"].unique()),
                         key="f_wilayah",
                         placeholder="Semua wilayah cabang ini" if CABANG else "Semua wilayah")
wilayah = akun.wilayah_efektif(wilayah)  # cabang: kosong = semua wilayah cabangnya
T_w = T[T["kode_wilayah"].isin(wilayah)] if wilayah else T
terpilih_w = bool(wilayah) and not (CABANG and set(wilayah) == set(akun.wilayah_akun()))

ew_list, n_ew_dinilai = ui.daftar_ew(T, wilayah, st.session_state["f_k"])
ew_list = ew_list.assign(urut=np.arange(1, len(ew_list) + 1))  # peringkat risiko di daftar k
ew_ids = set(ew_list["id_peserta"])

# satu peserta, satu tindakan (tepat_ui.PRIORITAS)
T_w = T_w.assign(utama=ui.tindakan_utama(T_w["rute"], T_w["id_peserta"].isin(ew_ids)))
triase_w = T_w[T_w["utama"].isin(ui.RUTE_AKSI)]
ew_utama = ew_list[ew_list["id_peserta"].isin(T_w.loc[T_w["utama"] == ui.PERINGATAN_DINI, "id_peserta"])]
n_triase, n_ew = len(triase_w), len(ew_utama)

pilihan = c2.segmented_control(
    "Daftar", ["triase", "ew"], key="f_daftar", label_visibility="collapsed",
    format_func=lambda x: (f":material/route: Triase pola bayar  {ui.angka(n_triase)}" if x == "triase"
                           else f"{ui.EW_MI} {ui.EW_NAMA}  {ui.angka(n_ew)}"))
pilihan = pilihan or "triase"

# ---------------------------------------------------------------- alur perlakuan (flowchart)
with st.expander("Alur perlakuan: dari peserta ke satu tindakan", icon=":material/account_tree:"):
    st.html(ui.alur_perlakuan(jumlah=T_w["utama"].value_counts().to_dict(), total=len(T_w),
                              label_mulai="Peserta PBPU/BP mandiri" + (" di wilayah terpilih" if terpilih_w else
                                                                  " di wilayah cabang ini" if CABANG else "")))
    st.caption(f"Pertanyaan diperiksa dari atas; jawaban ya pertama menentukan tindakan, jadi satu peserta hanya "
               f"mendapat satu tindakan. Jumlah mengikuti filter wilayah dan kapasitas "
               f"{st.session_state['f_k']}% di daftar {ui.EW_NAMA}. Kanal tiap perlakuan adalah usulan tim "
               f"setelah coaching dan perlu dikonfirmasi BPJS.")


def label_warna(kode: pd.Series, urutan: list[str], nama, warna) -> tuple[pd.Series, dict]:
    """Isi kolom label berwarna (satu label per baris) dan konfigurasinya untuk st.dataframe."""
    opsi = [nama(k) for k in urutan]
    return kode.map(lambda k: [nama(k)]), dict(options=opsi, color=[warna(k) for k in urutan], disabled=True)


def tabel_pilih(view: pd.DataFrame, kunci: str, unduh: pd.DataFrame, nama_file: str,
                column_config: dict) -> None:
    """Baris aksi (jumlah, Buka profil, Unduh CSV) di atas tabel yang bisa dipilih satu baris."""
    if "Keputusan" in view.columns:  # taruh di sebelah ID supaya terlihat tanpa menggeser tabel
        kol = [c for c in view.columns if c != "Keputusan"]
        kol.insert(kol.index("ID peserta") + 1, "Keputusan")
        view = view[kol]
    if "Dicatat oleh" in view.columns:  # hanya Pusat; sempit supaya tabel tidak melebar
        view = view.assign(**{"Dicatat oleh": view["Dicatat oleh"].str.replace(" (contoh)", "", regex=False)})
    sel = st.session_state.get(kunci)
    pid = None
    if sel is not None and sel.selection.rows:
        i = sel.selection.rows[0]
        if i < len(view):
            pid = view.iloc[i]["ID peserta"]

    a, b, c = st.columns([6, 1.7, 1.5], vertical_alignment="center")
    a.markdown(f"**{ui.angka(len(view))}** peserta" + (f", terpilih **{pid}**" if pid else ""))
    if b.button("Buka profil", icon=":material/open_in_new:", type="primary", disabled=pid is None,
                width="stretch", key=f"{kunci}_buka", help=None if pid else "Pilih satu baris dulu"):
        st.switch_page(ui.HALAMAN_PROFIL, query_params={"id": pid})
    c.download_button("CSV", unduh.to_csv(index=False).encode("utf-8-sig"), nama_file, "text/csv",
                      icon=":material/download:", on_click="ignore", width="stretch",
                      key=f"{kunci}_unduh", help="Unduh daftar ini")
    st.html('<div style="height:.9rem" aria-hidden="true"></div>')  # ruang untuk toolbar tabel
    st.dataframe(view, key=kunci, on_select="rerun", selection_mode="single-row", hide_index=True,
                 height=min(600, 38 + 35 * max(len(view), 1)), column_config=column_config)


# ---------------------------------------------------------------- triase pola bayar
if pilihan == "triase":
    hitung = triase_w["rute"].value_counts()
    terpilih = st.session_state.get("f_rute") or []
    st.html(ui.kartu([dict(ikon=ui.RUTE[r]["ikon"], c=ui.RUTE[r]["warna"], l=ui.RUTE[r]["lembut"],
                           n=ui.angka(int(hitung.get(r, 0))), label=ui.RUTE[r]["nama"], mati=r not in terpilih)
                      for r in ui.RUTE_AKSI]))

    pindah = int(((T_w["rute"] == "pengingat_autodebet_REHAB") & (T_w["utama"] == ui.PERINGATAN_DINI)).sum())
    c1, c2, c3 = st.columns([6, 2.4, 0.4], vertical_alignment="center")
    rute = c1.pills("Rute", ui.RUTE_AKSI, selection_mode="multi", key="f_rute",
                    format_func=lambda r: f'{ui.RUTE[r]["mi"]} {ui.RUTE[r]["pendek"]}',
                    label_visibility="collapsed")
    hanya_nonaktif = c2.toggle("Hanya yang nonaktif", key="f_nonaktif", help="Status per 31 Desember 2025")
    c3.html(ui.info(
        "Rute dihitung aturan dari riwayat bayar, status, dan klaim sejak Januari 2023, posisi "
        f"31 Desember 2025. {ui.angka(pindah)} peserta rute pengingat yang juga berisiko menunggak "
        f"ditangani di daftar {ui.EW_NAMA}. Keputusan tetap di petugas.", kanan=True))

    if not rute:
        st.markdown("Pilih minimal satu rute.")
    else:
        d = triase_w[triase_w["rute"].isin(rute)]
        if hanya_nonaktif:
            d = d[d["status_akhir"] == "nonaktif"]
        d = d.sort_values(["urut_rute", "tunggakan_rp", "id_peserta"], ascending=[True, False, True])
        # label rute berwarna sesuai perlakuannya (warna sama dengan kartu di atas dan flowchart)
        isi_rute, cfg_rute = label_warna(d["rute"], ui.RUTE_AKSI, lambda r: ui.RUTE[r]["pendek"],
                                         lambda r: ui.RUTE[r]["warna"])
        view = pd.DataFrame({
            "ID peserta": d["id_peserta"],
            "Rute": isi_rute,
            "Perlakuan": d["rute"].map(lambda r: ui.PERLAKUAN[r]["pendek"]),
            "Alasan": d["alasan"].map(ui.alasan_rapi),
            "Status": d["status_akhir"].map(ui.STATUS),
            "Tunggakan": d["tunggakan_bulan"].astype(int),
            "Wilayah": d["kode_wilayah"],
            "DTSEN": d["rentang_desil"].map(ui.DESIL),
            "Juga di": np.where(d["id_peserta"].isin(ew_ids), ui.EW_NAMA, ""),
            "Keputusan": d["id_peserta"].map(ui.label_keputusan),
            "Dicatat oleh": d["id_peserta"].map(ui.pencatat),
        })
        unduh = d[["id_peserta", "rute", "alasan", "status_akhir", "tunggakan_bulan", "tunggakan_rp",
                   "kode_wilayah", "rentang_desil"]].assign(
            juga_berisiko_menunggak=d["id_peserta"].isin(ew_ids), tindakan_utama=d["utama"],
            perlakuan=d["rute"].map(lambda r: ui.PERLAKUAN[r]["pendek"]),
            keputusan=d["id_peserta"].map(ui.label_keputusan),
            dicatat_oleh=d["id_peserta"].map(ui.pencatat))
        if not ui.keputusan():
            view = view.drop(columns=["Keputusan", "Dicatat oleh"])
        elif CABANG:  # pencatat sama dengan akun sendiri; kolom ini untuk Pusat
            view = view.drop(columns="Dicatat oleh")
        kunci = "tbl_triase_" + str(abs(hash((tuple(wilayah), tuple(sorted(rute)), hanya_nonaktif))))
        tabel_pilih(view, kunci, unduh, "tepat_triase.csv", {
            "ID peserta": st.column_config.TextColumn(width=88, pinned=True),
            "Rute": st.column_config.MultiselectColumn(width=118, help=" | ".join(
                f"{ui.RUTE[r]['pendek']}: {ui.RUTE[r]['nama']}" for r in ui.RUTE_AKSI), **cfg_rute),
            "Perlakuan": st.column_config.TextColumn(
                width=230, help="Yang dikerjakan petugas, lewat kanal yang sudah ada. Usulan tim, perlu "
                                "dikonfirmasi BPJS. Alurnya ada di bagian Alur perlakuan."),
            "Alasan": st.column_config.TextColumn(width=420),
            "Status": st.column_config.TextColumn(width=78),
            "Tunggakan": st.column_config.NumberColumn(format="%d bulan", width=88,
                                                       help="Bulan iuran tertunggak per 31 Des 2025"),
            "Wilayah": st.column_config.TextColumn(width=66),
            "DTSEN": st.column_config.TextColumn(width=92),
            "Juga di": st.column_config.TextColumn(
                width=110, help="Juga memenuhi daftar lain, tetapi ditangani lewat rute ini"),
            "Keputusan": st.column_config.TextColumn(width=88, help="Keputusan petugas di sesi ini"),
            "Dicatat oleh": st.column_config.TextColumn(width=150, help="Akun kantor cabang yang mencatat"),
        })

# ---------------------------------------------------------------- berisiko menunggak
else:
    ke_rute = len(ew_list) - n_ew
    saran = ew_utama["ew_saran"].value_counts()
    ikon_saran = {"pengingat_H-5_dan_tawaran_autodebet": ("bell-ring", "Pengingat H-5 + autodebet"),
                  "cek_kelayakan_PBI": ("hand-heart", "Cek kelayakan PBI"),
                  "pengingat_saldo_autodebet": ("wallet", "Pengingat saldo autodebet")}
    st.html(ui.kartu(
        [dict(ikon=ui.EW_IKON, c=ui.WARNA_EW, l=ui.EW_LEMBUT, n=ui.angka(n_ew),
              label=f"dari {ui.angka(len(ew_list))} teratas")]
        + [dict(ikon=ikon_saran[s][0], c=ui.WARNA["tinta2"], l=ui.WARNA["permukaan"],
                n=ui.angka(int(saran.get(s, 0))), label=ikon_saran[s][1]) for s in ui.SARAN]))

    c1, c2 = st.columns([3, 5], vertical_alignment="center")
    c1.slider(":material/groups: Kapasitas petugas bulan ini", 1, 20, key="f_k", format="%d%% peserta aktif",
              disabled=CABANG)
    if CABANG:
        c1.caption(f"Kapasitas ditetapkan Kantor Pusat: {st.session_state['f_k']}%")
    c2.html(ui.info(
        f"Peserta aktif yang berisiko menunggak dalam 3 bulan ke depan menurut model peringatan dini, "
        f"diurutkan dari peluang tertinggi. Kapasitas dihitung dari {ui.angka(n_ew_dinilai)} peserta aktif"
        f"{' di wilayah terpilih' if terpilih_w else ' di wilayah cabang ini' if CABANG else ''}; angka proposal adalah 5%, yaitu 712 orang. "
        f"{ui.angka(ke_rute)} peserta juga ada di rute verifikasi, jadi ditangani lewat verifikasi."))

    d = ew_utama
    # saran berwarna: warna mengikuti perlakuan yang paling dekat (cek PBI biru, autodebet hijau)
    warna_saran = {"pengingat_H-5_dan_tawaran_autodebet": ui.WARNA_EW,
                   "cek_kelayakan_PBI": ui.RUTE["rujuk_cek_kelayakan_PBI"]["warna"],
                   "pengingat_saldo_autodebet": ui.RUTE["pengingat_autodebet_REHAB"]["warna"]}
    saran_pendek = {"pengingat_H-5_dan_tawaran_autodebet": "Pengingat H-5 + autodebet",
                    "cek_kelayakan_PBI": "Cek kelayakan PBI",
                    "pengingat_saldo_autodebet": "Pengingat saldo autodebet"}
    isi_saran, cfg_saran = label_warna(d["ew_saran"], list(ui.SARAN), saran_pendek.get, warna_saran.get)
    view = pd.DataFrame({
        "Peringkat": d["urut"].values,
        "ID peserta": d["id_peserta"].values,
        # dibulatkan ke bawah: skor 0,9975 tampil 99%, bukan 100% yang terkesan pasti
        "Peluang menunggak": np.floor(100 * d["ew_skor"].values),
        "Alasan": d["ew_alasan"].map(ui.alasan_rapi).values,
        "Saran": isi_saran.values,
        "Wilayah": d["kode_wilayah"].values,
        "Juga di": d["rute"].map(lambda r: ui.RUTE[r]["pendek"]).values,
        "Keputusan": d["id_peserta"].map(ui.label_keputusan).values,
        "Dicatat oleh": d["id_peserta"].map(ui.pencatat).values,
    })
    unduh = d[["ew_peringkat", "id_peserta", "ew_skor", "ew_alasan", "ew_saran", "kode_wilayah",
               "rute", "urut"]].rename(columns={"urut": "peringkat_di_daftar"}).assign(
        keputusan=d["id_peserta"].map(ui.label_keputusan),
        dicatat_oleh=d["id_peserta"].map(ui.pencatat))
    if not ui.keputusan():
        view = view.drop(columns=["Keputusan", "Dicatat oleh"])
    elif CABANG:
        view = view.drop(columns="Dicatat oleh")
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
        "Saran": st.column_config.MultiselectColumn(width=210, help="Perlakuan yang disarankan model", **cfg_saran),
        "Wilayah": st.column_config.TextColumn(width=66),
        "Juga di": st.column_config.TextColumn(
            width=98, help="Juga memenuhi rute triase ini, tetapi ditangani lewat daftar ini"),
        "Keputusan": st.column_config.TextColumn(width=88),
        "Dicatat oleh": st.column_config.TextColumn(width=150),
    })
