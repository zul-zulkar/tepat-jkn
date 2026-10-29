"""Halaman Profil peserta: ringkasan, tindakan bulan ini, rute + alasan, linimasa 3 tahun, keputusan, draf pesan."""
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import llm
import pesan_template
import tepat_ui as ui
from ikon import ikon

T = ui.tabel_peserta()
IDX = T.set_index("id_peserta")
W = ui.WARNA
STATUS_WARNA = {"aktif": ("#17704D", "#E1EEE6"), "nonaktif": ("#9A3F12", "#F6E4D6"),
                "masa_tunggu": ("#9A5F0E", "#F5E6C8")}


def _buka(pid: str) -> None:
    st.query_params["id"] = pid


def _cari() -> None:
    v = ui.normalkan_id(st.session_state.get("cari_id", ""))
    if v:
        st.query_params["id"] = v
    st.session_state["cari_id"] = ""


def _warna_tindakan(t: str) -> tuple[str, str, str]:
    if t == ui.PERINGATAN_DINI:
        return ui.WARNA_EW, ui.EW_LEMBUT, ui.EW_IKON
    return ui.RUTE[t]["warna"], ui.RUTE[t]["lembut"], ui.RUTE[t]["ikon"]


# ---------------------------------------------------------------- baris atas
a, b = st.columns([3, 2], vertical_alignment="bottom")
with a:
    st.page_link(ui.HALAMAN_DAFTAR, label="Daftar kerja", icon=":material/arrow_back:")
b.text_input(":material/search: Cari ID peserta", key="cari_id", on_change=_cari,
             placeholder="P-002329 atau 2329")

pid = st.query_params.get("id")
pid = ui.normalkan_id(pid) if pid else st.session_state.get("_pid_terakhir")

if not pid:
    ui.kepala("Profil peserta", "Riwayat tiga tahun, rute, alasan, dan keputusan petugas untuk satu peserta. "
              "Pilih dari daftar kerja, ketik ID, atau buka salah satu contoh.")
    contoh = []
    for r in ui.RUTE_AKSI:
        d = T[T["rute"] == r].sort_values(["tunggakan_rp", "id_peserta"], ascending=[False, True])
        if r == "pengingat_autodebet_REHAB":
            d = d[d["tunggakan_bulan"] > 0]
        if len(d):
            contoh.append((d.iloc[0]["id_peserta"], ui.RUTE[r]["nama"], ui.RUTE[r]["mi"]))
    p1 = T[T["ew_peringkat"] == 1]
    if len(p1):
        contoh.append((p1.iloc[0]["id_peserta"], f"{ui.EW_NAMA}, peringkat 1", ui.EW_MI))
    ui.judul_bagian("Contoh", "layers")
    kol = st.columns(len(contoh))
    for c, (i, lbl, mi) in zip(kol, contoh):
        c.button(i, icon=mi, key=f"contoh_{i}", on_click=_buka, args=(i,), width="stretch")
        c.caption(lbl)
    st.stop()

if pid not in IDX.index:
    ui.kepala("Profil peserta", "Format ID: P- diikuti enam angka, misalnya P-002329.")
    st.markdown(f":material/error: ID **{ui.e(pid)}** tidak ada di data peserta mandiri. Periksa penulisannya.")
    st.stop()

st.session_state["_pid_terakhir"] = pid
p = IDX.loc[pid].to_dict() | {"id_peserta": pid}
p["alasan_rapi"] = ui.alasan_rapi(p["alasan"])

status = ui.linimasa("linimasa_status", pid).sort_values("tgl_mulai")
bayar = ui.linimasa("linimasa_bayar", pid).sort_values("tgl_bayar")
klaim = ui.linimasa("linimasa_klaim", pid).sort_values("tgl_masuk")
reakt = ui.linimasa("linimasa_reaktivasi", pid).sort_values("tgl_reakt")
pasangan = ui.pasangan_reaktivasi_klaim(reakt, klaim)

