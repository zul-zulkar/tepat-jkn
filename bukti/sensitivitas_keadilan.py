#!/usr/bin/env python3
"""
sensitivitas_keadilan.py - TEPAT: seberapa kuat temuan panel Keadilan terhadap asumsi data buatan.

Tanpa label: file label tidak pernah dibaca (bukti/skor_verifikasi.muat_tanpa_label memblokirnya). Untuk dua
profil generator (asumsi, sampel2024) dan beberapa seed, skrip menghitung beban per kelompok (kelas, kemiskinan
wilayah, usia, jenis kelamin) dengan definisi yang sama dengan halaman Keadilan (halaman/keadilan.py):
  - seluruh jalur verifikasi, dan
  - "diperiksa" = min(k, isi jalur) peserta jalur dengan skor tertinggi, k = 1% peserta (pra-registrasi 3a;
    tie-break: urut id_peserta, u = default_rng([7, 1]).random(n), skor + (1 + u) x 1e-6).

Dua kontrafaktual, masing-masing mengubah SATU hal dan hanya untuk mengukur (rumus terkunci tidak berubah):
  - usia netral : faktor usia f_usia pada laju layanan di generate_data.py (asumsi tim, tanpa sumber) diganti
                  konstanta rata-ratanya, sehingga total klaim terjaga. Menjawab: apakah kemiringan usia di
                  jalur berasal dari asumsi itu?
  - iuran sama  : penyebut iuran di skor, ln(1 + klaim / iuran), diganti iuran bulanan median untuk semua
                  peserta. Menjawab: apakah kemiringan kelas berasal dari penyebut iuran?

Keluaran (bukti/hasil/): sensitivitas_keadilan_beban.csv, _corong.csv, _iuran.csv, sensitivitas_keadilan.txt.
Data buatan dibuat di bukti/data_sensitivitas/ (di-.gitignore lewat bukti/data_*/) dan dihapus sesudah dipakai
kecuali --simpan.

Pemakaian (dari folder utama repo; 20 run sekitar 3 menit dengan 2 proses):
    python bukti/sensitivitas_keadilan.py                  # 4 varian x 5 seed (2026 1 2 3 4)
    python bukti/sensitivitas_keadilan.py --seed 2026      # cepat: satu seed
    python bukti/sensitivitas_keadilan.py --ringkas        # hanya cetak ringkasan dari CSV yang ada

Batas: hanya data buatan; kontrafaktual hanya mengisolasi asumsi di atas; 5 seed bukan selang kepercayaan.
Seed 2026 profil asumsi identik dengan data/ kanonik, jadi barisnya dicocokkan dengan bukti/hasil/beban_strata.csv.
"""
import argparse
import importlib.util
import math
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))
import cek_sinyal as cs  # noqa: E402

_spec = importlib.util.spec_from_file_location("sv", AKAR / "bukti" / "skor_verifikasi.py")
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)

HASIL = AKAR / "bukti" / "hasil"
KERJA = AKAR / "bukti" / "data_sensitivitas"
JALUR = "verifikasi_pola_reaktivasi"
K_PORSI = 0.01
AMBANG_PRA, AMBANG_PERHATIAN, Z95 = 2.0, 1.25, 1.96
AMBANG_JARANG = 1 / AMBANG_PERHATIAN
URUT = {"kelas": ["kelas_1", "kelas_2", "kelas_3"], "kemiskinan": ["rendah", "sedang", "tinggi"],
        "usia": ["<=35", "36-55", ">55"], "jk": ["L", "P"]}
F_USIA = "f_usia = float(np.clip(0.6 + (usia - 18) / 40, 0.6, 2.2))"
PROFIL = ["asumsi", "sampel2024"]
VARIAN = ["asumsi", "asumsi_netral", "sampel2024", "sampel2024_netral"]
NAMA = {"asumsi": "asumsi (asli)", "asumsi_netral": "asumsi, usia netral", "sampel2024": "sampel2024 (asli)",
        "sampel2024_netral": "sampel2024, usia netral"}


