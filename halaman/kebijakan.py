"""Halaman Kebijakan: uji lonjakan hari ke-45, rawat inap terjadwal dibanding plasebo IGD.

Untuk unit kebijakan. Hanya membaca bunching_harian dan bunching_ringkasan. siapkan_app.py menghitung
keduanya dengan fungsi dan RNG yang sama dengan cek_sinyal.py, jadi angkanya sama dengan proposal.

Dua aturan tafsir yang dijaga di halaman ini:
- Ukuran ujinya LOMPATAN (kelebihan hari 46-60 + kekurangan hari 31-45), bukan kelebihan saja. Kurva
  perkiraan bisa terlalu rendah di hari yang dikecualikan dari fit, dan itu menaikkan kedua jendela.
- Lompatan bukan jumlah rawat inap yang ditunda (kasus yang pindah terhitung dua kali). Perkiraan kasus
  yang ditunda adalah KELEBIHAN di hari 46-60.
"""
import altair as alt
import pandas as pd
import streamlit as st

import tepat_ui as ui
from ikon import ikon

W = ui.WARNA
HARIAN, R = ui.bunching()


def _jendela(nama: str) -> tuple[int, int]:
    """Hari awal dan akhir jendela, dibaca dari data supaya batasnya hanya ada di cek_sinyal.py."""
    h = HARIAN.loc[HARIAN["jendela"] == nama, "hari"]
    return int(h.min()), int(h.max())


KURANG, LEBIH = _jendela("kurang_31_45"), _jendela("lebih_46_60")
BATAS = int(R.loc["terjadwal", "batas_hari"])
(DERAJAT,) = ui._konstanta("cek_sinyal.py", "DERAJAT")  # derajat kurva perkiraan
MAKS = int(HARIAN["hari"].max())

PANEL = {
    "terjadwal": dict(nama="Rawat inap terjadwal", sumber="Bisa ditunda", warna="#9A5F0E",
                      lembut="#F5E6C8", ikon="calendar"),
    "IGD": dict(nama="Rawat inap darurat lewat IGD", sumber="Pembanding: tidak bisa ditunda",
                warna="#B24A2B", lembut="#F6E4D6", ikon="siren"),
}


def bil(x, desimal: int = 0) -> str:
    """Angka gaya Indonesia dengan tanda minus tipografis."""
    return ui.angka(round(float(x), desimal) if desimal else round(float(x)), desimal).replace("-", "−")


def rentang(lo: float, hi: float) -> str:
    return f"{bil(lo)} s.d. {bil(hi)}" if round(lo) < 0 else f"{bil(lo)}–{bil(hi)}"


def ada_lonjakan(cara: str) -> bool:
    r = R.loc[cara]
    return (not bool(r["ik_lompat_mencakup_0"])) and r["lompat"] > 0


hari_txt = lambda a_b: f"{a_b[0]}–{a_b[1]}"  # noqa: E731

ui.kepala("Uji lonjakan hari ke-45",
          f"Apakah peserta menunda rawat inap terjadwal sampai denda pelayanan {BATAS} hari setelah aktif "
          "kembali lewat? Rawat inap darurat lewat IGD menjadi pembanding karena tidak bisa ditunda. "
          "Untuk unit kebijakan BPJS Kesehatan, dilaporkan per kuartal.")

# ---------------------------------------------------------------- kesimpulan
t_ada, i_ada = ada_lonjakan("terjadwal"), ada_lonjakan("IGD")
if t_ada and not i_ada:
    vonis, c_v, l_v, ik_v = "Lonjakan hanya muncul pada rawat inap yang bisa ditunda", "#9A5F0E", "#F5E6C8", "trending-up"
    rinci = (f"Rawat inap terjadwal menumpuk tepat setelah hari ke-{BATAS}; rawat inap darurat tidak. Pola ini "
             "cocok dengan peserta yang menunda rawat inap sampai denda pelayanan tidak berlaku lagi.")
elif t_ada and i_ada:
    vonis, c_v, l_v, ik_v = "Pembanding IGD ikut melonjak", "#9A3F12", "#F6E4D6", "circle-x"
    rinci = ("Lonjakan rawat inap terjadwal belum bisa dibaca sebagai penundaan. Periksa kurva perkiraan dan "
             "rawat inap terencana yang masuk lewat IGD.")
else:
    vonis, c_v, l_v, ik_v = f"Tidak ada lonjakan yang terdeteksi setelah hari ke-{BATAS}", W["tinta2"], W["permukaan"], "circle-check-big"
    rinci = "Bukan bukti tidak ada penundaan: penundaan kecil bisa lolos dari uji ini."

