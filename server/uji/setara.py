"""Bandingkan jawaban API Go dengan perhitungan aplikasi Streamlit (tepat_ui.py dan halaman/*.py).

Jalankan server Go dulu (go run ./cmd/tepat -buka=false), lalu dari folder repo:
    python server/uji/setara.py --url http://127.0.0.1:8080
Keluar dengan kode 1 bila ada yang beda. Hanya membaca; tidak mengubah apa pun.
"""
from __future__ import annotations

import argparse
import ast
import http.cookiejar
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR))

import logging  # noqa: E402

logging.getLogger("streamlit").setLevel(logging.ERROR)
import akun as akun_py  # noqa: E402
import pesan_template  # noqa: E402
import tepat_ui as ui  # noqa: E402


class Klien:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def __call__(self, metode: str, jalur: str, badan: dict | None = None):
        req = urllib.request.Request(self.url + jalur, method=metode,
                                     data=None if badan is None else json.dumps(badan).encode(),
                                     headers={"content-type": "application/json"})
        with self.op.open(req) as r:
            return json.loads(r.read())


GAGAL: list[str] = []


def cek(nama: str, kondisi: bool, rinci: str = "") -> None:
    if not kondisi:
        GAGAL.append(f"{nama} {rinci}")
        print("BEDA ", nama, rinci)


def harapan_daftar(T: pd.DataFrame, kunci: str, pilihan: list[str], k: int) -> dict:
    a = akun_py.AKUN[kunci]
    cabang = a["peran"] == "cabang"
    if cabang:
        T = T[T["kode_wilayah"].isin(a["wilayah"])]
    wil = ([w for w in pilihan if w in set(a["wilayah"])] or list(a["wilayah"])) if cabang else list(pilihan)
    T_w = T[T["kode_wilayah"].isin(wil)] if wil else T
    ew_list, n_dinilai = ui.daftar_ew(T, wil, k)
    ew_ids = set(ew_list["id_peserta"])
    T_w = T_w.assign(utama=ui.tindakan_utama(T_w["rute"], T_w["id_peserta"].isin(ew_ids)))
    tri = T_w[T_w["utama"].isin(ui.RUTE_AKSI)].sort_values(["urut_rute", "tunggakan_rp", "id_peserta"],
                                                          ascending=[True, False, True])
    ew_utama = ew_list.assign(urut=np.arange(1, len(ew_list) + 1))
    ew_utama = ew_utama[ew_utama["id_peserta"].isin(T_w.loc[T_w["utama"] == ui.PERINGATAN_DINI, "id_peserta"])]
    return dict(total=len(T_w), jumlah=T_w["utama"].value_counts().to_dict(), n_dinilai=n_dinilai,
                n_ew=len(ew_list), triase=list(tri["id_peserta"]), juga=list(tri["id_peserta"].isin(ew_ids)),
                ew=list(zip(ew_utama["urut"], ew_utama["id_peserta"])),
                pindah=int(((T_w["rute"] == "pengingat_autodebet_REHAB") & (T_w["utama"] == ui.PERINGATAN_DINI)).sum()))


def cek_daftar(api: Klien, T: pd.DataFrame) -> None:
    skenario = [("pusat", [], 5), ("pusat", [], 1), ("pusat", [], 13), ("pusat", [], 20),
                ("pusat", ["W06", "W29"], 5), ("pusat", ["W40"], 17), ("cabang_a", [], 5),
                ("cabang_a", ["W06", "W09"], 5), ("cabang_c", [], 5), ("cabang_d", ["W37"], 5)]
    for kunci, pilihan, k in skenario:
        api("POST", "/api/masuk", {"akun": "pusat"})
        api("PUT", "/api/kapasitas", {"k": k})
        api("POST", "/api/masuk", {"akun": kunci})
        g = api("GET", "/api/daftar?wilayah=" + ",".join(pilihan))
        h = harapan_daftar(T, kunci, pilihan, k)
        nama = f"daftar[{kunci} {pilihan} k={k}]"
        cek(nama + " total", g["total"] == h["total"], f'{g["total"]} vs {h["total"]}')
        cek(nama + " jumlah_utama", g["jumlah_utama"] == h["jumlah"], f'{g["jumlah_utama"]} vs {h["jumlah"]}')
        cek(nama + " n_dinilai", g["n_dinilai"] == h["n_dinilai"])
        cek(nama + " n_ew_daftar", g["n_ew_daftar"] == h["n_ew"])
        cek(nama + " pindah", g["pindah"] == h["pindah"])
        cek(nama + " urutan triase", [x["id"] for x in g["triase"]] == h["triase"])
        cek(nama + " juga_ew", [x["juga_ew"] for x in g["triase"]] == h["juga"])
        cek(nama + " daftar ew", [(x["urut"], x["id"]) for x in g["ew"]] == [(int(a), b) for a, b in h["ew"]])
        print(f"ok   {nama}: triase {len(g['triase'])}, berisiko {len(g['ew'])}")