# ---------------------------------------------------------------- pipeline tanpa label
def proses(folder: Path) -> pd.DataFrame:
    """Satu baris per peserta mandiri: fitur triase, rute, skor, atribut, dan kelompok."""
    D, _ = cs.saring_cakupan(sv.muat_tanpa_label(folder))
    assert "label" not in D
    re = cs.tabel_reaktivasi(D["status"], D["bayar"])
    p = cs.triase(cs.fitur_peserta(D, re))
    p["skor"] = sv.skor_verifikasi(p)
    k = D["klaim"]
    besar = k[(k["jenis_layanan"] == "RITL") | (k["biaya_klaim"] >= cs.KLAIM_BESAR)]
    p["n_klaim_besar"] = p["id_peserta"].map(besar.groupby("id_peserta").size()).fillna(0).astype(int)
    att = D["peserta"][["id_peserta", "kelas", "usia_2023", "jenis_kelamin", "kode_wilayah"]]
    dup = [c for c in att.columns if c in p.columns and c != "id_peserta"]
    p = p.drop(columns=dup).merge(att, on="id_peserta", how="left", validate="one_to_one")
    w = pd.read_csv(folder / "wilayah.csv")
    w["kem"] = pd.qcut(w["indeks_kemiskinan"].rank(method="first"), 3,
                       labels=["rendah", "sedang", "tinggi"]).astype(str)
    p["kemiskinan"] = p["kode_wilayah"].map(w.set_index("kode_wilayah")["kem"])
    p["usia"] = pd.cut(p["usia_2023"], [0, 35, 55, 200], labels=["<=35", "36-55", ">55"]).astype(str)
    p["kelas"] = "kelas_" + p["kelas"].astype(str)
    p["jk"] = p["jenis_kelamin"]
    p["jalur"] = p["rute"].eq(JALUR)
    return p


def skor_iuran_sama(p: pd.DataFrame) -> pd.Series:
    """Skor yang sama dengan bukti/skor_verifikasi.py, kecuali penyebut iuran = iuran bulanan median semua peserta."""
    med = float(p["iuran_bulanan"].median())
    s = p["porsi_reakt_terkait"] * (1 - p["rasio_hari_aktif"]) * np.log1p(p["klaim_rp"] / med)
    s = s + p["baru_klaim_lalu_berhenti"].astype(float)
    return s.where(p["rentang_desil"] != "1-5", 0.0).round(4)


def tandai_diperiksa(p: pd.DataFrame, kolom_skor: str = "skor") -> pd.DataFrame:
    """Pra-registrasi 3a: min(k, isi jalur) skor tertinggi di dalam jalur."""
    p = p.sort_values("id_peserta").reset_index(drop=True)
    n, isi = len(p), int(p["jalur"].sum())
    k = math.ceil(round(K_PORSI * n, 9))
    u = np.random.default_rng([7, 1]).random(n)
    sd = np.where(p["jalur"], p[kolom_skor] + (1 + u) * 1e-6, 0.0)
    p["diperiksa"] = False
    p.loc[np.argsort(-sd, kind="mergesort")[:min(k, isi)], "diperiksa"] = True
    return p


def wilson_bawah(x, n):
    pp, z2 = x / n, Z95 * Z95
    return (pp + z2 / (2 * n)) / (1 + z2 / n) - Z95 * math.sqrt(pp * (1 - pp) / n + z2 / (4 * n * n)) / (1 + z2 / n)


def status(x, n, rata):
    r = (x / n) / rata
    if r > AMBANG_PRA:
        return "di_atas"
    if r >= AMBANG_PERHATIAN and wilson_bawah(x, n) / rata > 1:
        return "perhatian"
    return "wajar"


def jarang(x, n, rata):
    return (x / n) / rata <= AMBANG_JARANG and (1 - wilson_bawah(n - x, n)) / rata < 1


