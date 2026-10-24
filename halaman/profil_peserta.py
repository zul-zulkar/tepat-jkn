"""Halaman Profil peserta: ringkasan, rute + alasan, linimasa 3 tahun, keputusan petugas, draf pesan."""
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import pesan_template
import tepat_ui as ui

T = ui.tabel_peserta()
IDX = T.set_index("id_peserta")
W = ui.WARNA


def _buka(pid: str) -> None:
    st.query_params["id"] = pid


def _cari() -> None:
    v = ui.normalkan_id(st.session_state.get("cari_id", ""))
    if v:
        st.query_params["id"] = v
    st.session_state["cari_id"] = ""


# ---------------------------------------------------------------- baris atas
a, b = st.columns([3, 2], vertical_alignment="bottom")
with a:
    st.page_link(ui.HALAMAN_DAFTAR, label="Kembali ke daftar kerja", icon=":material/arrow_back:")
b.text_input("Cari ID peserta", key="cari_id", on_change=_cari, placeholder="Contoh: P-002329 atau 2329")

pid = st.query_params.get("id")
pid = ui.normalkan_id(pid) if pid else st.session_state.get("_pid_terakhir")

if not pid:
    ui.kepala("Profil peserta", "Riwayat tiga tahun, rute, alasan, dan keputusan petugas untuk satu peserta. "
              "Pilih peserta dari daftar kerja, ketik ID di atas, atau buka salah satu contoh.")
    contoh = []
    for r in ui.RUTE_AKSI:
        d = T[T["rute"] == r].sort_values(["tunggakan_rp", "id_peserta"], ascending=[False, True])
        if r == "pengingat_autodebet_REHAB":
            d = d[d["tunggakan_bulan"] > 0]
        if len(d):
            contoh.append((d.iloc[0]["id_peserta"], ui.RUTE[r]["nama"]))
    p1 = T[T["ew_peringkat"] == 1]
    if len(p1):
        contoh.append((p1.iloc[0]["id_peserta"], "Peringatan dini, peringkat 1"))
    st.markdown("**Contoh per rute**")
    kol = st.columns(len(contoh))
    for c, (i, lbl) in zip(kol, contoh):
        c.button(i, key=f"contoh_{i}", on_click=_buka, args=(i,), width="stretch")
        c.caption(lbl)
    st.stop()

if pid not in IDX.index:
    ui.kepala("Profil peserta", "")
    st.markdown(f"ID **{ui.e(pid)}** tidak ada di data peserta mandiri. Periksa penulisannya; "
                "formatnya P- diikuti enam angka, misalnya P-002329.")
    st.stop()

st.session_state["_pid_terakhir"] = pid
p = IDX.loc[pid].to_dict() | {"id_peserta": pid}
p["alasan_rapi"] = ui.alasan_rapi(p["alasan"])

status = ui.linimasa("linimasa_status", pid).sort_values("tgl_mulai")
bayar = ui.linimasa("linimasa_bayar", pid).sort_values("tgl_bayar")
klaim = ui.linimasa("linimasa_klaim", pid).sort_values("tgl_masuk")
reakt = ui.linimasa("linimasa_reaktivasi", pid).sort_values("tgl_reakt")
pasangan = ui.pasangan_reaktivasi_klaim(reakt, klaim)

# daftar peringatan dini memakai filter dan kapasitas yang sedang dipakai di halaman Daftar kerja
ew_list, _ = ui.daftar_ew(T, st.session_state.get("f_wilayah", []), st.session_state.get("f_k", 5))
masuk_ew = pid in set(ew_list["id_peserta"])
utama = ui.tindakan_utama(pd.Series([p["rute"]]), pd.Series([masuk_ew])).iloc[0]

# ---------------------------------------------------------------- kepala dan fakta
m = ui.manifest()
st.html(
    f'<div class="tp-cap" style="margin:.8rem 0 0"><b>Data sintetis.</b> Posisi {ui.tgl(m["triase_per_tanggal"])}.</div>'
    f'<div class="tp-id">{ui.e(pid)}</div>'
    f'<p class="tp-ringkas">Peserta {ui.e(p["segmen_kepesertaan"])} mandiri kelas {int(p["kelas"])}, '
    f'wilayah {ui.e(p["kode_wilayah"])}. Terdaftar {ui.tgl(p["tgl_daftar"])}.</p>')

