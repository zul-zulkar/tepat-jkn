"""Halaman Keadilan dan bukti: seberapa sering tiap kelompok peserta masuk jalur verifikasi.

Menjawab permintaan BPJS: apakah sistem berat sebelah. Tanpa label (label hanya boleh di halaman Evaluasi),
jadi yang dihitung SEMUA peserta yang masuk jalur, bukan hanya yang jujur.

Dua ukuran, keduanya dibanding rata-rata semua peserta (1x = sama dengan rata-rata):
- Seluruh jalur verifikasi: porsi kelompok yang masuk rute verifikasi_pola_reaktivasi. Sumber:
  bukti/hasil/beban_strata.csv (bukti/nilai_jalur.py). Dihitung ulang di sini dari skor_verifikasi.csv +
  atribut peserta, lalu dicocokkan baris demi baris; bila ada yang beda, halaman memberi peringatan.
- Yang diperiksa: min(k, isi jalur) peserta dengan skor tertinggi, k = 1% peserta (pra-registrasi bagian 3a).
  Aturan pemecah seri dan seed sama dengan nilai_jalur.skor_daftar.

Ambang:
- 2x rata-rata: dikunci di pra-registrasi (uji T4: "tidak ada kelompok > 2x rata-rata"). Di sana ambang ini
  untuk peserta jujur; di halaman ini dipakai pada semua peserta di jalur karena label tidak dibaca.
- Perlu perhatian: >= 1,25x dan batas bawah selang 95% (Wilson) di atas 1x. DITAMBAHKAN sesudah hasil
  dilihat, bukan pra-registrasi, dan tidak dikoreksi untuk pengujian berganda.
- Jarang diperiksa: kebalikannya, <= 0,8x dan batas atas selang 95% di bawah 1x. Juga tambahan sesudah hasil
  dilihat dan tidak dikoreksi.

Rasio ke rata-rata tidak bisa melebihi 1 / porsi kelompok (kelompok > separuh peserta tidak mungkin melewati
2x). Karena itu tiap baris juga menampilkan porsi: dari semua peserta, dari isi jalur, dan dari yang diperiksa.
Tabel lengkap memuat rasio terhadap peserta di luar kelompok, yang tidak punya batas itu (informasi, tanpa tanda).
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import tepat_ui as ui
from ikon import ikon

W = ui.WARNA
HASIL = Path(__file__).resolve().parent.parent / "bukti" / "hasil"
JALUR = "verifikasi_pola_reaktivasi"
K_PORSI = 0.01          # kapasitas periksa: 1% peserta (pra-registrasi bagian 3a)
AMBANG_PRA = 2.0        # pra-registrasi T4
AMBANG_PERHATIAN = 1.25  # ditambahkan sesudah melihat hasil
AMBANG_JARANG = 1 / AMBANG_PERHATIAN  # 0,8x; ditambahkan sesudah melihat hasil
Z95 = 1.96

# (kunci di beban_strata.csv, judul, sumber, ikon, label kelompok menurut urutan tampil)
DIMENSI = [
    ("kelas", "Kelas", "Kelas rawat peserta", "layers",
     {"kelas_1": "Kelas 1", "kelas_2": "Kelas 2", "kelas_3": "Kelas 3"}),
    ("kemiskinan", "Wilayah", "Tingkat kemiskinan wilayah, tiga kelompok", "map-pin",
     {"rendah": "Kemiskinan wilayah rendah", "sedang": "Kemiskinan wilayah sedang",
      "tinggi": "Kemiskinan wilayah tinggi"}),
    ("usia", "Usia", "Usia peserta", "calendar",
     {"<=35": "≤ 35 tahun", "36-55": "36–55 tahun", ">55": "> 55 tahun"}),
    ("jk", "Jenis kelamin", "Jenis kelamin peserta", "users", {"L": "Laki-laki", "P": "Perempuan"}),
]
LABEL = {kunci: lab for kunci, _, _, _, lab in DIMENSI}

STATUS = {
    "wajar": dict(nama="Wajar", warna="#17704D", lembut="#E1EEE6", ikon="circle-check-big"),
    "perhatian": dict(nama="Perlu perhatian", warna="#9A5F0E", lembut="#F5E6C8", ikon="trending-up"),
    "di_atas": dict(nama="Di atas ambang 2×", warna="#9A3F12", lembut="#F6E4D6", ikon="circle-x"),
    "jarang": dict(nama="Jarang diperiksa", warna="#1F5F8B", lembut="#DDE9F3", ikon="trending-down"),
}
URUT = ["wajar", "perhatian", "di_atas"]


def terburuk(status: list[str]) -> str:
    return max(status, key=URUT.index)


def x2(v: float) -> str:
    return f"{ui.angka(v, 2)}×" if np.isfinite(v) else "—"


# ---------------------------------------------------------------- hitungan
def wilson_bawah(x: int, n: int) -> float:
    """Batas bawah selang 95% Wilson untuk porsi x/n."""
    p, z2 = x / n, Z95 * Z95
    pusat = (p + z2 / (2 * n)) / (1 + z2 / n)
    sisi = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return pusat - sisi


def wilson_atas(x: int, n: int) -> float:
    """Batas atas selang 95% Wilson untuk porsi x/n."""
    return 1 - wilson_bawah(n - x, n)


def status(x: int, n: int, rata: float) -> str:
    r = (x / n) / rata
    if r > AMBANG_PRA:
        return "di_atas"
    if r >= AMBANG_PERHATIAN and wilson_bawah(x, n) / rata > 1:
        return "perhatian"
    return "wajar"


def terlalu_jarang(x: int, n: int, rata: float) -> bool:
    return (x / n) / rata <= AMBANG_JARANG and wilson_atas(x, n) / rata < 1


@st.cache_data(show_spinner="Menghitung beban per kelompok…")
def hitung() -> tuple[pd.DataFrame, dict]:
    csv = pd.read_csv(HASIL / "beban_strata.csv").rename(columns={"strata": "dimensi"})
    sk = pd.read_csv(HASIL / "skor_verifikasi.csv")
    T = ui.tabel_peserta()[["id_peserta", "kelas", "usia_2023", "jenis_kelamin", "kode_wilayah",
                            "indeks_kemiskinan"]]
    d = sk.merge(T, on="id_peserta", how="left", validate="one_to_one")
    assert d["kode_wilayah"].notna().all(), "ada peserta di skor_verifikasi.csv tanpa atribut"

    # kelompok: definisi sama dengan bukti/nilai_jalur.py (strata, kemiskinan_tiga)
    w = d.drop_duplicates("kode_wilayah").sort_values("kode_wilayah")
    tiga = pd.qcut(w["indeks_kemiskinan"].rank(method="first"), 3,
                   labels=["rendah", "sedang", "tinggi"]).astype(str)
    d["kemiskinan"] = d["kode_wilayah"].map(dict(zip(w["kode_wilayah"], tiga)))
    d["usia"] = pd.cut(d["usia_2023"], [0, 35, 55, 200], labels=["<=35", "36-55", ">55"]).astype(str)
    d["kelas"] = "kelas_" + d["kelas"].astype(str)
    d["jk"] = d["jenis_kelamin"]
    d["jalur"] = d["rute"].eq(JALUR)

    # yang diperiksa: pra-registrasi 3a (urut id_peserta, u dari default_rng([7, 1]), skor + (1 + u) x 1e-6)
    d = d.sort_values("id_peserta").reset_index(drop=True)
    n, isi = len(d), int(d["jalur"].sum())
    k = math.ceil(round(K_PORSI * n, 9))
    m = min(k, isi)
    u = np.random.default_rng([7, 1]).random(n)
    skor_daftar = np.where(d["jalur"], d["skor"] + (1 + u) * 1e-6, 0.0)
    d["diperiksa"] = False
    d.loc[np.argsort(-skor_daftar, kind="mergesort")[:m], "diperiksa"] = True
    assert d.loc[d["diperiksa"], "jalur"].all()

    ulang = pd.concat([
        d.groupby(kol).agg(n=("jalur", "size"), n_jalur=("jalur", "sum"), n_periksa=("diperiksa", "sum"))
         .reset_index().rename(columns={kol: "kelompok"}).assign(dimensi=dim)
        for dim, kol in [("kelas", "kelas"), ("kemiskinan", "kemiskinan"), ("usia", "usia"), ("jk", "jk")]
    ], ignore_index=True)

    # cek silang hitungan ulang terhadap beban_strata.csv; angka seluruh jalur yang ditampilkan dari CSV
    gab = ulang.merge(csv, on=["dimensi", "kelompok"], how="outer", suffixes=("_ulang", ""), indicator=True)
    cocok = int(((gab["_merge"] == "both") & (gab["n"] == gab["n_peserta"])
                 & (gab["n_jalur_ulang"] == gab["n_jalur"])).sum())
    gab = gab[gab["_merge"] == "both"]

    rata_j, rata_p = isi / n, m / n
    t = pd.DataFrame(dict(dimensi=gab["dimensi"].values, kelompok=gab["kelompok"].values,
                          n=gab["n_peserta"].astype(int).values, n_jalur=gab["n_jalur"].astype(int).values,
                          n_periksa=gab["n_periksa"].astype(int).values))
    t["porsi_jalur"], t["porsi_periksa"] = t["n_jalur"] / t["n"], t["n_periksa"] / t["n"]
    t["rasio_jalur"], t["rasio_periksa"] = t["porsi_jalur"] / rata_j, t["porsi_periksa"] / rata_p
    t["status_jalur"] = [status(x, nn, rata_j) for x, nn in zip(t["n_jalur"], t["n"])]
    t["status_periksa"] = [status(x, nn, rata_p) for x, nn in zip(t["n_periksa"], t["n"])]
    t["jarang_jalur"] = [terlalu_jarang(x, nn, rata_j) for x, nn in zip(t["n_jalur"], t["n"])]
    t["jarang_periksa"] = [terlalu_jarang(x, nn, rata_p) for x, nn in zip(t["n_periksa"], t["n"])]
    # porsi: dari semua peserta, dari isi jalur, dari yang diperiksa. Rasio ke rata-rata = bagian / porsi_pop,
    # jadi tidak bisa melebihi 1 / porsi_pop (batas_atas).
    t["porsi_pop"], t["bagian_jalur"], t["bagian_periksa"] = t["n"] / n, t["n_jalur"] / isi, t["n_periksa"] / m
    t["batas_atas"] = n / t["n"]
    sisa = (n - t["n"]).where(n - t["n"] > 0)
    with np.errstate(divide="ignore", invalid="ignore"):   # rasio terhadap peserta di luar kelompok (informasi)
        t["luar_jalur"] = t["porsi_jalur"] / ((isi - t["n_jalur"]) / sisa)
        t["luar_periksa"] = t["porsi_periksa"] / ((m - t["n_periksa"]) / sisa)
    per_wil = d[d["jalur"]].groupby("kode_wilayah").size()
    info = dict(n=n, isi=isi, k=k, m=m, baris_csv=len(csv), cocok=cocok, rata_j=rata_j, rata_p=rata_p,
                n_wilayah=int(d["kode_wilayah"].nunique()), wil_min=int(per_wil.min()), wil_maks=int(per_wil.max()))
    return t, info


tabel, INFO = hitung()
N, ISI, M = INFO["n"], INFO["isi"], INFO["m"]
XMAKS = max(2.2, float(tabel[["rasio_jalur", "rasio_periksa"]].max().max()) * 1.08)  # skala sama di semua panel
pos = lambda v: f"{min(v / XMAKS, 1) * 100:.2f}%"  # noqa: E731

ui.kepala("Panel keadilan dan bukti",
          "Kelompok peserta mana yang paling sering masuk jalur verifikasi, dibanding rata-rata semua peserta. "
          "Dihitung tanpa label, jadi mencakup semua peserta di jalur, bukan hanya yang jujur. Angkanya bisa "
          "dihitung ulang dari skor_verifikasi.csv dan beban_strata.csv.")

# ---------------------------------------------------------------- kesimpulan
lain = tabel[(tabel["status_jalur"] != "wajar") | (tabel["status_periksa"] != "wajar")]
di_atas = lain[(lain["status_jalur"] == "di_atas") | (lain["status_periksa"] == "di_atas")]
perhatian = lain.drop(di_atas.index)
rendah = tabel[tabel["jarang_jalur"] | tabel["jarang_periksa"]]
mustahil = tabel[tabel["batas_atas"] <= AMBANG_PRA]   # lebih dari separuh peserta: 2× tidak mungkin tercapai


def nama_penuh(dimensi: str, kelompok: str) -> str:
    """Nama kelompok yang bisa berdiri sendiri di kalimat ('> 55 tahun' saja tidak jelas itu usia)."""
    return ("Usia " if dimensi == "usia" else "") + LABEL[dimensi][kelompok]


def uraian(df: pd.DataFrame) -> str:
    return "; ".join(f"{nama_penuh(r.dimensi, r.kelompok)} ({x2(r.rasio_jalur)} di seluruh jalur, "
                     f"{x2(r.rasio_periksa)} di yang diperiksa)" for r in df.itertuples())


if len(di_atas):
    kunci_v, vonis = "di_atas", f"{len(di_atas)} kelompok di atas ambang 2×"
    rinci = (uraian(di_atas) + ". Lebih sering masuk jalur belum berarti diperlakukan tidak adil, tetapi "
             "harus bisa dijelaskan sebelum aturan dipakai.")
elif len(perhatian):
    kunci_v = "perhatian"
    vonis = f"Tidak ada kelompok di atas ambang 2×, tetapi {len(perhatian)} kelompok perlu perhatian"
    rinci = (uraian(perhatian) + ". Selisihnya bukan kebetulan (selang 95% di atas rata-rata), tetapi panel ini "
             "belum menjelaskan penyebabnya.")
elif len(rendah):
    kunci_v = "jarang"
    vonis = f"Tidak ada kelompok yang terlalu sering diperiksa, tetapi {len(rendah)} kelompok jarang diperiksa"
    rinci = (uraian(rendah) + ". Selisihnya bukan kebetulan (selang 95% di bawah rata-rata), tetapi panel ini "
             "belum menjelaskan penyebabnya.")
else:
    kunci_v, vonis = "wajar", "Tidak ada kelompok yang menonjol"
    rinci = ("Semua kelompok di bawah ambang 2× dan tidak ada yang di atas 1,25× dengan selang 95% di atas "
             "rata-rata. Itu bukan bukti tidak ada ketimpangan di dimensi lain.")
S_V = STATUS[kunci_v]

tambahan = []   # catatan di bawah vonis; tanda 'jarang' dan batas ambang tidak boleh terlewat
if len(rendah) and kunci_v != "jarang":
    tambahan.append("Jarang diperiksa (≤ 0,8×, selang 95% di bawah rata-rata; tanda tambahan): " + uraian(rendah) + ".")
if len(mustahil):
    tambahan.append(
        "Ambang 2× tidak mungkin tercapai oleh kelompok yang lebih dari separuh peserta ("
        + "; ".join(f"{nama_penuh(r.dimensi, r.kelompok)} {ui.persen(r.porsi_pop)} dari peserta → "
                    f"{ui.persen(r.bagian_periksa)} dari yang diperiksa" for r in mustahil.itertuples())
        + "). Untuk mereka, bandingkan kedua porsi itu, bukan rasionya.")
html_tambahan = "".join(f'<div class="lain" style="margin-top:.35rem">{ui.e(t)}</div>' for t in tambahan)

st.html(f'<div class="tp-tindakan" style="--c:{S_V["warna"]};--l:{S_V["lembut"]}">'
        f'<div class="tp-bulat">{ikon("scale", 20, S_V["warna"])}</div>'
        f'<div style="flex:1 1 320px"><div class="lbl">Hasil pemeriksaan keadilan</div>'
        f'<div class="isi">{ui.e(vonis)}</div>'
        f'<div class="lain" style="margin-top:.2rem">{ui.e(rinci)}</div>{html_tambahan}'
        f'<div class="lain" style="margin-top:.35rem;display:flex;gap:.35rem;align-items:flex-start">'
        f'{ikon("flask-conical", 14, W["tinta2"])}<span>Data sintetis: pola ini berasal dari data buatan. Panel '
        f'ini menunjukkan alat ukurnya bekerja, bukan bahwa peserta BPJS asli diperlakukan seperti ini.</span>'
        f'</div></div></div>')

# ---------------------------------------------------------------- angka utama
n_di_atas = int(((tabel["status_jalur"] == "di_atas") | (tabel["status_periksa"] == "di_atas")).sum())
st.html(ui.kartu([
    dict(ikon="users", c=W["utama"], l=W["utama_lembut"], n=ui.angka(ISI),
         label=f"Peserta di jalur verifikasi ({ui.persen(ISI / N)} dari {ui.angka(N)})"),
    dict(ikon="search-check", c="#9A3F12", l="#F6E4D6", n=ui.angka(M),
         label=f"Diperiksa sesuai kapasitas ({ui.persen(K_PORSI, 0)} peserta)"),
    dict(ikon="circle-x", c=STATUS["di_atas"]["warna"], l=STATUS["di_atas"]["lembut"],
         n=f"{n_di_atas} dari {len(tabel)}", label="Kelompok di atas ambang 2×", mati=n_di_atas == 0),
    dict(ikon="trending-up", c=STATUS["perhatian"]["warna"], l=STATUS["perhatian"]["lembut"],
         n=f"{len(perhatian)} dari {len(tabel)}", label="Kelompok perlu perhatian (≥ 1,25×)",
         mati=len(perhatian) == 0),
    dict(ikon="trending-down", c=STATUS["jarang"]["warna"], l=STATUS["jarang"]["lembut"],
         n=f"{len(rendah)} dari {len(tabel)}", label="Kelompok jarang diperiksa (≤ 0,8×)",
         mati=len(rendah) == 0),
]))

# ---------------------------------------------------------------- panel per dimensi
ui.judul_bagian("Beban per kelompok", "layers",
                f"Rasio 1× = sama dengan rata-rata semua peserta. Seluruh jalur: rata-rata "
                f"{ui.persen(INFO['rata_j'])} ({ui.angka(ISI)} dari {ui.angka(N)}). Diperiksa: rata-rata "
                f"{ui.persen(INFO['rata_p'])} ({ui.angka(M)} dari {ui.angka(N)}), bila petugas memeriksa menurut "
                "urutan skor (pra-registrasi bagian 3a).")
kotak = lambda c: f'<i style="width:16px;height:9px;border-radius:2px;background:{c}"></i>'  # noqa: E731
st.html('<div class="tp-legenda-lini" style="margin-bottom:.7rem">'
        f'<span>{kotak(STATUS["wajar"]["warna"])}Seluruh jalur verifikasi</span>'
        f'<span><i style="width:10px;height:10px;transform:rotate(45deg);border:2px solid {W["tinta"]};'
        f'box-sizing:border-box;background:{STATUS["wajar"]["warna"]}"></i>Yang diperiksa ({ui.angka(M)} skor tertinggi)</span>'
        f'<span><i style="width:0;height:12px;border-left:1.5px solid #8F9993"></i>Rata-rata (1×)</span>'
        f'<span><i style="width:0;height:12px;border-left:1.5px dashed {STATUS["di_atas"]["warna"]}"></i>'
        f'Ambang 2× (pra-registrasi)</span>'
        f'<span style="color:{STATUS["perhatian"]["warna"]}">Oranye = perlu perhatian</span>'
        f'<span style="color:{STATUS["jarang"]["warna"]}">Biru = jarang diperiksa</span></div>')


def baris(r) -> str:
    sj, sp = STATUS[r.status_jalur], STATUS[r.status_periksa]
    nama = LABEL[r.dimensi][r.kelompok]
    jarang = r.jarang_jalur or r.jarang_periksa
    batas = r.batas_atas <= AMBANG_PRA
    bagi = (f"Porsi: <b>{ui.persen(r.porsi_pop)}</b> dari semua peserta → <b>{ui.persen(r.bagian_jalur)}</b> dari isi "
            f"jalur → <b>{ui.persen(r.bagian_periksa)}</b> dari yang diperiksa"
            + (f'. <em>Rasio tertinggi yang mungkin {x2(r.batas_atas)}: ambang 2× tidak bisa tercapai.</em>'
               if batas else ""))
    ringkas = (f"{nama}: seluruh jalur {x2(r.rasio_jalur)} rata-rata ({ui.angka(r.n_jalur)} dari "
               f"{ui.angka(r.n)} peserta, {ui.persen(r.porsi_jalur)}); diperiksa {x2(r.rasio_periksa)} "
               f"({ui.angka(r.n_periksa)} dari {ui.angka(r.n)}, {ui.persen(r.porsi_periksa, 2)}). "
               f"Porsi dari semua peserta {ui.persen(r.porsi_pop)}, dari isi jalur {ui.persen(r.bagian_jalur)}, "
               f"dari yang diperiksa {ui.persen(r.bagian_periksa)}"
               + (f"; rasio tertinggi yang mungkin {x2(r.batas_atas)}" if batas else ""))
    s_all = terburuk([r.status_jalur, r.status_periksa])
    penanda = ("" if s_all == "wajar" else
               ui.chip(STATUS[s_all]["nama"], STATUS[s_all]["ikon"], STATUS[s_all]["warna"], STATUS[s_all]["lembut"]))
    if jarang:
        penanda += ui.chip(STATUS["jarang"]["nama"], STATUS["jarang"]["ikon"], STATUS["jarang"]["warna"],
                           STATUS["jarang"]["lembut"])
    wj = sj["warna"] if r.status_jalur != "wajar" else (STATUS["jarang"]["warna"] if r.jarang_jalur else "inherit")
    wp = sp["warna"] if r.status_periksa != "wajar" else (STATUS["jarang"]["warna"] if r.jarang_periksa else "inherit")
    return (f'<div class="tp-beban-r" role="listitem" aria-label="{ui.e(ringkas)}" title="{ui.e(ringkas)}">'
            f'<div class="nm">{ui.e(nama)}<small>{ui.angka(r.n)} peserta</small>{penanda}</div>'
            f'<div class="tp-trek" style="--wj:{sj["warna"]};--wp:{sp["warna"]}">'
            f'<i class="g" style="left:{pos(1)}"></i><i class="g g2" style="left:{pos(AMBANG_PRA)}"></i>'
            f'<b class="br" style="width:{pos(r.rasio_jalur)}"></b>'
            f'<span class="dm" style="left:{pos(r.rasio_periksa)}"></span></div>'
            f'<div class="ang"><span style="color:{wj}">'
            f'<small>jalur</small> <b>{x2(r.rasio_jalur)}</b></span>'
            f'<span style="color:{wp}">'
            f'<small>diperiksa</small> <b>{x2(r.rasio_periksa)}</b></span></div>'
            f'<div class="bagi">{bagi}</div></div>')


def sumbu() -> str:
    return (f'<div class="tp-beban-ax"><span></span><div class="tp-trek-ax">'
            f'<i style="left:{pos(0)}">0</i><i style="left:{pos(1)}">1×</i>'
            f'<i style="left:{pos(AMBANG_PRA)}">2×</i></div><span></span></div>')


kiri, kanan = st.columns(2, gap="medium")
for i, (kunci, judul, sumber, nama_ikon, label) in enumerate(DIMENSI):
    t = tabel[tabel["dimensi"] == kunci].copy()
    t["urut"] = t["kelompok"].map({k: j for j, k in enumerate(label)})
    t = t.sort_values("urut")
    s_p = STATUS[terburuk(list(t["status_jalur"]) + list(t["status_periksa"]))]
    chip_p = ui.chip(s_p["nama"], s_p["ikon"], s_p["warna"], s_p["lembut"])
    if (t["jarang_jalur"] | t["jarang_periksa"]).any():
        chip_p += ui.chip(STATUS["jarang"]["nama"], STATUS["jarang"]["ikon"], STATUS["jarang"]["warna"],
                          STATUS["jarang"]["lembut"])
    with (kiri if i % 2 == 0 else kanan).container(border=True, key=f"tpgrafik_{kunci}"):
        st.html(f'<div class="tp-grafik-kepala" style="--c:{W["utama"]};--l:{W["utama_lembut"]}">'
                f'<div class="tp-bulat">{ikon(nama_ikon, 20, W["utama"])}</div>'
                f'<div><p class="sumber">{ui.e(sumber)}</p><p class="nama">{ui.e(judul)}</p></div>'
                f'<span class="vonis">{chip_p}</span></div>')
        st.html(f'<div class="tp-beban" role="list">{"".join(baris(r) for r in t.itertuples())}</div>' + sumbu())

# ---------------------------------------------------------------- angka lengkap
with st.expander("Angka lengkap dan cek silang", icon=":material/table:"):
    tampil = tabel.copy()
    tampil["Dimensi"] = tampil["dimensi"].map({k: j for k, j, *_ in DIMENSI})
    tampil["Kelompok"] = [LABEL[a][b] for a, b in zip(tampil["dimensi"], tampil["kelompok"])]
    urut_dim = {k: i for i, (k, *_) in enumerate(DIMENSI)}
    tampil["_u"] = [(urut_dim[a], list(LABEL[a]).index(b)) for a, b in zip(tampil["dimensi"], tampil["kelompok"])]
    tampil = tampil.sort_values("_u")
    jarang_teks = lambda a: np.where(a, STATUS["jarang"]["nama"], "")  # noqa: E731
    unduh = pd.DataFrame({
        "dimensi": tampil["dimensi"], "kelompok": tampil["kelompok"], "n_peserta": tampil["n"],
        "porsi_peserta": tampil["porsi_pop"].round(4), "rasio_tertinggi_mungkin": tampil["batas_atas"].round(2),
        "n_jalur": tampil["n_jalur"], "porsi_jalur": tampil["porsi_jalur"].round(4),
        "bagian_dari_isi_jalur": tampil["bagian_jalur"].round(4),
        "rasio_jalur": tampil["rasio_jalur"].round(2), "status_jalur": tampil["status_jalur"],
        "jarang_jalur": tampil["jarang_jalur"], "rasio_vs_luar_kelompok_jalur": tampil["luar_jalur"].round(2),
        "n_diperiksa": tampil["n_periksa"], "porsi_diperiksa": tampil["porsi_periksa"].round(4),
        "bagian_dari_yang_diperiksa": tampil["bagian_periksa"].round(4),
        "rasio_diperiksa": tampil["rasio_periksa"].round(2), "status_diperiksa": tampil["status_periksa"],
        "jarang_diperiksa": tampil["jarang_periksa"],
        "rasio_vs_luar_kelompok_diperiksa": tampil["luar_periksa"].round(2)})
    st.dataframe(pd.DataFrame({
        "Dimensi": tampil["Dimensi"], "Kelompok": tampil["Kelompok"],
        "Peserta": tampil["n"].map(ui.angka), "Porsi peserta": tampil["porsi_pop"].map(ui.persen),
        "Rasio tertinggi mungkin": tampil["batas_atas"].map(x2),
        "Di jalur": tampil["n_jalur"].map(ui.angka), "Porsi jalur": tampil["porsi_jalur"].map(ui.persen),
        "Bagian dari isi jalur": tampil["bagian_jalur"].map(ui.persen),
        "Rasio jalur": tampil["rasio_jalur"].map(x2),
        "Status jalur": tampil["status_jalur"].map(lambda s: STATUS[s]["nama"]),
        "Jalur: jarang": jarang_teks(tampil["jarang_jalur"]),
        "Jalur vs di luar kelompok": tampil["luar_jalur"].map(x2),
        "Diperiksa": tampil["n_periksa"].map(ui.angka),
        "Porsi diperiksa": tampil["porsi_periksa"].map(lambda v: ui.persen(v, 2)),
        "Bagian dari yang diperiksa": tampil["bagian_periksa"].map(ui.persen),
        "Rasio diperiksa": tampil["rasio_periksa"].map(x2),
        "Status diperiksa": tampil["status_periksa"].map(lambda s: STATUS[s]["nama"]),
        "Diperiksa: jarang": jarang_teks(tampil["jarang_periksa"]),
        "Diperiksa vs di luar kelompok": tampil["luar_periksa"].map(x2)}),
        hide_index=True, width="stretch", height=(len(tampil) + 1) * 33 + 3)  # semua baris terlihat
    st.download_button("Unduh angka (CSV)", unduh.to_csv(index=False).encode("utf-8"),
                       file_name="beban_per_kelompok.csv", mime="text/csv", icon=":material/download:")
    if INFO["cocok"] == INFO["baris_csv"] == len(tabel):
        st.html(f'<p class="tp-catatan-kecil">{ikon("circle-check-big", 14, W["utama"])} Cek silang: dihitung '
                f'ulang dari skor_verifikasi.csv dan atribut peserta, {INFO["cocok"]} dari {INFO["baris_csv"]} '
                'baris cocok dengan beban_strata.csv (jumlah peserta dan jumlah di jalur).</p>')
    else:
        st.warning(f"Cek silang gagal: hanya {INFO['cocok']} dari {INFO['baris_csv']} baris beban_strata.csv "
                   "cocok dengan hitungan ulang. Jangan pakai angka di halaman ini sebelum diperiksa.")

# ---------------------------------------------------------------- cara membaca dan batas
ui.judul_bagian("Cara membaca", "gavel")
st.html(
    '<ol class="tp-baca">'
    f'<li><b>Seluruh jalur</b> adalah {ui.angka(ISI)} peserta yang ditandai aturan triase untuk diperiksa '
    f'petugas. <b>Diperiksa</b> adalah {ui.angka(M)} di antaranya dengan skor tertinggi, bila petugas memeriksa '
    f'menurut urutan skor dengan kapasitas {ui.persen(K_PORSI, 0)} peserta (pra-registrasi bagian 3a).</li>'
    f'<li>Ambang <b>2× rata-rata</b> dikunci di pra-registrasi (uji T4) sebelum hasil dilihat. '
    f'<b>Perlu perhatian</b> (≥ {ui.angka(AMBANG_PERHATIAN, 2)}× dan selang 95% di atas rata-rata) dan '
    f'<b>jarang diperiksa</b> (≤ {ui.angka(AMBANG_JARANG, 2)}× dan selang 95% di bawah rata-rata) '
    'ditambahkan sesudah hasil dilihat, jadi bukan bagian pra-registrasi.</li>'
    '<li><b>Porsi</b> di bawah tiap batang: berapa persen peserta, isi jalur, dan yang diperiksa berasal dari '
    'kelompok itu. Bila porsi diperiksa jauh di atas porsi peserta, kelompok itu terlalu sering diperiksa, '
    'walau rasionya belum melewati 2×. Rasio ke rata-rata tidak bisa melebihi 1 ÷ porsi peserta, jadi ambang 2× '
    'tidak bisa mendeteksi kelompok yang lebih dari separuh peserta; untuk itu baca porsinya.</li>'
    '<li>Lebih sering masuk jalur bukan bukti perlakuan tidak adil, dan tidak ada selisih bukan bukti '
    'sebaliknya. Panel ini menunjukkan di mana selisih ada. Sebabnya perlu diselidiki terpisah.</li>'
    '<li>Peserta yang masuk jalur diperiksa petugas lebih dulu sebelum ada tindakan. Jalur ini bukan tuduhan '
    'dan tidak mencabut jaminan.</li>'
    '</ol>')

with st.expander("Batas panel ini", icon=":material/rule:"):
    st.html(
        '<ul class="tp-baca">'
        '<li><b>Data sintetis.</b> Pola di sini berasal dari data buatan. Di data asli, hasilnya bisa lain.</li>'
        '<li><b>Semua peserta di jalur, bukan hanya yang jujur.</b> Label tidak dibaca di halaman ini. '
        'Uji berlabel yang memisahkan peserta jujur (T4) dilaporkan terpisah dan hanya dinilai bila ada cukup '
        'peserta jujur di jalur (syarat pra-registrasi: minimal 30).</li>'
        f'<li><b>Yang diperiksa hanya {ui.angka(M)} orang.</b> Per kelompok hanya '
        f'{ui.angka(int(tabel["n_periksa"].min()))}–{ui.angka(int(tabel["n_periksa"].max()))} orang, jadi '
        'rasionya lebih goyah daripada rasio seluruh jalur. Tanda perhatian memakai selang 95% tetapi tidak '
        f'dikoreksi untuk {len(tabel) * 2} perbandingan sekaligus.</li>'
        '<li><b>Satu dimensi sekali jalan.</b> Kelompok antardimensi saling tumpang tindih (misalnya usia dan '
        'kelas), jadi selisih di satu dimensi bisa berasal dari dimensi lain.</li>'
        f'<li><b>Wilayah</b> berarti tiga kelompok tingkat kemiskinan wilayah (sepertiga bawah, tengah, atas '
        f'dari {INFO["n_wilayah"]} wilayah), seperti di pra-registrasi. Per kode wilayah tidak ditampilkan: '
        f'hanya {INFO["wil_min"]}–{INFO["wil_maks"]} peserta di jalur per wilayah, terlalu sedikit untuk '
        'dibandingkan.</li>'
        '<li><b>Pembandingnya rata-rata semua peserta</b>, bukan kelompok lain. Dua kelompok bisa sama-sama '
        'dekat rata-rata namun selisih antar keduanya tetap besar. Tabel lengkap memuat rasio terhadap peserta di '
        'luar kelompok, yang tidak punya batas 1 ÷ porsi; angka itu informasi tanpa ambang.</li>'
        '<li><b>Skor ikut menentukan siapa yang diperiksa.</b> Rumus skor (pra-registrasi bagian 3) membagi klaim '
        'dengan iuran, sehingga peserta berkelas murah mendapat skor lebih tinggi untuk klaim yang sama dan kelas '
        'murah cenderung lebih banyak di antara yang diperiksa. Besarnya pengaruh ini diukur terpisah di '
        'bukti/hasil/sensitivitas_keadilan.txt (bagian C), bersama uji usia netral dan rentang antar seed '
        '(skrip: bukti/sensitivitas_keadilan.py).</li>'
        '</ul>')