# daftar berisiko menunggak memakai filter dan kapasitas yang sedang dipakai di halaman Daftar kerja
ew_list, _ = ui.daftar_ew(T, st.session_state.get("f_wilayah", []), st.session_state.get("f_k", 5))
masuk_ew = pid in set(ew_list["id_peserta"])
utama = ui.tindakan_utama(pd.Series([p["rute"]]), pd.Series([masuk_ew])).iloc[0]
m = ui.manifest()

# ---------------------------------------------------------------- kepala dan fakta
sejak = status.iloc[-1]["tgl_mulai"] if len(status) else None
sw, sl = STATUS_WARNA.get(p["status_akhir"], (W["tinta2"], W["permukaan"]))
status_teks = ui.STATUS.get(p["status_akhir"], p["status_akhir"]) + (f" sejak {ui.tgl(sejak)}" if sejak is not None else "")
st.html(
    f'<div class="tp-id"><h1>{ui.e(pid)}</h1>'
    + ui.chip(status_teks, "activity", sw, sl)
    + ui.chip(f'{p["segmen_kepesertaan"]} mandiri, kelas {int(p["kelas"])}')
    + ui.chip(p["kode_wilayah"], "map-pin")
    + ui.chip(f'Terdaftar {ui.tgl(p["tgl_daftar"])}', "calendar")
    + f'<span style="margin-left:auto;display:inline-flex;align-items:center;gap:.2rem">{ui.chip_data()}</span></div>')

klaim_rp, iuran_rp = float(p["klaim_rp"] or 0), float(p["iuran_rp"] or 0)
fakta = [
    ("wallet", "Tunggakan", f"{int(p['tunggakan_bulan'])} bulan", ui.rp(p["tunggakan_rp"])),
    ("receipt", "Iuran", ui.rp(p["iuran_bulanan"]), "per bulan"),
    ("repeat", "Autodebet", "Ya" if p["autodebet"] else "Tidak", ""),
    ("users", "DTSEN", ui.DESIL.get(p["rentang_desil"], "-"), ""),
    ("scale", "Klaim : iuran", (ui.angka(p["rasio_klaim_iuran"], 2) + "×") if iuran_rp else "-",
     f"{ui.rp(klaim_rp)} klaim"),
    ("history", "Aktif kembali", f"{int(p['n_reaktivasi'])} kali", f"aktif {ui.persen(p['rasio_hari_aktif'], 0)} waktu"),
]
st.html('<div class="tp-fakta">' + "".join(
    f'<div><div class="dt">{ikon(ik, 14, W["tinta3"])}{ui.e(k)}</div>'
    f'<div class="dd">{ui.e(v)}{f"<small>{ui.e(s)}</small>" if s else ""}</div></div>'
    for ik, k, v, s in fakta) + "</div>")

# ---------------------------------------------------------------- tindakan bulan ini
if utama == "tanpa_tindakan":
    st.html(f'<div class="tp-tindakan" style="--c:{W["tinta2"]};--l:{W["permukaan"]}">'
            f'<div class="tp-bulat" style="color:{W["tinta3"]}">{ikon("circle-check-big", 20, W["tinta3"])}</div>'
            f'<div><div class="lbl">Tindakan bulan ini</div><div class="isi">Tidak ada</div></div></div>')
else:
    c, lmbt, ik = _warna_tindakan(utama)
    lain = [ui.RUTE[p["rute"]]["pendek"]] if p["rute"] not in ("tanpa_tindakan", utama) else []
    lain += [ui.EW_NAMA] if masuk_ew and utama != ui.PERINGATAN_DINI else []
    sisi = ""
    if lain:
        sisi = (f'<div class="lain" style="margin-left:auto;display:flex;align-items:center;gap:.2rem">'
                f'Juga masuk: {ui.e(", ".join(lain))} (tidak dijalankan)'
                + ui.info("Satu peserta hanya mendapat satu tindakan. Urutan: verifikasi, cek PBI, "
                          "berisiko menunggak, lalu pengingat.", kanan=True) + "</div>")
    st.html(f'<div class="tp-tindakan" style="--c:{c};--l:{lmbt}"><div class="tp-bulat" style="color:{c}">'
            f'{ikon(ik, 20, c)}</div><div><div class="lbl">Tindakan bulan ini</div>'
            f'<div class="isi">{ui.e(ui.nama_tindakan(utama))}</div></div>{sisi}</div>')