sejak = status.iloc[-1]["tgl_mulai"] if len(status) else None
klaim_rp, iuran_rp = float(p["klaim_rp"] or 0), float(p["iuran_rp"] or 0)
fakta = [
    ("Status per 31 Des 2025", ui.STATUS.get(p["status_akhir"], p["status_akhir"]),
     f"sejak {ui.tgl(sejak)}" if sejak is not None else ""),
    ("Tunggakan", f"{int(p['tunggakan_bulan'])} bulan", ui.rp(p["tunggakan_rp"])),
    ("Iuran", ui.rp(p["iuran_bulanan"]), "per bulan"),
    ("Autodebet", "Ya" if p["autodebet"] else "Tidak", ""),
    ("DTSEN", ui.DESIL.get(p["rentang_desil"], "-"), ""),
    ("Klaim dibanding iuran", (ui.angka(p["rasio_klaim_iuran"], 2) + "×") if iuran_rp else "-",
     f"{ui.rp(klaim_rp)} klaim, {ui.rp(iuran_rp)} iuran"),
]
st.html('<dl class="tp-fakta">' + "".join(
    f'<div><dt>{ui.e(k)}</dt><dd>{ui.e(v)}{f"<small>{ui.e(s)}</small>" if s else ""}</dd></div>'
    for k, v, s in fakta) + "</dl>")

# ---------------------------------------------------------------- rute dan peringatan dini
R = ui.RUTE[p["rute"]]
angka_rute = ""
if p["rute"] != "tanpa_tindakan":
    angka_rute = ('<div class="tp-angka">'
                  f'<span>Aktif kembali <b>{int(p["n_reaktivasi"])} kali</b></span>'
                  f'<span>Diikuti klaim besar ≤ 90 hari <b>{int(p["n_reakt_terkait_klaim"])} kali</b></span>'
                  f'<span>Waktu aktif <b>{ui.persen(p["rasio_hari_aktif"], 0)}</b></span></div>')
pagar = ('<p class="tp-pagar">Peserta DTSEN desil 1–5 tidak pernah masuk rute ini.</p>'
         if p["rute"] == "verifikasi_pola_reaktivasi" else "")
panel_triase = (
    f'<section class="tp-rute{"" if utama == p["rute"] else " tp-sekunder"}" style="--c:{R["warna"]}">'
    f'<p class="sumber">Rute triase</p>'
    f'<p class="nama">{ui.e(R["nama"])}</p>'
    + (f'<p class="alasan">{ui.e(p["alasan_rapi"])}</p>' if p["alasan_rapi"] else "")
    + f'<p class="arti">{ui.e(R["arti"])}</p>{angka_rute}{pagar}</section>')

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
        f'<section class="tp-rute{"" if utama == ui.PERINGATAN_DINI else " tp-sekunder"}" '
        f'style="--c:{ui.WARNA_EW}"><p class="sumber">Peringatan dini, '
        f'{ui.bulan_tahun(str(e_["bulan"]))}</p>'
        f'<p class="nama">Peluang menunggak 3 bulan: {ui.persen(e_["skor"], 1)}</p>'
        f'<p class="alasan">{ui.e(ui.alasan_rapi(e_["alasan"]))}</p>'
        f'<p class="arti">Peringkat {ui.angka(int(e_["peringkat"]))} dari {ui.angka(m["ew_n_dinilai"])} '
        f'peserta aktif. {status_daftar} Saran: {ui.e(ui.kecil(ui.SARAN.get(e_["saran_intervensi"], "-")))}.</p>'
        + (f'<p class="tp-pagar" style="margin-top:.7rem">Penyumbang terbesar skor</p>'
           f'<div class="tp-kontrib">{baris}</div>' if kontrib else "")
        + "</section>")

if utama == "tanpa_tindakan":
    kalimat = "Tidak ada tindakan bulan ini."
else:
    lain = [ui.RUTE[p["rute"]]["nama"]] if p["rute"] not in ("tanpa_tindakan", utama) else []
    lain += ["Peringatan dini"] if masuk_ew and utama != ui.PERINGATAN_DINI else []
    kalimat = f"Tindakan bulan ini: <b>{ui.e(ui.nama_tindakan(utama))}</b>."
    if lain:
        kalimat += (f" Juga memenuhi {ui.e(ui.kecil(', '.join(lain)))}, tetapi tidak dijalankan: "
                    "satu peserta hanya mendapat satu tindakan.")