def beban(p: pd.DataFrame) -> pd.DataFrame:
    """Sama dengan halaman Keadilan: rasio ke rata-rata (seluruh jalur dan diperiksa), tanda, dan porsi."""
    p = tandai_diperiksa(p)
    n, isi, m = len(p), int(p["jalur"].sum()), int(p["diperiksa"].sum())
    rj, rp = isi / n, m / n
    baris = []
    for dim, urut in URUT.items():
        for kel in urut:
            g = p[p[dim] == kel]
            ng, nj, np_ = len(g), int(g["jalur"].sum()), int(g["diperiksa"].sum())
            baris.append(dict(dimensi=dim, kelompok=kel, n_kelompok=ng, n_jalur=nj, n_periksa=np_,
                              porsi_pop=ng / n, rasio_jalur=(nj / ng) / rj, rasio_periksa=(np_ / ng) / rp,
                              bagian_periksa=np_ / m if m else np.nan,
                              st_jalur=status(nj, ng, rj), st_periksa=status(np_, ng, rp),
                              jarang_jalur=jarang(nj, ng, rj), jarang_periksa=jarang(np_, ng, rp)))
    return pd.DataFrame(baris).assign(n_total=n, isi=isi, m=m)


def kelas_menurut_skor(p: pd.DataFrame) -> pd.DataFrame:
    """Porsi tiap kelas di populasi dan di yang diperiksa: skor asli vs iuran disamakan."""
    pop = p["kelas"].value_counts(normalize=True)
    baris = []
    for nama, skor in [("skor asli", p["skor"]), ("iuran disamakan", skor_iuran_sama(p))]:
        d = tandai_diperiksa(p.assign(skor_uji=skor.values), "skor_uji")
        per = d.loc[d["diperiksa"], "kelas"].value_counts(normalize=True)
        for kel in URUT["kelas"]:
            baris.append(dict(skor=nama, kelas=kel, porsi_pop=pop.get(kel, 0.0), porsi_periksa=per.get(kel, 0.0),
                              m=int(d["diperiksa"].sum())))
    return pd.DataFrame(baris)


TAHAP = [
    ("pernah_reaktivasi", lambda p: p["n_reaktivasi"] >= 1),
    ("punya_klaim_besar", lambda p: p["n_klaim_besar"] >= 1),
    ("reaktivasi_lalu_klaim_besar", lambda p: p["n_reakt_terkait_klaim"] >= 1),
    ("masuk_jalur", lambda p: p["jalur"]),
]


def corong(p: pd.DataFrame) -> pd.DataFrame:
    """Per kelompok usia: tingkat tiap tahap dari perilaku ke rute dan rasionya ke rata-rata semua peserta."""
    baris = []
    for nama, f in TAHAP:
        ya = f(p).astype(bool)
        for kel in URUT["usia"]:
            m = p["usia"] == kel
            baris.append(dict(tahap=nama, usia=kel, n=int(m.sum()), tingkat=ya[m].mean(), rasio=ya[m].mean() / ya.mean()))
    re = p["n_reaktivasi"] >= 1
    rata = p.loc[re, "jalur"].mean()
    for kel in URUT["usia"]:
        m = re & (p["usia"] == kel)
        baris.append(dict(tahap="jalur_bila_pernah_reaktivasi", usia=kel, n=int(m.sum()),
                          tingkat=p.loc[m, "jalur"].mean(), rasio=p.loc[m, "jalur"].mean() / rata))
    return pd.DataFrame(baris)


# ---------------------------------------------------------------- data buatan
def skrip_netral(nama: str, c: float) -> Path:
    """Salinan generate_data.py dengan f_usia = konstanta c (kedua tempat pemakaiannya)."""
    src = (AKAR / "generate_data.py").read_text(encoding="utf-8")
    assert src.count(F_USIA) == 2, "baris f_usia di generate_data.py berubah; sesuaikan F_USIA di skrip ini"
    KERJA.mkdir(parents=True, exist_ok=True)
    out = KERJA / f"gen_{nama}.py"
    out.write_text(src.replace(F_USIA, f"f_usia = {c!r}  # NETRAL USIA (kontrafaktual)"), encoding="utf-8")
    return out