# ---------------------------------------------------------------- rute dan risiko menunggak
R = ui.RUTE[p["rute"]]
arti = ui.e(R["arti"])
angka_rute, catatan = "", ""
if p["rute"] != "tanpa_tindakan":
    angka_rute = ('<div class="tp-angka">'
                  + ui.chip(f'Klaim besar ≤ 90 hari setelah aktif kembali: {int(p["n_reakt_terkait_klaim"])} kali',
                            R["ikon"], R["warna"], R["lembut"]) + "</div>")
if p["rute"] == "verifikasi_pola_reaktivasi":
    arti += " Peserta DTSEN desil 1–5 tidak pernah masuk rute ini."
    # aturan tetap menghitung IGD (keputusan 24 Okt); petugas diberi tahu bila buktinya rawat inap darurat
    q = pasangan[pasangan["terkait"]] if len(pasangan) else pasangan
    n_igd = int(((q["jenis_layanan"] == "RITL") & (q["cara_masuk"] == "IGD")).sum()) if len(q) else 0
    if n_igd:
        awal = "Semua bukti" if n_igd == len(q) else f"{n_igd} dari {len(q)} bukti"
        catatan = (f'<div class="tp-catatan">{ikon("siren", 16, "#8A3B14")}<span>{awal} berupa rawat inap darurat '
                   'lewat IGD. Periksa apakah peserta baru melunasi karena musibah.</span></div>')
panel_triase = (
    f'<section class="tp-panel{"" if utama == p["rute"] else " tp-sekunder"}" '
    f'style="--c:{R["warna"]};--l:{R["lembut"]}"><div class="atas"><div class="tp-bulat">{ikon(R["ikon"], 20, R["warna"])}</div>'
    f'<div><p class="sumber">Rute triase</p><p class="nama">{ui.e(R["nama"])}</p></div>'
    f'{ui.info(arti, kanan=True, label="Arti rute")}</div>'
    + (f'<p class="alasan">{ui.e(p["alasan_rapi"])}</p>' if p["alasan_rapi"] else "")
    + f"{angka_rute}{catatan}</section>")

panel_ew = ""
if pd.notna(p.get("ew_peringkat")):
    e_ = ui.ew_baris().loc[pid]
    kontrib = sorted(((c[len("kontribusi_"):], float(e_[c])) for c in e_.index
                      if c.startswith("kontribusi_") and float(e_[c]) > 0), key=lambda t: -t[1])[:3]
    maks = max([v for _, v in kontrib] + [1e-9])
    baris = "".join(f'<div><span>{ui.e(ui.FITUR_EW.get(f, (f,))[0])}</span>'
                    f'<s style="width:{100 * v / maks:.0f}%"></s></div>' for f, v in kontrib)
    status_daftar = (f"Masuk daftar pada kapasitas saat ini ({ui.angka(len(ew_list))} orang)."
                     if masuk_ew else "Tidak masuk daftar pada kapasitas saat ini.")
    panel_ew = (
        f'<section class="tp-panel{"" if utama == ui.PERINGATAN_DINI else " tp-sekunder"}" '
        f'style="--c:{ui.WARNA_EW};--l:{ui.EW_LEMBUT}"><div class="atas"><div class="tp-bulat">'
        f'{ikon(ui.EW_IKON, 20, ui.WARNA_EW)}</div><div><p class="sumber">{ui.EW_NAMA_PANJANG}</p>'
        f'<p class="nama">Peluang {ui.persen(e_["skor"], 1)}</p></div>'
        + ui.info(f'Model peringatan dini, dihitung {ui.bulan_tahun(str(e_["bulan"]))}. Peringkat '
                  f'{ui.angka(int(e_["peringkat"]))} dari {ui.angka(m["ew_n_dinilai"])} peserta aktif. '
                  f'{status_daftar} Batang di bawah menunjukkan penyumbang terbesar skor.',
                  kanan=True, label="Tentang skor")
        + f'</div><p class="alasan">{ui.e(ui.alasan_rapi(e_["alasan"]))}</p>'
        + '<div class="tp-angka">'
        + ui.chip(f'Saran: {ui.SARAN.get(e_["saran_intervensi"], "-")}', "bell-ring", ui.WARNA_EW, ui.EW_LEMBUT)
        + "</div>"
        + (f'<div class="tp-kontrib">{baris}</div>' if kontrib else "")
        + "</section>")