st.html(f'<p class="tp-utama">{kalimat}</p>')

if panel_ew:
    k1, k2 = st.columns(2, gap="large")
    k1.html(panel_triase)
    k2.html(panel_ew)
else:
    st.html(panel_triase)

# ---------------------------------------------------------------- linimasa
st.subheader("Linimasa Januari 2023 sampai Desember 2025", anchor=False)

BARIS = ["Status", "Iuran dibayar", "Klaim"]
KAT = {
    "Aktif": "#BFDFC8", "Nonaktif": "#EFC6BD", "Masa tunggu": "#F1DDAA",
    "Iuran 1 bulan": "#8C99A6", "Melunasi beberapa bulan": W["utama"],
    "Rawat jalan": "#B4BDC7", "Rawat jalan ≥ Rp1 juta": "#6A7785",
    "Rawat inap terjadwal": "#B4650E", "Rawat inap lewat IGD": "#B23A2E",
}
skala = alt.Scale(domain=list(KAT), range=list(KAT.values()))
X0, X1 = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-01-01")
label_bulan = ("['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'][month(datum.value)]"
               " + (month(datum.value) == 0 ? ' ' + year(datum.value) : '')")
sx = alt.Scale(domain=[alt.DateTime(year=2023, month=1, date=1), alt.DateTime(year=2026, month=1, date=1)])
ax = alt.Axis(title=None, labelExpr=label_bulan, tickCount={"interval": "month", "step": 3},
              grid=True, gridColor="#EEF1F4", domain=False, tickColor=W["garis"], labelColor=W["tinta2"],
              labelFontSize=11, labelPadding=6)
y = alt.Y("baris:N", sort=BARIS, scale=alt.Scale(domain=BARIS, paddingInner=0.3, paddingOuter=0.15),
          axis=alt.Axis(title=None, domain=False, ticks=False, labelColor=W["tinta2"], labelFontSize=12,
                        labelPadding=10, labelFontWeight=500))
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
    lapisan.append(alt.Chart(s[["baris", "kat", "x", "x2", "ket"]]).mark_bar(cornerRadius=2).encode(
        x=X("x"), x2="x2:T", y=y, color=warna,
        tooltip=[alt.Tooltip("ket:N", title="Status")]))