st.html(f'<div class="tp-tindakan" style="--c:{c_v};--l:{l_v}"><div class="tp-bulat">{ikon(ik_v, 20, c_v)}</div>'
        f'<div style="flex:1 1 320px"><div class="lbl">Hasil uji</div><div class="isi">{ui.e(vonis)}</div>'
        f'<div class="lain" style="margin-top:.2rem">{ui.e(rinci)}</div>'
        f'<div class="lain" style="margin-top:.35rem;display:flex;gap:.35rem;align-items:flex-start">'
        f'{ikon("flask-conical", 14, W["tinta2"])}<span>Data sintetis: penundaan sengaja dibuat di data buatan untuk '
        f'menguji alat ini. Halaman ini menunjukkan ujinya bisa menemukan pola itu, bukan bahwa peserta asli '
        f'menunda.</span></div></div></div>')

# ---------------------------------------------------------------- angka utama
rt, ri = R.loc["terjadwal"], R.loc["IGD"]


def _kartu(nama_ikon: str, c: str, l: str, n: str, label: str, ket: str) -> str:
    return (f'<div class="tp-kartu" style="--c:{c};--l:{l};align-items:flex-start">'
            f'<div class="tp-bulat">{ikon(nama_ikon, 20, c)}</div>'
            f'<div><div class="n">{ui.e(n)}</div><div class="l" style="color:#3D4B46;font-weight:600">'
            f'{ui.e(label)}</div><div class="l">{ui.e(ket)}</div></div></div>')


kartu = [
    _kartu("calendar", PANEL["terjadwal"]["warna"], PANEL["terjadwal"]["lembut"], bil(rt["lompat"]),
           "Lompatan rawat inap terjadwal",
           f"Rentang 95%: {rentang(rt['lompat_ik_bawah'], rt['lompat_ik_atas'])}"
           + (", di atas nol" if t_ada else ", mencakup nol")),
    _kartu("siren", PANEL["IGD"]["warna"], PANEL["IGD"]["lembut"], bil(ri["lompat"]),
           "Lompatan IGD (pembanding)",
           f"Rentang 95%: {rentang(ri['lompat_ik_bawah'], ri['lompat_ik_atas'])}"
           + (", di atas nol" if i_ada else ", mencakup nol")),
    _kartu("trending-up", W["utama"], W["utama_lembut"], bil(rt["lebih"]),
           f"Perkiraan rawat inap yang ditunda ke hari {hari_txt(LEBIH)}",
           f"Rentang 95%: {rentang(rt['lebih_ik_bawah'], rt['lebih_ik_atas'])}"),
]
if pd.notna(rt["denda_terhindar_rp"]):
    kartu.append(_kartu("receipt", W["tinta2"], W["permukaan"],
                        f"Rp{ui.angka(round(rt['denda_terhindar_rp'] / 1e6))} juta",
                        "Perkiraan denda pelayanan yang lolos",
                        "Biaya klaim sintetis; satu rawat inap per aktif kembali, denda paling tinggi Rp20 juta"))
st.html(f'<div class="tp-kartu-grid">{"".join(kartu)}</div>')

# ---------------------------------------------------------------- grafik
ui.judul_bagian("Rawat inap per hari setelah peserta aktif kembali", "activity",
                f"Batang: kasus nyata per hari. Garis: perkiraan jumlah kasus kalau tidak ada yang menunda, dari "
                f"kurva yang dipasang ke hari 1–{KURANG[0] - 1} dan {LEBIH[1] + 1}–{MAKS}. Hari 0 tidak digambar. "
                "Sumbu tegak tiap grafik berbeda karena jumlah kasusnya berbeda.")

kotak = lambda c, o=1: f'<i style="width:12px;height:9px;border-radius:2px;background:{c};opacity:{o}"></i>'  # noqa: E731
st.html('<div class="tp-legenda-lini" style="margin-bottom:.7rem">'
        f'<span>{kotak(PANEL["terjadwal"]["warna"])}{kotak(PANEL["IGD"]["warna"])}Kasus nyata per hari</span>'
        f'<span><i style="width:18px;height:2px;background:{W["tinta"]}"></i>Perkiraan tanpa penundaan</span>'
        f'<span>{kotak("#DDD9CC")}Jendela uji: hari {hari_txt(KURANG)} dan {hari_txt(LEBIH)}</span>'
        f'<span><i style="width:0;height:12px;border-left:1.5px dashed {W["tinta3"]}"></i>Batas denda hari ke-{BATAS}</span>'
        '</div>')