if panel_ew:
    k1, k2 = st.columns(2, gap="medium")
    k1.html(panel_triase)
    k2.html(panel_ew)
else:
    st.html(panel_triase)

# ---------------------------------------------------------------- linimasa
ui.judul_bagian("Linimasa 2023 sampai 2025", "activity",
                "Garis putus-putus hijau: aktif kembali. Garis oranye: klaim besar paling lama 90 hari setelah "
                "aktif kembali, angkanya jarak dalam hari. Arahkan kursor ke tanda untuk rinciannya.")

BARIS = ["Status", "Iuran dibayar", "Klaim"]
KAT = {
    "Aktif": "#CBE5D7", "Nonaktif": "#F1D3C4", "Masa tunggu": "#F3E3BF",
    "Iuran 1 bulan": "#8F9993", "Melunasi beberapa bulan": W["utama"],
    "Rawat jalan": "#C5CCC8", "Rawat jalan ≥ Rp1 juta": "#5E6B66",
    "Rawat inap terjadwal": "#9A5F0E", "Rawat inap lewat IGD": "#B24A2B",
}
skala = alt.Scale(domain=list(KAT), range=list(KAT.values()))
label_bulan = ("['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'][month(datum.value)]"
               " + (month(datum.value) == 0 ? ' ' + year(datum.value) : '')")
sx = alt.Scale(domain=[alt.DateTime(year=2023, month=1, date=1), alt.DateTime(year=2026, month=1, date=1)])
ax = alt.Axis(title=None, labelExpr=label_bulan, tickCount={"interval": "month", "step": 3},
              grid=True, gridColor="#E6E5DE", domain=False, tickColor=W["garis"], labelColor=W["tinta3"],
              labelFontSize=11, labelPadding=6)
y = alt.Y("baris:N", sort=BARIS, scale=alt.Scale(domain=BARIS, paddingInner=0.3, paddingOuter=0.15),
          axis=alt.Axis(title=None, domain=False, ticks=False, labelColor=W["tinta2"], labelFontSize=12,
                        labelPadding=10, labelFontWeight=600))
warna = alt.Color("kat:N", scale=skala, legend=None)
_x_pertama = [True]


def X(kolom: str) -> alt.X:
    """Skala dan sumbu waktu hanya didefinisikan di lapisan pertama supaya tidak bentrok antarlapisan."""
    if _x_pertama[0]:
        _x_pertama[0] = False
        return alt.X(f"{kolom}:T", scale=sx, axis=ax)
    return alt.X(f"{kolom}:T", axis=None)


lapisan = []
if len(status):
    s = status.assign(baris="Status", kat=status["status"].map(ui.STATUS),
                      x=status["tgl_mulai"], x2=status["tgl_selesai"] + pd.Timedelta(days=1))
    s["ket"] = s["kat"] + ", " + s["tgl_mulai"].map(ui.tgl) + " sampai " + s["tgl_selesai"].map(ui.tgl)
    lapisan.append(alt.Chart(s[["baris", "kat", "x", "x2", "ket"]]).mark_bar(cornerRadius=3).encode(
        x=X("x"), x2="x2:T", y=y, color=warna, tooltip=[alt.Tooltip("ket:N", title="Status")]))
# garis reaktivasi di belakang tanda pembayaran
if len(reakt):
    r_ = reakt.assign(x=reakt["tgl_reakt"])
    r_["ket"] = ("Aktif kembali " + r_["tgl_reakt"].map(ui.tgl) + ", melunasi "
                 + r_["bulan_tertunggak"].astype(int).astype(str) + " bulan tertunggak")
    lapisan.append(alt.Chart(r_[["x", "ket"]]).mark_rule(strokeDash=[3, 3], strokeWidth=1.2,
                                                         color="#1E8A5F", opacity=0.7).encode(
        x=X("x"), tooltip=[alt.Tooltip("ket:N", title="Reaktivasi")]))