# garis reaktivasi di belakang tanda pembayaran
if len(reakt):
    r_ = reakt.assign(x=reakt["tgl_reakt"])
    r_["ket"] = ("Aktif kembali " + r_["tgl_reakt"].map(ui.tgl) + ", melunasi "
                 + r_["bulan_tertunggak"].astype(int).astype(str) + " bulan tertunggak")
    lapisan.append(alt.Chart(r_[["x", "ket"]]).mark_rule(strokeDash=[3, 3], strokeWidth=1.2,
                                                         color="#5E9C97", opacity=0.75).encode(
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
    lapisan.append(alt.Chart(q).mark_rule(strokeWidth=3, color="#B4650E", opacity=0.55).encode(
        x=X("x"), x2="x2:T", y=y, tooltip=[alt.Tooltip("ket:N", title="Pola")]))
    # label bergantian di atas dan di bawah garis supaya pasangan yang berdekatan tidak bertumpuk
    for sisa, dy in ((0, -14), (1, 16)):
        bag = q[q.index % 2 == sisa]
        if len(bag):
            lapisan.append(alt.Chart(bag).mark_text(dy=dy, fontSize=11, fontWeight=600, color="#8F4F0A").encode(
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
        opacity=0.9, stroke="white", strokeWidth=0.8).encode(
        x=X("x"), y=y, color=warna,
        size=alt.Size("besar:Q", scale=alt.Scale(type="sqrt", domain=[0, 25_000_000], range=[18, 420]),
                      legend=None),
        tooltip=[alt.Tooltip("ket:N", title="Klaim")]))

if lapisan:
    grafik = alt.layer(*lapisan).properties(height=210).configure_view(stroke=None).configure(
        font="Tepat, sans-serif")
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
        + _item(garis(W["utama"], 3, 16), "Melunasi beberapa bulan sekaligus")
        + _item(bulat(KAT["Rawat jalan"], 8), "Rawat jalan")
        + _item(bulat(KAT["Rawat jalan ≥ Rp1 juta"], 9), "Rawat jalan ≥ Rp1 juta")
        + _item(bulat(KAT["Rawat inap terjadwal"], 10), "Rawat inap terjadwal")
        + _item(bulat(KAT["Rawat inap lewat IGD"], 10), "Rawat inap lewat IGD")
        + _item(f'<i style="width:0;height:14px;border-left:1.5px dashed {W["utama"]}"></i>', "Aktif kembali")
        + _item(garis("#E1B98A", 18, 3), "Klaim besar ≤ 90 hari setelah aktif kembali")
        + "</div>")

# ---------------------------------------------------------------- keputusan dan draf pesan
kiri, kanan = st.columns([2, 3], gap="large")

if utama == ui.PERINGATAN_DINI:
    sasaran = ("Peringatan dini", ui.SARAN[p["ew_saran"]], ui.PERINGATAN_DINI)
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
    st.subheader("Keputusan petugas", anchor=False)
    if sasaran is None:
        st.markdown("Peserta ini tidak masuk rute mana pun, jadi tidak ada yang perlu diputuskan.")
    else:
        st.html(f'<p class="tp-ket" style="margin:0 0 .4rem">{ui.e(sasaran[0])}: '
                f'<b style="color:{W["tinta"]}">{ui.e(sasaran[1])}</b></p>')
        kep = st.radio("Keputusan", ["setuju", "tolak"], index=None, horizontal=True, key=f"kep_{pid}",
                       format_func={"setuju": "Setuju dengan rute", "tolak": "Tolak rute"}.get,
                       label_visibility="collapsed")
        alasan = None
        if kep == "tolak":
            alasan = st.selectbox("Alasan menolak", ALASAN_TOLAK, index=None, key=f"alasan_{pid}",
                                  placeholder="Pilih alasan")
        catatan = st.text_area("Catatan", key=f"catatan_{pid}", height=90,
                               placeholder="Wajib diisi bila alasannya Lainnya.")
        if st.button("Simpan keputusan", type="primary", disabled=kep is None, key=f"simpan_{pid}"):
            if kep == "tolak" and not alasan:
                st.error("Pilih alasan menolak, lalu simpan lagi.")
            elif alasan == "Lainnya" and not catatan.strip():
                st.error("Tulis catatan untuk alasan Lainnya, lalu simpan lagi.")
            else:
                ui.keputusan()[pid] = dict(id_peserta=pid, sasaran=sasaran[0], kode=sasaran[2],
                                           keputusan=kep, alasan=alasan or "", catatan=catatan.strip(),
                                           waktu=datetime.now().strftime("%Y-%m-%d %H:%M"))
                st.toast("Keputusan disimpan")
        ada = ui.keputusan().get(pid)
        if ada:
            jam = datetime.strptime(ada["waktu"], "%Y-%m-%d %H:%M")
            teks = (f"Tersimpan: **{'disetujui' if ada['keputusan'] == 'setuju' else 'ditolak'}**, "
                    f"{jam.day} {ui.BULAN[jam.month - 1]} pukul {jam:%H.%M}.")
            if ada["alasan"]:
                teks += f" Alasan: {ui.kecil(ada['alasan'])}."
            st.markdown(teks)
        st.caption("Keputusan tidak mengubah rute. Tersimpan selama sesi ini dan ikut di CSV unduhan "
                   "daftar kerja; penyimpanan permanen menyusul.")

with kanan:
    st.subheader("Draf pesan", anchor=False)
    draf = pesan_template.susun(p, utama)
    if not draf:
        st.markdown("Tidak ada pesan. Peserta tidak masuk rute mana pun bulan ini.")
    else:
        tab = st.tabs([f"{d['sumber']}: {d['judul'].lower()}" for d in draf]) if len(draf) > 1 else [st.container()]
        for t, d in zip(tab, draf):
            with t:
                st.text_area(d["judul"], d["isi"], height=300, key=f"draf_{pid}_{d['sumber']}",
                             label_visibility="collapsed")
        st.caption("Draf untuk tindakan bulan ini, dari template, bisa disunting sebelum dikirim. "
                   "Lapisan AI menyusul dan tidak mengubah rute.")

# ---------------------------------------------------------------- riwayat
st.subheader("Riwayat", anchor=False)
t1, t2, t3 = st.tabs([f"Pembayaran  {ui.angka(len(bayar))}", f"Klaim  {ui.angka(len(klaim))}",
                      f"Status  {ui.angka(len(status))}"])
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