def cek_profil(api: Klien, T: pd.DataFrame) -> None:
    api("POST", "/api/masuk", {"akun": "pusat"})
    api("PUT", "/api/kapasitas", {"k": 5})
    ew_list, _ = ui.daftar_ew(T, [], 5)
    ew_ids = set(ew_list["id_peserta"])
    idx = T.set_index("id_peserta")
    contoh = ["P-002329", "P-005882", "P-004192"]
    rng = np.random.default_rng(11)
    for rute in ui.RUTE:
        ids = T.loc[T["rute"] == rute, "id_peserta"].to_numpy()
        contoh += list(rng.choice(ids, size=min(25, len(ids)), replace=False))
    contoh += list(ew_list["id_peserta"].head(25))
    for pid in contoh:
        g = api("GET", f"/api/peserta/{pid}")
        p = idx.loc[pid].to_dict() | {"id_peserta": pid}
        p["alasan_rapi"] = ui.alasan_rapi(p["alasan"])
        masuk = pid in ew_ids
        utama = ui.tindakan_utama(pd.Series([p["rute"]]), pd.Series([masuk])).iloc[0]
        cek(f"profil {pid} utama", g["utama"] == utama, f'{g["utama"]} vs {utama}')
        cek(f"profil {pid} status", g["status_akhir"] == p["status_akhir"])
        cek(f"profil {pid} draf", [d["isi"] for d in g["draf"]] == [d["isi"] for d in pesan_template.susun(p, utama)])
        status = ui.linimasa("linimasa_status", pid)
        bayar = ui.linimasa("linimasa_bayar", pid)
        klaim = ui.linimasa("linimasa_klaim", pid).sort_values("tgl_masuk")
        reakt = ui.linimasa("linimasa_reaktivasi", pid).sort_values("tgl_reakt")
        pas = ui.pasangan_reaktivasi_klaim(reakt, klaim)
        cek(f"profil {pid} jumlah linimasa",
            (len(g["linimasa"]["status"]), len(g["linimasa"]["bayar"]), len(g["linimasa"]["klaim"]),
             len(g["linimasa"]["reaktivasi"])) == (len(status), len(bayar), len(klaim), len(reakt)))
        hari_g = [x["hari"] for x in g["linimasa"]["pasangan"]]
        hari_p = [None if pd.isna(h) else int(h) for h in (pas["hari"] if len(pas) else [])]
        cek(f"profil {pid} pasangan", hari_g == hari_p, f"{hari_g} vs {hari_p}")
        cek(f"profil {pid} terkait", [x["terkait"] for x in g["linimasa"]["pasangan"]] ==
            ([bool(v) for v in pas["terkait"]] if len(pas) else []))
        if g["ew"]:
            e_ = ui.ew_baris().loc[pid]
            kontrib = sorted(((c[len("kontribusi_"):], float(e_[c])) for c in e_.index
                              if c.startswith("kontribusi_") and float(e_[c]) > 0), key=lambda t: -t[1])[:3]
            cek(f"profil {pid} kontribusi", [(k["fitur"], k["nilai"]) for k in g["ew"]["kontribusi"]] == kontrib)
    print(f"ok   profil: {len(contoh)} peserta diperiksa")
    api("POST", "/api/masuk", {"akun": "cabang_a"})
    try:
        api("GET", "/api/peserta/P-000001" if idx.loc["P-000001", "kode_wilayah"] not in akun_py.AKUN["cabang_a"]["wilayah"]
            else "/api/peserta/P-000002")
        cek("cabang tidak boleh membuka peserta di luar wilayahnya", False)
    except urllib.error.HTTPError as e:
        cek("cabang di luar wilayah = 403", e.code == 403, str(e.code))