if len(bayar):
    b_ = bayar.assign(baris="Iuran dibayar", x=bayar["tgl_bayar"],
                      kat=bayar["jumlah_bulan_dibayar"].gt(1).map({True: "Melunasi beberapa bulan",
                                                                    False: "Iuran 1 bulan"}))
    b_["ket"] = (b_["tgl_bayar"].map(ui.tgl) + ": " + b_["jumlah_bulan_dibayar"].astype(str) + " bulan, "
                 + b_["nominal"].map(ui.rp) + " lewat " + b_["kanal"].map(ui.KANAL))
    b_["tebal"] = b_["jumlah_bulan_dibayar"].gt(1).map({True: 3, False: 1.4})
    b_["tinggi"] = b_["jumlah_bulan_dibayar"].gt(1).map({True: 26, False: 14})
    lapisan.append(alt.Chart(b_[["baris", "kat", "x", "ket", "tebal", "tinggi"]]).mark_tick().encode(
        x=X("x"), y=y, color=warna,
        size=alt.Size("tinggi:Q", scale=None, legend=None),
        strokeWidth=alt.StrokeWidth("tebal:Q", scale=None, legend=None),
        tooltip=[alt.Tooltip("ket:N", title="Pembayaran")]))
if len(pasangan) and pasangan["terkait"].any():
    q = pasangan[pasangan["terkait"]].assign(baris="Klaim")
    q["x"], q["x2"] = q["tgl_reakt"], q["tgl_masuk"]
    q["tengah"] = q["tgl_reakt"] + (q["tgl_masuk"] - q["tgl_reakt"]) / 2
    q["label"] = q["hari"].astype(int).astype(str) + " hari"
    q["ket"] = ("Aktif kembali " + q["tgl_reakt"].map(ui.tgl) + ", klaim besar " + q["label"]
                + " kemudian (" + q["tgl_masuk"].map(ui.tgl) + ")")
    q = q[["baris", "x", "x2", "tengah", "label", "ket"]].reset_index(drop=True)
    lapisan.append(alt.Chart(q).mark_rule(strokeWidth=3, color="#9A5F0E", opacity=0.5).encode(
        x=X("x"), x2="x2:T", y=y, tooltip=[alt.Tooltip("ket:N", title="Pola")]))
    # label bergantian di atas dan di bawah garis supaya pasangan yang berdekatan tidak bertumpuk
    for sisa, dy in ((0, -14), (1, 16)):
        bag = q[q.index % 2 == sisa]
        if len(bag):
            lapisan.append(alt.Chart(bag).mark_text(dy=dy, fontSize=11, fontWeight=700, color="#7A4A0B").encode(
                x=X("tengah"), y=y, text="label:N"))
if len(klaim):
    k_ = klaim.assign(baris="Klaim", x=klaim["tgl_masuk"])
    k_["kat"] = "Rawat jalan"
    k_.loc[(k_["jenis_layanan"] == "RJTL") & (k_["biaya_klaim"] >= ui.KLAIM_BESAR), "kat"] = "Rawat jalan ≥ Rp1 juta"
    k_.loc[(k_["jenis_layanan"] == "RITL") & (k_["cara_masuk"] == "terjadwal"), "kat"] = "Rawat inap terjadwal"
    k_.loc[(k_["jenis_layanan"] == "RITL") & (k_["cara_masuk"] == "IGD"), "kat"] = "Rawat inap lewat IGD"
    k_["ket"] = (k_["tgl_masuk"].map(ui.tgl) + ": " + k_["kat"].map(ui.kecil) + ", "
                 + k_["kelompok_layanan"].str.replace("_", " ") + ", " + k_["biaya_klaim"].map(ui.rp)
                 + k_["denda_pelayanan"].map(lambda v: f", denda pelayanan {ui.rp(v)}" if v else ""))
    k_["besar"] = k_["biaya_klaim"]
    lapisan.append(alt.Chart(k_[["baris", "kat", "x", "ket", "besar"]]).mark_circle(
        opacity=0.92, stroke="white", strokeWidth=0.8).encode(
        x=X("x"), y=y, color=warna,
        size=alt.Size("besar:Q", scale=alt.Scale(type="sqrt", domain=[0, 25_000_000], range=[18, 420]),
                      legend=None),
        tooltip=[alt.Tooltip("ket:N", title="Klaim")]))