def buat_data(skrip: Path, profil: str, seed: int, n: int, folder: Path) -> None:
    if (folder / "peserta.csv").exists():
        return
    subprocess.run([sys.executable, str(skrip), "--n", str(n), "--seed", str(seed), "--profil", profil,
                    "--out", str(folder)], check=True, capture_output=True, cwd=str(AKAR))


def rata_fusia(folder: Path) -> float:
    p = pd.read_csv(folder / "peserta.csv")
    p = p[p["segmen_kepesertaan"].isin(["PBPU", "BP"])]
    return float(np.clip(0.6 + (p["usia_2023"] - 18) / 40, 0.6, 2.2).mean())


def kerja(varian: str, profil: str, skrip: str, seed: int, n: int, simpan: bool):
    folder = KERJA / f"{varian}_{seed}"
    buat_data(Path(skrip), profil, seed, n, folder)
    p = proses(folder)
    b = beban(p).assign(varian=varian, seed=seed)
    c = corong(p).assign(varian=varian, seed=seed)
    k = kelas_menurut_skor(p).assign(varian=varian, seed=seed)
    if not simpan:
        shutil.rmtree(folder, ignore_errors=True)
    return b, c, k


# ---------------------------------------------------------------- ringkasan
def fmt(s: pd.Series) -> str:
    return f"{s.mean():.2f} [{s.min():.2f}-{s.max():.2f}]"


def ringkas(B: pd.DataFrame, C: pd.DataFrame, K: pd.DataFrame) -> str:
    v_ada = [v for v in VARIAN if v in set(B["varian"])]
    o = [f"run per varian: {B.groupby('varian').seed.nunique().to_dict()}",
         "rata-rata [min-maks] antar seed; 1x = sama dengan rata-rata semua peserta", ""]
    o.append("== isi jalur dan jumlah diperiksa (rata-rata) ==")
    o.append(B.groupby("varian")[["isi", "m"]].mean().round(0).reindex(v_ada).to_string())
    for judul, kol in [("A. SELURUH JALUR", "rasio_jalur"), ("B. DIPERIKSA (skor tertinggi, k = 1%)", "rasio_periksa")]:
        o += ["", f"== {judul}: rasio ke rata-rata =="]
        for dim in ["usia", "kelas", "kemiskinan", "jk"]:
            for kel in URUT[dim]:
                baris = {NAMA[v]: fmt(B[(B.varian == v) & (B.dimensi == dim) & (B.kelompok == kel)][kol]) for v in v_ada}
                o.append(f"{kel:9s}" + " | ".join(f"{a}: {b}" for a, b in baris.items()))
    o += ["", "== C. PORSI KELAS DI POPULASI vs DI YANG DIPERIKSA (rata-rata antar seed) =="]
    for v in v_ada:
        for skor in ["skor asli", "iuran disamakan"]:
            g = K[(K.varian == v) & (K.skor == skor)].groupby("kelas")[["porsi_pop", "porsi_periksa"]].mean()
            o.append(f"{NAMA[v]:24s} {skor:16s} " + "  ".join(
                f"{k[-1]}: {g.loc[k, 'porsi_pop']:.1%} -> {g.loc[k, 'porsi_periksa']:.1%}" for k in URUT["kelas"]))
    o += ["", "== D. FREKUENSI TANDA (jumlah seed) =="]
    for v in v_ada:
        g = B[B.varian == v]
        for tampil, col, jr in [("jalur", "st_jalur", "jarang_jalur"), ("diperiksa", "st_periksa", "jarang_periksa")]:
            x = []
            for (dim, kel), h in g.groupby(["dimensi", "kelompok"]):
                a, b, c = int((h[col] == "perhatian").sum()), int((h[col] == "di_atas").sum()), int(h[jr].sum())
                if a or b or c:
                    x.append(f"{dim}/{kel}: {a} perhatian, {b} >2x, {c} jarang")
            o.append(f"{NAMA[v]:24s} [{tampil:9s}] " + ("; ".join(x) if x else "tidak ada"))
    o += ["", "== E. CORONG USIA (rasio ke rata-rata semua peserta) =="]
    for kel in [">55", "<=35"]:
        o.append(f"-- usia {kel}")
        for t in [t for t, _ in TAHAP] + ["jalur_bila_pernah_reaktivasi"]:
            baris = {NAMA[v]: fmt(C[(C.varian == v) & (C.tahap == t) & (C.usia == kel)].rasio) for v in v_ada}
            o.append(f"  {t:30s}" + " | ".join(f"{a}: {b}" for a, b in baris.items()))
    return "\n".join(o)