def grafik(cara: str) -> alt.LayerChart:
    P = PANEL[cara]
    d = HARIAN[(HARIAN["cara_masuk"] == cara) & (HARIAN["hari"] >= 1)].copy()
    d["x1"], d["x2"] = d["hari"] - 0.42, d["hari"] + 0.42
    d["op"] = d["jendela"].isin(["kurang_31_45", "lebih_46_60"]).map({True: 1.0, False: 0.45})
    d["ket"] = ("Hari ke-" + d["hari"].astype(str) + ": " + d["hitung"].astype(str) + " kasus, perkiraan "
                + d["cf"].map(lambda v: ui.angka(v, 1)))
    ymax = float(max(d["hitung"].max(), d["cf"].max())) * 1.22
    sx = alt.Scale(domain=[0, MAKS + 1], nice=False, zero=False)
    sy = alt.Scale(domain=[0, ymax], nice=False)
    ax_x = alt.Axis(title="Hari sejak aktif kembali sampai masuk rawat inap", values=[1, 15, 30, 45, 60, 90, 120],
                    grid=False, domainColor=W["garis"], tickColor=W["garis"], labelColor=W["tinta3"],
                    titleColor=W["tinta3"], titleFontWeight=500, titleFontSize=11.5, labelFontSize=11)
    ax_y = alt.Axis(title="Kasus per hari", grid=True, gridColor="#E6E5DE", domain=False, ticks=False, tickCount=5,
                    labelColor=W["tinta3"], titleColor=W["tinta3"], titleFontWeight=500, titleFontSize=11.5,
                    labelFontSize=11, labelPadding=6)

    pita = pd.DataFrame({"x1": [KURANG[0] - 0.5, LEBIH[0] - 0.5], "x2": [KURANG[1] + 0.5, LEBIH[1] + 0.5],
                         "tengah": [(KURANG[0] + KURANG[1]) / 2, (LEBIH[0] + LEBIH[1]) / 2],
                         "label": [hari_txt(KURANG), hari_txt(LEBIH)], "y": ymax * 0.965})
    lapisan = [
        alt.Chart(pita).mark_rect(color="#ECEADF", opacity=0.9).encode(
            x=alt.X("x1:Q", scale=sx, axis=ax_x), x2="x2:Q"),
        alt.Chart(pita).mark_text(fontSize=10, fontWeight=600, color=W["tinta3"], baseline="top").encode(
            x=alt.X("tengah:Q", scale=sx), y=alt.Y("y:Q", scale=sy), text="label:N"),
        alt.Chart(d[["x1", "x2", "hitung", "op", "ket"]]).mark_bar(color=P["warna"], cornerRadiusTopLeft=1.5,
                                                                    cornerRadiusTopRight=1.5).encode(
            x=alt.X("x1:Q", scale=sx), x2="x2:Q", y=alt.Y("hitung:Q", scale=sy, axis=ax_y), y2=alt.datum(0),
            opacity=alt.Opacity("op:Q", scale=None, legend=None),
            tooltip=[alt.Tooltip("ket:N", title=P["nama"])]),
        alt.Chart(d[["hari", "cf"]]).mark_line(color=W["tinta"], strokeWidth=2, interpolate="monotone").encode(
            x=alt.X("hari:Q", scale=sx), y=alt.Y("cf:Q", scale=sy)),
        alt.Chart(pd.DataFrame({"x": [BATAS + 0.5]})).mark_rule(
            color=W["tinta3"], strokeDash=[4, 3], strokeWidth=1.3).encode(x=alt.X("x:Q", scale=sx)),
        alt.Chart(pd.DataFrame({"x": [BATAS - 0.6], "y": [ymax * 0.8], "t": ["batas denda"]})).mark_text(
            align="right", fontSize=10.5, color=W["tinta3"]).encode(
            x=alt.X("x:Q", scale=sx), y=alt.Y("y:Q", scale=sy), text="t:N"),
    ]
    return (alt.layer(*lapisan).properties(height=280).configure_view(stroke=None)
            .configure(font="Tepat, sans-serif", background="transparent"))


def ringkas_jendela(cara: str) -> str:
    d = HARIAN[HARIAN["cara_masuk"] == cara]
    r = R.loc[cara]
    kotak_ = []
    for (a, b), nama, selisih in ((KURANG, "sebelum batas", -r["kurang"]), (LEBIH, "sesudah batas", r["lebih"])):
        w = d[d["hari"].between(a, b)]
        arah = "turun" if round(selisih) < 0 else "naik"
        kata = "kurang" if round(selisih) < 0 else "lebih"
        kotak_.append(f'<div>Hari {a}–{b}, {nama}<b>{ui.angka(int(w["hitung"].sum()))} kasus</b>'
                      f'perkiraan {ui.angka(round(w["cf"].sum()))} → <span class="{arah}">{kata} '
                      f'{ui.angka(abs(round(selisih)))}</span></div>')
    return f'<div class="tp-jendela">{"".join(kotak_)}</div>'