if lapisan:
    grafik = alt.layer(*lapisan).properties(height=210).configure_view(stroke=None).configure(
        font="Tepat, sans-serif", background="transparent")
    st.altair_chart(grafik, width="stretch", theme="streamlit")


def _item(bentuk: str, teks: str) -> str:
    return f"<span>{bentuk}{ui.e(teks)}</span>"


kotak = lambda c: f'<i style="width:12px;height:9px;border-radius:2px;background:{c}"></i>'  # noqa: E731
garis = lambda c, w, h: f'<i style="width:{w}px;height:{h}px;background:{c}"></i>'  # noqa: E731
bulat = lambda c, d: f'<i style="width:{d}px;height:{d}px;border-radius:50%;background:{c}"></i>'  # noqa: E731
st.html('<div class="tp-legenda-lini">'
        + _item(kotak(KAT["Aktif"]), "Aktif") + _item(kotak(KAT["Nonaktif"]), "Nonaktif")
        + _item(kotak(KAT["Masa tunggu"]), "Masa tunggu")
        + _item(garis(KAT["Iuran 1 bulan"], 2, 12), "Iuran 1 bulan")
        + _item(garis(W["utama"], 3, 16), "Melunasi beberapa bulan")
        + _item(bulat(KAT["Rawat jalan"], 8), "Rawat jalan")
        + _item(bulat(KAT["Rawat jalan ≥ Rp1 juta"], 9), "Rawat jalan ≥ Rp1 juta")
        + _item(bulat(KAT["Rawat inap terjadwal"], 10), "Rawat inap terjadwal")
        + _item(bulat(KAT["Rawat inap lewat IGD"], 10), "Rawat inap IGD")
        + _item('<i style="width:0;height:14px;border-left:1.5px dashed #1E8A5F"></i>', "Aktif kembali")
        + _item(garis("#D9B88C", 18, 3), "Klaim besar ≤ 90 hari")
        + "</div>")

# ---------------------------------------------------------------- keputusan dan draf pesan
kiri, kanan = st.columns([2, 3], gap="large")

if utama == ui.PERINGATAN_DINI:
    sasaran = ("Pencegahan, berisiko menunggak", ui.SARAN[p["ew_saran"]], ui.PERINGATAN_DINI)
elif utama in ui.RUTE_AKSI:
    sasaran = ("Rute triase", R["nama"], p["rute"])
else:
    sasaran = None

ALASAN_TOLAK = ["Data tidak sesuai kondisi di lapangan",
                "Peserta sudah melunasi atau sudah ditangani",
                "Peserta tidak mampu, lebih tepat dirujuk cek PBI",
                "Ada penjelasan lain yang wajar, misalnya sakit atau kerja musiman",
                "Lainnya"]