def cek_kanonik(B: pd.DataFrame) -> str:
    """Seed 2026 profil asumsi = data/ kanonik: n dan n_jalur per kelompok harus sama dengan beban_strata.csv."""
    f = HASIL / "beban_strata.csv"
    g = B[(B.varian == "asumsi") & (B.seed == 2026)]
    if not f.exists() or g.empty:
        return "cek kanonik dilewati (asumsi seed 2026 atau beban_strata.csv tidak ada)"
    c = pd.read_csv(f).rename(columns={"strata": "dimensi"})
    m = g.merge(c, on=["dimensi", "kelompok"], how="inner")
    ok = int(((m["n_kelompok"] == m["n_peserta"]) & (m["n_jalur_x"] == m["n_jalur_y"])).sum())
    return f"cek kanonik: {ok} dari {len(c)} baris cocok dengan bukti/hasil/beban_strata.csv"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, nargs="+", default=[2026, 1, 2, 3, 4])
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--proses", type=int, default=2, help="jumlah proses paralel")
    ap.add_argument("--simpan", action="store_true", help="jangan hapus data buatan sesudah dipakai")
    ap.add_argument("--ringkas", action="store_true", help="hanya cetak ringkasan dari CSV yang sudah ada")
    a = ap.parse_args()
    nb, nc, nk = (HASIL / f"sensitivitas_keadilan_{x}.csv" for x in ("beban", "corong", "iuran"))
    if not a.ringkas:
        t0 = time.time()
        asli = AKAR / "generate_data.py"
        c = {}
        for pr in PROFIL:   # konstanta f_usia = rata-rata faktor itu pada seed pertama profil yang sama
            folder = KERJA / f"{pr}_{a.seed[0]}"
            buat_data(asli, pr, a.seed[0], a.n, folder)
            c[pr] = round(rata_fusia(folder), 4)
        print(f"rata-rata f_usia: {c}", flush=True)
        skrip = {"asumsi": asli, "sampel2024": asli,
                 "asumsi_netral": skrip_netral("asumsi_netral", c["asumsi"]),
                 "sampel2024_netral": skrip_netral("sampel2024_netral", c["sampel2024"])}
        profil = {"asumsi": "asumsi", "asumsi_netral": "asumsi", "sampel2024": "sampel2024",
                  "sampel2024_netral": "sampel2024"}
        jobs = [(v, profil[v], str(skrip[v]), s, a.n, a.simpan) for s in a.seed for v in VARIAN]
        hasil = []
        with ProcessPoolExecutor(max_workers=a.proses) as ex:
            futs = [ex.submit(kerja, *j) for j in jobs]
            for j, f in zip(jobs, futs):
                hasil.append(f.result())
                print(f"selesai {j[0]:18s} seed {j[3]:<5d} ({time.time() - t0:.0f} dtk)", flush=True)
        HASIL.mkdir(parents=True, exist_ok=True)
        pd.concat([h[0] for h in hasil], ignore_index=True).to_csv(nb, index=False)
        pd.concat([h[1] for h in hasil], ignore_index=True).to_csv(nc, index=False)
        pd.concat([h[2] for h in hasil], ignore_index=True).to_csv(nk, index=False)
    B, C, K = pd.read_csv(nb), pd.read_csv(nc), pd.read_csv(nk)
    teks = ringkas(B, C, K) + "\n\n" + cek_kanonik(B)
    print("\n" + teks)
    if not a.ringkas:
        (HASIL / "sensitivitas_keadilan.txt").write_text(teks + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