k1, k2 = st.columns(2, gap="medium")
for kolom, cara in ((k1, "terjadwal"), (k2, "IGD")):
    P, r, ada = PANEL[cara], R.loc[cara], ada_lonjakan(cara)
    with kolom.container(border=True, key=f"tpgrafik_{cara}"):
        st.html(f'<div class="tp-grafik-kepala" style="--c:{P["warna"]};--l:{P["lembut"]}">'
                f'<div class="tp-bulat">{ikon(P["ikon"], 20, P["warna"])}</div>'
                f'<div><p class="sumber">{ui.e(P["sumber"])}</p><p class="nama">{ui.e(P["nama"])}</p></div>'
                f'<span class="vonis">'
                + (ui.chip("Ada lonjakan", "trending-up", "#9A3F12", "#F6E4D6") if ada
                   else ui.chip("Tidak ada lonjakan", "circle-check-big", W["utama"], W["utama_lembut"]))
                + "</span></div>")
        st.altair_chart(grafik(cara), width="stretch", theme="streamlit")
        st.html(ringkas_jendela(cara)
                + f'<p class="tp-catatan-kecil">Lompatan = kekurangan sebelum batas + kelebihan sesudah batas = '
                  f'{bil(r["kurang"], 1)} + {bil(r["lebih"], 1)} = <b style="color:#12302A">{bil(r["lompat"], 1)}</b>, '
                  f'dibulatkan {bil(r["lompat"])}. Total kasus hari 1–{MAKS}: '
                  f'{ui.angka(int(r["n_kasus"] - r["n_hari0"]))}.</p>')

# ---------------------------------------------------------------- cara membaca
ui.judul_bagian("Cara membaca untuk pembuat aturan", "gavel")
st.html(
    '<ol class="tp-baca">'
    f'<li>Denda pelayanan berlaku untuk rawat inap dalam {BATAS} hari pertama setelah peserta aktif kembali. '
    f'Kalau peserta menunda, kasus berkurang di hari {hari_txt(KURANG)} dan menumpuk di hari {hari_txt(LEBIH)}. '
    'Lompatan menjumlahkan kedua perubahan itu.</li>'
    '<li>Keadaan darurat tidak bisa ditunda. Kalau IGD ikut melonjak, yang salah alat ukurnya, bukan perilaku '
    'peserta. Karena itu lonjakan rawat inap terjadwal hanya dibaca bila IGD tidak melonjak.</li>'
    f'<li>Perkiraan rawat inap yang ditunda adalah kelebihan di hari {hari_txt(LEBIH)} '
    f'(<b>{bil(rt["lebih"])}</b>), bukan lompatan (<b>{bil(rt["lompat"])}</b>). Lompatan menghitung kasus yang '
    'pindah dua kali: sekali saat hilang, sekali saat muncul.</li>'
    '<li>Penundaan berarti dua hal: denda tidak tertagih, dan perawatan yang sudah direncanakan bergeser lebih '
    'lambat. Hasil ini bahan evaluasi aturan denda. Keputusannya tetap di pembuat kebijakan.</li>'
    '</ol>')

with st.expander("Batas uji ini", icon=":material/rule:"):
    st.html(
        '<ul class="tp-baca">'
        '<li><b>Data sintetis.</b> Penundaan sengaja dibuat di data buatan. Di data asli, hasilnya bisa nol.</li>'
        f'<li><b>Kurva perkiraan bisa terlalu rendah</b> di hari {KURANG[0]}–{LEBIH[1]}. Di IGD, kelebihan hari '
        f'{hari_txt(LEBIH)} saja sudah {bil(ri["lebih"])} kasus (rentang 95%: '
        f'{rentang(ri["lebih_ik_bawah"], ri["lebih_ik_atas"])}), padahal tidak ada yang menunda. Karena itu '
        'ukurannya lompatan, bukan kelebihan saja.</li>'
        '<li><b>Penundaan kecil bisa lolos.</b> Hasil "tidak ada lonjakan" bukan bukti tidak ada penundaan. '
        'Data nasional jauh lebih besar, jadi ujinya lebih peka.</li>'
        '<li><b>IGD di data asli</b> bisa memuat sebagian rawat inap terencana. Pembanding bisa ikut naik '
        'sedikit.</li>'
        f'<li><b>Hari 0</b> (melunasi tunggakan di hari masuk rumah sakit) tidak dihitung dalam kurva: '
        f'{ui.angka(int(rt["n_hari0"]))} rawat inap terjadwal dan {ui.angka(int(ri["n_hari0"]))} IGD. '
        'Itu pola lain, dipantau lewat triase.</li>'
        f'<li><b>Metode.</b> Kurva polinomial derajat {DERAJAT} dan {ui.angka(int(rt["n_bootstrap"]))} sampel bootstrap. '
        'Untuk data asli, pakai metode dengan batasan integrasi (Chetty dkk. 2011; Kleven 2016).</li>'
        '</ul>')