with kiri:
    ui.judul_bagian("Keputusan petugas", "gavel",
                    "Keputusan tidak mengubah rute. Tersimpan selama sesi ini dan ikut di CSV unduhan "
                    "daftar kerja; penyimpanan permanen menyusul.")
    if sasaran is None:
        st.markdown("Tidak ada yang perlu diputuskan.")
    else:
        c, lmbt, ik = _warna_tindakan(utama)
        st.html(f'<div style="margin:0 0 .5rem">{ui.chip(sasaran[1], ik, c, lmbt)}</div>')
        kep = st.radio("Keputusan", ["setuju", "tolak"], index=None, horizontal=True, key=f"kep_{pid}",
                       format_func={"setuju": ":material/check_circle: Setuju",
                                    "tolak": ":material/cancel: Tolak"}.get,
                       label_visibility="collapsed")
        alasan = None
        if kep == "tolak":
            alasan = st.selectbox("Alasan menolak", ALASAN_TOLAK, index=None, key=f"alasan_{pid}",
                                  placeholder="Pilih alasan")
        catatan = st.text_area("Catatan", key=f"catatan_{pid}", height=80,
                               placeholder="Wajib bila alasannya Lainnya")
        if st.button("Simpan keputusan", icon=":material/save:", type="primary", disabled=kep is None,
                     key=f"simpan_{pid}"):
            if kep == "tolak" and not alasan:
                st.error("Pilih alasan menolak, lalu simpan lagi.")
            elif alasan == "Lainnya" and not catatan.strip():
                st.error("Tulis catatan untuk alasan Lainnya, lalu simpan lagi.")
            else:
                ui.keputusan()[pid] = dict(id_peserta=pid, sasaran=sasaran[0], kode=sasaran[2],
                                           keputusan=kep, alasan=alasan or "", catatan=catatan.strip(),
                                           waktu=datetime.now().strftime("%Y-%m-%d %H:%M"))
                st.toast("Keputusan disimpan", icon=":material/task_alt:")
        ada = ui.keputusan().get(pid)
        if ada:
            jam = datetime.strptime(ada["waktu"], "%Y-%m-%d %H:%M")
            teks = (f":material/task_alt: **{'Disetujui' if ada['keputusan'] == 'setuju' else 'Ditolak'}**, "
                    f"{jam.day} {ui.BULAN[jam.month - 1]} pukul {jam:%H.%M}")
            if ada["alasan"]:
                teks += f". {ada['alasan']}"
            st.markdown(teks)

def _antre_ai(kunci_antre: str) -> None:
    """Callback tombol AI: hanya menandai antrean (seketika). Panggilan AI-nya jalan di badan halaman,
    di dalam spinner, supaya petugas melihat bahwa sistem sedang bekerja (tunggu bisa sampai 45 detik)."""
    st.session_state[kunci_antre] = True


def _tulis_ulang_ai(peserta: dict, tindakan: str, kunci: str) -> None:
    """Hanya mengganti isi kotak draf bila AI berhasil dan lolos aturan; bila tidak, isi kotak (termasuk
    sunting petugas) dibiarkan dan alasannya tampil di bawahnya. Harus dipanggil SEBELUM kotak draf dibuat
    pada putaran skrip yang sama, karena state widget tidak boleh diubah setelah widgetnya dirender."""
    h = llm.susun(peserta, tindakan, pakai_ai=st.session_state.get("ai_aktif", True))
    st.session_state[f"ai_hasil_{peserta['id_peserta']}"] = h
    if h.status == "ai":
        st.session_state[kunci] = h.draf[0]["isi"]