def hitung_keadilan_py() -> tuple[pd.DataFrame, dict]:
    """Jalankan hitung() dari halaman/keadilan.py tanpa menjalankan halamannya."""
    src = (AKAR / "halaman" / "keadilan.py").read_text(encoding="utf-8")
    pohon = ast.parse(src)
    batas = next(n.lineno for n in pohon.body if isinstance(n, ast.Assign) and "hitung()" in ast.unparse(n.value))
    simpan = [n for n in pohon.body if n.lineno < batas and (
        isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))
        or (isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)))]
    for n in simpan:
        if isinstance(n, ast.FunctionDef):
            n.decorator_list = []
    ns: dict = {"__file__": str(AKAR / "halaman" / "keadilan.py")}
    exec(compile(ast.Module(body=simpan, type_ignores=[]), "keadilan.py", "exec"), ns)
    return ns["hitung"]()


def cek_keadilan(api: Klien) -> None:
    api("POST", "/api/masuk", {"akun": "pusat"})
    g = api("GET", "/api/keadilan")
    t, info = hitung_keadilan_py()
    t = t.sort_values(["dimensi", "kelompok"]).reset_index(drop=True)
    for k, v in info.items():
        gv = g["info"][k]
        cek(f"keadilan info {k}", gv == v if not isinstance(v, float) else math.isclose(gv, v, rel_tol=1e-15),
            f"{gv} vs {v}")
    cek("keadilan jumlah baris", len(g["tabel"]) == len(t))
    for gb, (_, pb) in zip(g["tabel"], t.iterrows()):
        for kol in ["dimensi", "kelompok", "n", "n_jalur", "n_periksa", "status_jalur", "status_periksa",
                    "jarang_jalur", "jarang_periksa"]:
            cek(f"keadilan {pb['dimensi']}/{pb['kelompok']} {kol}", gb[kol] == pb[kol], f"{gb[kol]} vs {pb[kol]}")
        for kol in ["rasio_jalur", "rasio_periksa", "porsi_pop", "bagian_jalur", "bagian_periksa", "batas_atas",
                    "luar_jalur", "luar_periksa"]:
            v = pb[kol]
            gv = gb[kol]
            sama = (gv is None and not np.isfinite(v)) or (gv is not None and gv == float(v))
            cek(f"keadilan {pb['dimensi']}/{pb['kelompok']} {kol}", sama, f"{gv} vs {v}")
    print(f"ok   keadilan: {len(t)} kelompok, cocok {g['info']['cocok']}/{g['info']['baris_csv']}")


def cek_kebijakan(api: Klien) -> None:
    g = api("GET", "/api/kebijakan")
    harian, ring = ui.bunching()
    cek("kebijakan harian", len(g["harian"]) == len(harian))
    for cara in ("terjadwal", "IGD"):
        for kol in ["lompat", "lompat_ik_bawah", "lompat_ik_atas", "lebih", "kurang", "n_kasus", "n_hari0"]:
            cek(f"kebijakan {cara} {kol}", g["ringkasan"][cara][kol] == ring.loc[cara, kol])
    print(f"ok   kebijakan: lompatan terjadwal {g['ringkasan']['terjadwal']['lompat']:.1f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    api = Klien(ap.parse_args().url)
    api("GET", "/api/sesi")
    T = ui.tabel_peserta()
    cek_daftar(api, T)
    cek_profil(api, T)
    cek_keadilan(api)
    cek_kebijakan(api)
    print(f"\n{len(GAGAL)} beda" if GAGAL else "\nSemua sama dengan aplikasi Python.")
    return 1 if GAGAL else 0


if __name__ == "__main__":
    sys.exit(main())