with kanan:
    ui.judul_bagian("Draf pesan", "message-square-text",
                    "Draf awal dari template, bisa disunting sebelum dikirim. Tombol AI menulis ulang kata-katanya: "
                    "rute tidak berubah, nomor peserta tidak dikirim ke AI, dan bila AI tidak tersedia template "
                    "tetap dipakai. Rute verifikasi hanya punya catatan untuk petugas, tanpa AI.")
    draf = pesan_template.susun(p, utama)
    if not draf:
        st.markdown("Tidak ada pesan bulan ini.")
    else:
        for d in draf:
            kunci_draf = f"draf_{pid}_{d['sumber']}"
            st.html(f'<div style="margin:0 0 .5rem">{ui.chip(d["judul"], "file-text")}</div>')
            # nilai awal lewat session state (bukan value=) karena tombol AI menimpa isinya lewat state yang sama
            st.session_state.setdefault(kunci_draf, d["isi"])
            kunci_antre = f"ai_antre_{pid}"
            if d["jenis"] == "pesan_peserta" and st.session_state.pop(kunci_antre, False):
                with st.spinner(f"AI sedang menyusun draf. Biasanya 3 sampai 30 detik, paling lama "
                                f"{llm.batas_waktu():g} detik. Bila gagal, template tetap dipakai."):
                    _tulis_ulang_ai(p, utama, kunci_draf)
            st.text_area(d["judul"], height=280, key=kunci_draf, label_visibility="collapsed")
            if d["jenis"] == "pesan_peserta":
                a1, a2 = st.columns([3, 2], vertical_alignment="center")
                a1.button("Tulis ulang dengan AI", icon=":material/auto_awesome:", key=f"ai_{pid}",
                          on_click=_antre_ai, args=(kunci_antre,),
                          disabled=not st.session_state.get("ai_aktif", True))
                a2.toggle("Pakai AI", value=True, key="ai_aktif",
                          help="Matikan untuk bekerja hanya dengan template, misalnya saat API tidak tersedia.")
                hasil_ai = st.session_state.get(f"ai_hasil_{pid}")
                if not st.session_state.get("ai_aktif", True):
                    st.caption("AI dimatikan petugas. Draf dari template.")
                elif hasil_ai is None or hasil_ai.jalur != utama:
                    st.caption("Draf dari template.")
                elif hasil_ai.status == "ai":
                    st.html(ui.chip("Disusun AI", "message-square-text", ui.WARNA["utama"], "#E1EEE6"))
                    st.caption(hasil_ai.keterangan)
                    if hasil_ai.ringkasan_petugas:
                        st.caption(f"Ringkasan untuk petugas: {hasil_ai.ringkasan_petugas}")
                else:
                    st.html(ui.chip("Template", "info", "#9A5F0E", "#F5E6C8"))
                    st.caption(hasil_ai.keterangan + " Isi kotak tidak diubah.")

# ---------------------------------------------------------------- riwayat
ui.judul_bagian("Riwayat", "history", "Angka di setiap tab adalah jumlah baris: berapa kali membayar, "
                "berapa klaim, dan berapa kali status berganti sejak Januari 2023.")
t1, t2, t3 = st.tabs([f":material/payments: Pembayaran ({ui.angka(len(bayar))})",
                      f":material/local_hospital: Klaim ({ui.angka(len(klaim))})",
                      f":material/swap_horiz: Perubahan status ({ui.angka(len(status))})"])
with t1:
    if len(bayar):
        v = pd.DataFrame({
            "Tanggal bayar": bayar["tgl_bayar"].map(ui.tgl).values,
            "Periode": (bayar["periode_awal"].map(ui.bulan_tahun) + " sampai "
                        + bayar["periode_akhir"].map(ui.bulan_tahun)).values,
            "Bulan dibayar": bayar["jumlah_bulan_dibayar"].astype(int).values,
            "Nominal": bayar["nominal"].map(ui.rp).values,
            "Kanal": bayar["kanal"].map(ui.KANAL).values,
        }).iloc[::-1]
        st.dataframe(v, hide_index=True, height=min(420, 38 + 35 * len(v)))
    else:
        st.markdown("Belum ada pembayaran tercatat.")
with t2:
    if len(klaim):
        v = pd.DataFrame({
            "Tanggal masuk": klaim["tgl_masuk"].map(ui.tgl).values,
            "Layanan": klaim["jenis_layanan"].map({"RITL": "Rawat inap", "RJTL": "Rawat jalan"}).values,
            "Cara masuk": klaim["cara_masuk"].map({"poli": "Poli", "IGD": "IGD", "terjadwal": "Terjadwal"}).values,
            "Kelompok": klaim["kelompok_layanan"].str.replace("_", " ").str.capitalize().values,
            "Biaya": klaim["biaya_klaim"].map(ui.rp).values,
            "Denda pelayanan": klaim["denda_pelayanan"].map(lambda v: ui.rp(v) if v else "").values,
        }).iloc[::-1]
        st.dataframe(v, hide_index=True, height=min(420, 38 + 35 * len(v)))
    else:
        st.markdown("Belum ada klaim tercatat.")
with t3:
    v = pd.DataFrame({
        "Mulai": status["tgl_mulai"].map(ui.tgl).values,
        "Selesai": status["tgl_selesai"].map(ui.tgl).values,
        "Status": status["status"].map(ui.STATUS).values,
    }).iloc[::-1]
    st.dataframe(v, hide_index=True, height=min(420, 38 + 35 * len(v)))
