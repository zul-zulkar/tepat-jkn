"""Uji lapisan AI draf pesan (Z09): python uji_llm.py   (juga terbaca pytest)

Tanpa kunci API dan tanpa internet: AI diganti klien tiruan, dan lapisan HTTP diuji lewat server
lokal. Yang diuji adalah janji Z09:
  jalur tidak berubah | tanpa kata curang dan ancaman | menyebut REHAB 3.0/autodebet/PBI |
  keluaran JSON | API mati => template tetap muncul.
Yang TIDAK bisa diuji di sini: mutu bahasa jawaban model sungguhan. Itu harus dilihat petugas.
"""
from __future__ import annotations

import contextlib
import copy
import json
import os
import sys
import threading
import time
import traceback
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd

import llm
import pesan_template as tpl

llm.JEDA_ULANG_DETIK = 0.0  # uji tidak perlu menunggu jeda coba ulang

AKAR = Path(__file__).resolve().parent / "app_data"
ENV_AI = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "TEPAT_AI", "TEPAT_LLM_MODEL",
          "TEPAT_LLM_PROVIDER", "ANTHROPIC_BASE_URL", "GEMINI_BASE_URL", "TEPAT_AI_BATAS_HARIAN",
          "TEPAT_AI_TIMEOUT")


@contextlib.contextmanager
def lingkungan(**kv):
    """Atur env AI (None = hapus). Mengembalikan keadaan semula."""
    lama = {k: os.environ.get(k) for k in ENV_AI}
    for k in ENV_AI:
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in kv.items() if v is not None})
    llm._pemakaian.update(tgl=None, n=0)
    try:
        yield
    finally:
        for k in ENV_AI:
            os.environ.pop(k, None)
        os.environ.update({k: v for k, v in lama.items() if v is not None})


# ------------------------------------------------------------------ data contoh (meniru tepat_ui.tabel_peserta)
def _data() -> tuple[pd.DataFrame, pd.DataFrame]:
    pes = pd.read_parquet(AKAR / "peserta.parquet")
    dk = pd.read_parquet(AKAR / "daftar_kerja.parquet").drop(columns=["rentang_desil"])
    ew = pd.read_parquet(AKAR / "ew_daftar.parquet")
    t = pes.merge(dk, on="id_peserta", how="left", validate="1:1")
    e_ = ew[["id_peserta", "skor", "alasan", "saran_intervensi"]].rename(
        columns={"skor": "ew_skor", "alasan": "ew_alasan", "saran_intervensi": "ew_saran"})
    t = t.merge(e_, on="id_peserta", how="left")
    t["alasan_rapi"] = t["alasan"].fillna("")
    return t, ew


T, EW = _data()


def peserta(rute: str, *, n_min: int | None = None, n_eq: int | None = None, saran: str | None = None) -> dict:
    d = T[T["rute"] == rute] if saran is None else T[T["ew_saran"] == saran]
    if n_min is not None:
        d = d[d["tunggakan_bulan"] >= n_min]
    if n_eq is not None:
        d = d[d["tunggakan_bulan"] == n_eq]
    assert len(d), (rute, n_min, n_eq, saran)
    return d.sort_values("id_peserta").iloc[0].to_dict()


P_PENGINGAT = peserta("pengingat_autodebet_REHAB", n_min=1)
P_PENGINGAT_LUNAS = peserta("pengingat_autodebet_REHAB", n_eq=0)
P_PBI = peserta("rujuk_cek_kelayakan_PBI")
P_NONAKTIF = peserta("nonaktif_lama_tanpa_sinyal")
P_VERIF = peserta("verifikasi_pola_reaktivasi")
P_EW = peserta("tanpa_tindakan", saran="pengingat_H-5_dan_tawaran_autodebet")
KASUS_AI = [(P_PENGINGAT, P_PENGINGAT["rute"]), (P_PENGINGAT_LUNAS, P_PENGINGAT_LUNAS["rute"]),
            (P_PBI, P_PBI["rute"]), (P_NONAKTIF, P_NONAKTIF["rute"]), (P_EW, "peringatan_dini"),
            (peserta("x", saran="pengingat_saldo_autodebet"), "peringatan_dini"),
            (peserta("x", saran="cek_kelayakan_PBI"), "peringatan_dini")]


# ------------------------------------------------------------------ klien tiruan
def jawaban(p: dict, tindakan: str, *, jalur: str | None = None, pesan: str | None = None,
            ringkasan: str = "Peserta menunggak; pesan mengingatkan opsi yang ada.") -> str:
    """Jawaban 'AI' yang sah: template dengan nomor peserta diganti {ID}. Bagian bisa ditimpa."""
    isi = tpl.susun(p, tindakan)[0]["isi"].replace(str(p["id_peserta"]), "{ID}")
    return json.dumps({"jalur": tindakan if jalur is None else jalur,
                       "pesan_peserta": isi if pesan is None else pesan, "ringkasan_petugas": ringkasan},
                      ensure_ascii=False)


class Tiruan:
    def __init__(self, balas):
        self.balas, self.n, self.masukan, self.sistem = balas, 0, None, None

    def __call__(self, sistem: str, masukan: str) -> str:
        self.n += 1
        self.sistem, self.masukan = sistem, masukan
        if isinstance(self.balas, BaseException):
            raise self.balas
        return self.balas


def tolak(p, tindakan, mentah, kode, rinci_mengandung=None):
    """susun() harus jatuh ke template dengan kode tertentu, dan draf = template apa adanya."""
    asli = copy.deepcopy(p)
    with lingkungan():
        h = llm.susun(p, tindakan, klien=Tiruan(mentah))
    assert h.status == "template", (kode, h)
    assert h.cadangan == kode, (kode, h.cadangan, h.rinci)
    assert h.draf == tpl.susun(p, tindakan), "draf harus sama dengan template"
    assert h.jalur == tindakan and p == asli
    if rinci_mengandung:
        assert rinci_mengandung in h.rinci, (rinci_mengandung, h.rinci)
    return h


# ------------------------------------------------------------------ uji
def test_template_lolos_aturan_sendiri():
    """Cadangan tidak boleh melanggar aturan yang dipakai untuk menilai AI."""
    gagal = []
    n = 0
    for rute in ["pengingat_autodebet_REHAB", "rujuk_cek_kelayakan_PBI", "nonaktif_lama_tanpa_sinyal"]:
        d_ = T[T["rute"] == rute]
        for p in d_.sample(min(400, len(d_)), random_state=7).to_dict("records"):
            d = tpl.susun(p, rute)[0]
            v = llm.periksa_pesan_peserta(d["isi"].replace(p["id_peserta"], "{ID}"), kode_aturan=rute,
                                          bulan=int(p["tunggakan_bulan"]), nominal=llm._nominal(p))
            n += 1
            if v:
                gagal.append((rute, p["id_peserta"], v))
    for saran in T["ew_saran"].dropna().unique():
        d_ = T[T["ew_saran"] == saran]
        for p in d_.sample(min(300, len(d_)), random_state=7).to_dict("records"):
            d = tpl.susun(p, "peringatan_dini")[0]
            v = llm.periksa_pesan_peserta(d["isi"].replace(p["id_peserta"], "{ID}"),
                                          kode_aturan=f"peringatan_dini:{saran}",
                                          bulan=int(p["tunggakan_bulan"]), nominal=llm._nominal(p))
            n += 1
            if v:
                gagal.append((saran, p["id_peserta"], v))
    assert not gagal, f"{len(gagal)} dari {n} template melanggar: {gagal[:3]}"


def test_api_mati_template_tetap_muncul():
    for galat in (llm.AIGagal("api_error", "HTTP 503"), llm.AIGagal("timeout"), OSError("putus"),
                  urllib.error.URLError("tak terhubung"), RuntimeError("bug")):
        for p, t in KASUS_AI:
            with lingkungan():
                h = llm.susun(p, t, klien=Tiruan(galat))
            assert h.status == "template" and h.draf == tpl.susun(p, t) and h.draf, (galat, t)
    assert llm.susun(P_PBI, P_PBI["rute"], klien=Tiruan(RuntimeError("x"))).cadangan == "kesalahan_tak_terduga"


def test_tanpa_kunci_dan_saklar():
    with lingkungan():
        h = llm.susun(P_PBI, P_PBI["rute"])
    assert (h.status, h.cadangan) == ("template", "tanpa_kunci") and h.draf
    for nilai in ("off", "0", "false", "MATI"):
        with lingkungan(ANTHROPIC_API_KEY="k", TEPAT_AI=nilai):
            c = Tiruan(jawaban(P_PBI, P_PBI["rute"]))
            h = llm.susun(P_PBI, P_PBI["rute"], klien=c)
            assert (h.cadangan, c.n) == ("dimatikan", 0), nilai
    c = Tiruan(jawaban(P_PBI, P_PBI["rute"]))
    h = llm.susun(P_PBI, P_PBI["rute"], klien=c, pakai_ai=False)
    assert (h.cadangan, c.n, h.status) == ("dimatikan", 0, "template")


def test_keluaran_json():
    for mentah in ("bukan json sama sekali", "", "{rusak", "[1,2]", '{"jalur": "x"}',
                   json.dumps({"jalur": P_PBI["rute"], "pesan_peserta": 5, "ringkasan_petugas": "a"})):
        tolak(P_PBI, P_PBI["rute"], mentah, "json_rusak")
    # pagar kode ``` dan teks pembuka masih diterima bila JSON-nya utuh
    ok = "Berikut jawabannya:\n```json\n" + jawaban(P_PBI, P_PBI["rute"]) + "\n```"
    with lingkungan():
        assert llm.susun(P_PBI, P_PBI["rute"], klien=Tiruan(ok)).status == "ai"


def test_jalur_tidak_berubah():
    for p, t in KASUS_AI:
        for lain in ("rujuk_cek_kelayakan_PBI", "verifikasi_pola_reaktivasi", "tanpa_tindakan", "", "PERINGATAN_DINI"):
            if lain != t:
                tolak(p, t, jawaban(p, t, jalur=lain), "jalur_berubah")
        with lingkungan():  # jalur yang sah lolos, dan Hasil.jalur selalu = masukan
            h = llm.susun(p, t, klien=Tiruan(jawaban(p, t)))
        assert h.status == "ai" and h.jalur == t, (t, h)


def _dasar() -> tuple[dict, str, str]:
    p = P_PENGINGAT
    n, rp, iur = int(p["tunggakan_bulan"]), tpl._rp(p["tunggakan_rp"]), tpl._rp(p["iuran_bulanan"])
    return p, p["rute"], (f"Yth. peserta JKN ({{ID}}), iuran JKN Anda tercatat belum dibayar selama {n} bulan "
                          f"({rp}). Anda bisa mengajukan cicilan lewat REHAB 3.0 atau mendaftarkan autodebet "
                          f"agar iuran {iur} per bulan terbayar otomatis. Informasi lebih lanjut: Care Center 165.")


def test_dasar_lolos():
    p, t, pesan = _dasar()
    with lingkungan():
        h = llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=pesan)))
    assert h.status == "ai", (h.cadangan, h.rinci)
    assert "{ID}" not in h.draf[0]["isi"] and p["id_peserta"] in h.draf[0]["isi"]
    assert h.draf[0]["jenis"] == "pesan_peserta" and h.ringkasan_petugas


def test_kata_curang_dan_tuduhan():
    p, t, dasar = _dasar()
    for sisip, kode in [("Jangan curang ya.", "curang"), ("Ini KECURANGAN.", "curang"),
                        ("Kami menduga c u r a n g.", "curang"), ("c.u.r.a.n.g", "curang"),
                        ("Anda sengaja menunggak.", "tuduhan"), ("Jangan pura-pura lupa.", "tuduhan"),
                        ("Ini pelanggaran.", "tuduhan"), ("Cu​rang", "curang")]:
        tolak(p, t, jawaban(p, t, pesan=dasar + " " + sisip), "melanggar_aturan", kode)


def test_ancaman_dan_tekanan():
    p, t, dasar = _dasar()
    for sisip in ("Anda akan dikenakan denda.", "Kami akan melaporkan Anda ke polisi.", "Ada sanksi bagi Anda.",
                  "Ini kesempatan terakhir.", "Kepesertaan akan diblokir.", "Hak Anda akan dicabut.",
                  "Konsekuensinya serius.", "Jangan sampai terlambat.", "Proses hukum menanti.",
                  "Bisa dipidana.", "S a n k s i berat."):
        tolak(p, t, jawaban(p, t, pesan=dasar + " " + sisip), "melanggar_aturan", "ancaman")


def test_opsi_wajib_per_jalur():
    pb, tb = P_PBI, P_PBI["rute"]
    mulai = f"Yth. peserta JKN ({{ID}}), iuran JKN Anda tercatat belum dibayar selama {int(pb['tunggakan_bulan'])} bulan. "
    tolak(pb, tb, jawaban(pb, tb, pesan=mulai + "Silakan hubungi kantor desa. Informasi: Care Center 165."),
          "melanggar_aturan", "tanpa_opsi:PBI")
    p, t, dasar = _dasar()
    tolak(p, t, jawaban(p, t, pesan=dasar.replace("REHAB 3.0", "REHAB").replace("autodebet", "bayar sendiri")),
          "melanggar_aturan", "rehab_tanpa_3.0")
    tolak(p, t, jawaban(p, t, pesan=dasar.replace("REHAB 3.0", "program cicilan").replace("autodebet", "bayar")),
          "melanggar_aturan", "tanpa_opsi")
    ew = P_EW
    tolak(ew, "peringatan_dini", jawaban(ew, "peringatan_dini", pesan=(
        "Yth. peserta JKN ({ID}), iuran JKN bulan depan jatuh tempo tanggal 10. Mohon dicek ya. "
        "Informasi lebih lanjut: Care Center 165.")), "melanggar_aturan", "tanpa_opsi:autodebet")


def test_jalur_pbi_tanpa_opsi_bayar():
    """Temuan uji model asli 29 Okt: draf jalur PBI menyelipkan autodebet/REHAB. Peserta yang diarahkan ke
    cek PBI tidak boleh didorong membayar. Berlaku untuk jalur PBI saja."""
    pb, tb = P_PBI, P_PBI["rute"]
    dasar = jawaban(pb, tb)
    with lingkungan():
        assert llm.susun(pb, tb, klien=Tiruan(dasar)).status == "ai"  # template PBI sendiri lolos
    isi = json.loads(dasar)["pesan_peserta"]
    for sisip in ("Anda juga dapat mendaftarkan autodebet.", "Pakai auto-debet saja.", "Atau auto debet.",
                  "Ikuti program REHAB 3.0.", "Atau opsi REHAB.", "Ajukan cicilan tunggakan.",
                  "Bisa mencicil tunggakan.", "Tunggakan dapat dicicil.", "Ada angsuran ringan.",
                  "Anda bisa mengangsur."):
        tolak(pb, tb, jawaban(pb, tb, pesan=isi + " " + sisip), "melanggar_aturan", "opsi_bayar_di_jalur_pbi")
    # jalur lain tidak terkena aturan ini
    for kode in ("nonaktif_lama_tanpa_sinyal", "pengingat_autodebet_REHAB",
                 "peringatan_dini:pengingat_H-5_dan_tawaran_autodebet"):
        assert "opsi_bayar_di_jalur_pbi" not in llm.periksa_pesan_peserta(
            "REHAB 3.0, autodebet, cicilan, angsuran, PBI", kode_aturan=kode, bulan=3, nominal=[1])
    # prompt: larangan hanya untuk jalur PBI; "jangan menambah opsi" untuk semua jalur
    c = Tiruan(dasar)
    with lingkungan():
        llm.susun(pb, tb, klien=c)
    assert "jangan menyebut autodebet" in c.sistem and "Jangan menambah opsi" in c.sistem
    for p, t in KASUS_AI:
        if t == tb:
            continue
        c = Tiruan(jawaban(p, t))
        with lingkungan():
            llm.susun(p, t, klien=c)
        assert "jangan menyebut autodebet" not in c.sistem and "Jangan menambah opsi" in c.sistem, t


def test_opsi_hanya_dari_template():
    """Temuan uji model asli: draf jalur nonaktif menambah 'autodebet' yang tidak ada di template. Opsi (REHAB 3.0 /
    autodebet / PBI) di pesan AI harus himpunan bagian dari opsi di template peserta itu, untuk semua jalur."""
    # 1. himpunan opsi template memang seperti yang diasumsikan aturan kelayakan
    harapan = {
        id(P_PBI): {"PBI"}, id(P_NONAKTIF): {"REHAB 3.0", "PBI"}, id(P_PENGINGAT): {"REHAB 3.0", "autodebet"},
        id(P_PENGINGAT_LUNAS): {"autodebet"},  # tanpa tunggakan: tidak ada cicilan REHAB untuk ditawarkan
    }
    for p in (P_PBI, P_NONAKTIF, P_PENGINGAT, P_PENGINGAT_LUNAS):
        assert set(llm.opsi_dalam(tpl.susun(p, p["rute"])[0]["isi"])) == harapan[id(p)], p["rute"]
    # 2. penambahan opsi di luar template ditolak di setiap jalur, termasuk ejaan lain
    kasus = [
        (P_NONAKTIF, P_NONAKTIF["rute"], ["Anda juga bisa mendaftarkan autodebet.", "Pakai auto-debet saja.",
                                         "Atau auto debet lewat bank."], "autodebet"),
        (P_PENGINGAT_LUNAS, P_PENGINGAT_LUNAS["rute"], ["Anda dapat memakai program REHAB 3.0.",
                                                        "Bisa juga lewat Rehab 3.0."], "REHAB 3.0"),
        (P_PENGINGAT, P_PENGINGAT["rute"], ["Atau cek PBI di kantor desa."], "PBI"),
        (P_PBI, P_PBI["rute"], ["Anda dapat mendaftarkan autodebet."], "autodebet"),
        (P_EW, "peringatan_dini", ["Bisa juga ajukan REHAB 3.0.", "Cek juga PBI di kantor desa."], "REHAB 3.0|PBI"),
    ]
    for p, t, sisipan, opsi in kasus:
        isi = json.loads(jawaban(p, t))["pesan_peserta"]
        for s in sisipan:
            h = tolak(p, t, jawaban(p, t, pesan=isi + " " + s), "melanggar_aturan")
            assert "opsi_di_luar_template:" in h.rinci and any(o in h.rinci for o in opsi.split("|")), (t, s, h.rinci)
    for saran, tambah in (("pengingat_saldo_autodebet", "Atau ajukan REHAB 3.0."), ("cek_kelayakan_PBI", "Pakai autodebet.")):
        pe = peserta("x", saran=saran)
        isi = json.loads(jawaban(pe, "peringatan_dini"))["pesan_peserta"]
        tolak(pe, "peringatan_dini", jawaban(pe, "peringatan_dini", pesan=isi + " " + tambah), "melanggar_aturan",
              "opsi_di_luar_template")
    # 3. menyebut lebih sedikit opsi dari template tetap sah (asal opsi wajib jalur terpenuhi)
    p, t = P_PENGINGAT, P_PENGINGAT["rute"]
    sedikit = json.loads(jawaban(p, t))["pesan_peserta"].replace("REHAB 3.0", "program cicilan")
    assert "REHAB" not in sedikit
    with lingkungan():
        assert llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=sedikit))).status == "ai"
    # 4. tanpa opsi_boleh (pemanggil lain) aturan ini tidak berlaku; template sendiri selalu lolos
    assert not [x for x in llm.periksa_pesan_peserta("REHAB 3.0 autodebet PBI", kode_aturan="x", bulan=1, nominal=[1])
                if x.startswith("opsi_di_luar")]
    assert llm.opsi_dalam("REHAB 3.0, auto debet, PBI") == {"REHAB 3.0", "autodebet", "PBI"}
    assert llm.opsi_dalam("peserta pbiasa, rehabilitasi medis") == frozenset()  # kata lain bukan opsi
    assert llm.opsi_dalam("lewat REHAB3.0") == {"REHAB 3.0"}
    assert llm.opsi_dalam("cek lewat pbi") == {"PBI"} and llm.opsi_dalam("Pbi") == {"PBI"}  # ejaan lain tak lolos


def test_penguat_kepastian_ditolak():
    """Temuan uji model asli 30 Okt: 'mungkin memenuhi syarat' di template PBI menjadi 'besar kemungkinan Anda
    memenuhi syarat' dan lolos. Pesan tidak boleh lebih pasti daripada template."""
    pb, tb = P_PBI, P_PBI["rute"]
    dasar = json.loads(jawaban(pb, tb))["pesan_peserta"]
    assert "mungkin memenuhi syarat" in dasar
    for ganti in ("besar kemungkinan memenuhi syarat", "Besar  Kemungkinan memenuhi syarat",
                  "besar\nkemungkinan memenuhi syarat", "tinggi kemungkinan memenuhi syarat",
                  "kemungkinan besar memenuhi syarat", "sangat mungkin memenuhi syarat",
                  "amat mungkin memenuhi syarat", "hampir pasti memenuhi syarat", "sudah pasti memenuhi syarat",
                  "pasti memenuhi syarat", "dipastikan memenuhi syarat"):
        tolak(pb, tb, jawaban(pb, tb, pesan=dasar.replace("mungkin memenuhi syarat", ganti)),
              "melanggar_aturan", "klaim_pasti")
    # berlaku juga untuk jalur lain dan sisipan di tempat lain
    p, t, dasar2 = _dasar()
    tolak(p, t, jawaban(p, t, pesan=dasar2 + " Pembayaran dipastikan berhasil."), "melanggar_aturan", "klaim_pasti")
    # kata sah yang mirip tidak ditolak: template sendiri memakai 'Pastikan', draf wajar memakai 'Jaminan Kesehatan'
    for aman in ("mungkin memenuhi syarat", "kemungkinan memenuhi syarat", "dapat mengecek apakah memenuhi syarat"):
        with lingkungan():
            h = llm.susun(pb, tb, klien=Tiruan(jawaban(pb, tb, pesan=dasar.replace("mungkin memenuhi syarat", aman))))
        assert h.status == "ai", (aman, h.cadangan, h.rinci)
    for kalimat in ("Pastikan saldo rekening cukup.", "Kami akan memastikan data Anda.", "Program Jaminan Kesehatan Nasional.",
                    "Untuk kepastian, hubungi Care Center 165.", "Besarnya kemungkinan tidak kami ketahui.",
                    "Iuran besar bukan masalah."):
        assert not llm._KEPASTIAN.search(kalimat), kalimat
    # prompt memuat aturan yang sama untuk semua jalur
    for pp, tt in KASUS_AI:
        c = Tiruan(jawaban(pp, tt))
        with lingkungan():
            llm.susun(pp, tt, klien=c)
        assert "Jangan menaikkan kepastian" in c.sistem and "besar kemungkinan" in c.sistem, tt


def test_bawaan_sesuai_hasil_uji_nyata():
    """Bawaan dikunci ke hasil uji 29 Okt (6/6 sukses, tercepat); 3.8-flash sering 503, 20 dtk terlalu ketat."""
    assert llm.MODEL_GEMINI == "gemini-3.1-flash-lite"
    assert llm.BATAS_WAKTU_DETIK >= 40
    with lingkungan(GEMINI_API_KEY="k"):
        assert llm.klien_dari_lingkungan()[1:] == ("gemini", "gemini-3.1-flash-lite")


# Draf asli Gemini dari uji 29 Okt yang ejaannya sudah rapi: bahan uji negatif perapian spasi.
DRAF_ASLI_RAPI = [
    "Yth. Peserta JKN dengan nomor P-000002, kami menginformasikan bahwa saat ini terdapat catatan tunggakan iuran "
    "selama 8 bulan dengan total Rp1.200.000. Mengingat kondisi tersebut, Bapak/Ibu dapat melakukan pengecekan untuk "
    "melihat kemungkinan masuk dalam kategori peserta PBI yang iurannya dibayarkan oleh pemerintah. Silakan datang ke "
    "kantor desa, kelurahan, atau Dinas Sosial setempat untuk proses pendataan lebih lanjut. Untuk bantuan informasi, "
    "Bapak/Ibu dapat menghubungi BPJS Kesehatan Care Center 165 atau melalui aplikasi Mobile JKN. Terima kasih atas "
    "perhatiannya.",
    "Yth. peserta JKN dengan nomor P-000003, kepesertaan JKN Anda saat ini dalam status tidak aktif dengan total "
    "tunggakan iuran selama 14 bulan sebesar Rp2.100.000. Kami ingin mendukung agar Anda kembali mendapatkan "
    "perlindungan kesehatan. Jika pembayaran iuran terasa memberatkan, Anda dapat memanfaatkan program REHAB 3.0 "
    "untuk mencicil tunggakan atau menanyakan kemungkinan bantuan iuran melalui PBI di kantor desa atau kelurahan "
    "setempat. Untuk informasi lebih lanjut, silakan mengakses aplikasi Mobile JKN atau menghubungi BPJS Kesehatan "
    "Care Center 165.",
    "Yth. peserta JKN (nomor peserta P-000003), kepesertaan JKN Anda sudah lama nonaktif dengan tunggakan 14 bulan "
    "(Rp2.100.000). Kami ingin membantu agar Anda dapat kembali terlindungi.\n\nBila iuran terasa berat, Anda dapat "
    "meringankan cicilan tunggakan melalui program REHAB 3.0, atau menanyakan opsi bantuan iuran (PBI) di kantor "
    "desa atau kelurahan setempat.\n\nUntuk informasi lebih lanjut, silakan manfaatkan aplikasi Mobile JKN atau "
    "hubungi BPJS Kesehatan Care Center 165. Terima kasih.",
]


def test_rapikan_spasi_pola():
    """Kata menempel yang muncul di keluaran model asli (uji 29 Okt) diperbaiki; hanya spasi yang bertambah."""
    r = llm.rapikan_spasi
    kasus = [
        ("total Rp450.000.Selama iuran", "total Rp450.000. Selama iuran", 1),
        ("selama 3 bulan,Anda dapat", "selama 3 bulan, Anda dapat", 1),
        ("selama 3 bulan,anda dapat", "selama 3 bulan, anda dapat", 1),
        ("lewat programREHAB 3.0", "lewat program REHAB 3.0", 1),
        ("aplikasi MobileJKN atau", "aplikasi Mobile JKN atau", 1),
        ("hubungi BPJSKesehatan Care Center", "hubungi BPJS Kesehatan Care Center", 1),
        ("tunggakanRp450.000 saja", "tunggakan Rp450.000 saja", 1),
        ("peserta nomor{ID}, iuran", "peserta nomor {ID}, iuran", 1),
        ("{ID}iuran Anda tercatat", "{ID} iuran Anda tercatat", 1),
        ("mohon melakukanpelunasan iuran", "mohon melakukan pelunasan iuran", 1),
        ("agar dapatterus aktif", "agar dapat terus aktif", 1),
        ("kembali terlindungioleh program", "kembali terlindungi oleh program", 1),
        ("Anda dapat atauberkonsultasi di", "Anda dapat atau berkonsultasi di", 1),
        ("Informasi lebihlanjut dapat", "Informasi lebih lanjut dapat", 1),
        ("Lebihlanjut hubungi", "Lebih lanjut hubungi", 1),
        ("REHAB 3.0 untukmencicil tunggakan", "REHAB 3.0 untuk mencicil tunggakan", 1),
        ("akses layanankesehatan", "akses layanan kesehatan", 1),
        ("LAYANANKESEHATAN", "LAYANAN KESEHATAN", 1),  # kosakata tak peka huruf besar; kapitalisasi asli dipertahankan
        ("lebihlanjut dan untukmencicil, Anda", "lebih lanjut dan untuk mencicil, Anda", 2),
        # dua bentuk dari uji nyata ke-5 yang LOLOS dari tabel lama (tabel tujuh bentuk menangkap 0 dari 2)
        ("kami menyarankan Bapak/Ibuuntuk mengecek", "kami menyarankan Bapak/Ibu untuk mengecek", 1),
        ("selama 3 bulan dengantotal Rp450.000", "selama 3 bulan dengan total Rp450.000", 1),
        # kata yang belum pernah dilihat, tetapi gabungan dua kata kosakata
        ("Bapak/Ibumungkin memenuhi syarat", "Bapak/Ibu mungkin memenuhi syarat", 1),
        ("Bapak/Ibuyang masih aktif", "Bapak/Ibu yang masih aktif", 1),
        ("silakan untukpelunasan iuran", "silakan untuk pelunasan iuran", 1),
        ("tunggakaniuran Anda", "tunggakan iuran Anda", 1),
        ("datang ke kantordesa setempat", "datang ke kantor desa setempat", 1),
        ("Anda dapatmelakukan pembayaran", "Anda dapat melakukan pembayaran", 1),
        ("kepesertaanaktif kembali", "kepesertaan aktif kembali", 1),
    ]
    for kotor, benar, n in kasus:
        hasil, k = r(kotor)
        assert (hasil, k) == (benar, n), (kotor, hasil, k)
        assert r(hasil) == (hasil, 0), ("tidak idempoten", hasil)  # teks rapi tidak disentuh lagi
        assert hasil.replace(" ", "").lower() == kotor.replace(" ", "").lower(), "hanya spasi yang boleh bertambah"


def test_rapikan_spasi_tidak_merusak_teks_benar():
    r = llm.rapikan_spasi
    for t in DRAF_ASLI_RAPI:
        assert r(t) == (t, 0), t[:60]
    for t in ("Rp1.200.000", "REHAB 3.0", "WhatsApp", "Mobile JKN", "versi 3.0", "Yth. peserta", "e-KTP", "P-000001",
              "pukul 10.30", "(PBI).", "BPJS Kesehatan", "Care Center 165.", "Bapak/Ibu", "iuran, atau", "{ID}",
              "Rp 450.000", "autodebet;", "dapatkan layanan", "daripada", "bagaimana", "kepesertaan JKN-nya",
              "Bapak/Ibunda", "Bapak/Ibuku", "Bapak/Ibumu", "Bapak/Ibunya"):  # kata ganti/imbuhan sah setelah "Ibu"
        assert r(t) == (t, 0), t
    # seluruh jenis template asli (ratusan peserta nyata, semua rute) tidak boleh berubah satu karakter pun
    n = 0
    for rute in ["pengingat_autodebet_REHAB", "rujuk_cek_kelayakan_PBI", "nonaktif_lama_tanpa_sinyal"]:
        d_ = T[T["rute"] == rute]
        for p in d_.sample(min(300, len(d_)), random_state=3).to_dict("records"):
            isi = tpl.susun(p, rute)[0]["isi"]
            assert r(isi) == (isi, 0), (rute, p["id_peserta"])
            assert r(isi.replace(p["id_peserta"], "{ID}")) == (isi.replace(p["id_peserta"], "{ID}"), 0)
            n += 1
    for saran in T["ew_saran"].dropna().unique():
        d_ = T[T["ew_saran"] == saran]
        for p in d_.sample(min(200, len(d_)), random_state=3).to_dict("records"):
            isi = tpl.susun(p, "peringatan_dini")[0]["isi"]
            assert r(isi) == (isi, 0), (saran, p["id_peserta"])
            n += 1
    assert n > 500, n


def test_rapikan_spasi_kata_sah_tidak_dipisah():
    """Kata sah yang mengandung kata kosakata harus utuh. Kosakata tak boleh memuat 'dari' atau 'pada'
    ('daripada' sah): memasukkannya membuat uji ini gagal."""
    r = llm.rapikan_spasi
    sah = ["dapatkan", "dapatkanlah", "mendapatkan", "diperoleh", "memperoleh", "daripada", "kepada", "sehingga",
           "apabila", "bagaimana", "terdapat", "melakukannya", "pembayarannya", "tunggakannya", "kepesertaannya",
           "beruntung", "keuntungan", "peruntukan", "layanannya", "informasinya", "bantuannya", "dengannya",
           "kesehatannya", "pelunasannya", "mengecekkan", "perlindungannya", "bermanfaat", "memudahkan",
           "pemerintahan", "pemerintahnya", "perusahaan", "mengajukannya", "berkonsultasilah", "otomatisasi",
           "kelurahannya", "aplikasinya", "terbayarkan", "dibayarkannya", "mengaksesnya", "menghubunginya"]
    for w in sah:
        assert r(w) == (w, 0), w
        assert r(w.capitalize()) == (w.capitalize(), 0), w
        assert r(f"Silakan {w} segera.") == (f"Silakan {w} segera.", 0), w


def test_kosakata_perapian_konsisten():
    """Tak ada anggota yang sendirinya gabungan dua anggota lain (kalau ada, kata sah ikut terbelah)."""
    V = llm._KOSAKATA
    assert len(V) > 50 and all(w.isalpha() and w == w.lower() for w in V)
    gabungan = [(w, w[:i], w[i:]) for w in V for i in range(3, len(w) - 2) if w[:i] in V and w[i:] in V]
    assert not gabungan, gabungan
    assert not ({"dari", "pada", "ke", "di", "ter", "per", "ber", "mem", "men", "kan", "nya"} & V)
    # panjang minimum bagian (3 huruf) dan pemisahan yang tak ambigu: urutan percobaan di _pisah_gabungan tak berpengaruh
    assert min(map(len, V)) >= 3
    dua = {}
    for a in V:
        for b in V:
            dua.setdefault(a + b, set()).add((a, b))
    ambigu = {k: v for k, v in dua.items() if len(v) > 1}
    assert not ambigu, ambigu


def test_karakter_tak_terlihat_dibuang_sebelum_penilaian_dan_perapian():
    """Karakter tak terlihat di antara dua kata membuat kata tampak menempel dan lolos perapian spasi. Validator
    menilai teks ternormalisasi, jadi yang sampai ke petugas juga harus teks yang sama."""
    b = llm.bersihkan_karakter
    assert b("BPJS\u200bKesehatan") == "BPJSKesehatan"
    assert b("a\u00adb\u200cc\u200dd\u2060e\ufefff\u200eg\u200fh") == "abcdefgh"
    assert b("Rp450.000\u00a0per\u202fbulan") == "Rp450.000 per bulan"
    assert b("teks biasa, Bapak/Ibu. REHAB 3.0\n- butir") == "teks biasa, Bapak/Ibu. REHAB 3.0\n- butir"
    p, t, dasar = _dasar()
    kotor = (dasar.replace("Informasi lebih lanjut", "Informasi\u200blebih\u200b lanjut")
             .replace("lewat REHAB 3.0", "lewat\u00a0REHAB\u202f3.0").replace("Anda", "An\u00adda", 1))
    assert kotor != dasar
    with lingkungan():
        h = llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=kotor)))
    assert h.status == "ai", (h.cadangan, h.rinci)
    isi = h.draf[0]["isi"]
    assert all(ord(c) < 128 for c in isi), sorted({hex(ord(c)) for c in isi if ord(c) > 127})
    assert isi == llm._norm(isi) and "Informasi lebih lanjut" in isi and "lewat REHAB 3.0" in isi
    # dirapikan menghitung hanya perbaikan spasi: "Informasi\u200blebih" -> "Informasilebih" -> "Informasi lebih"
    assert "Informasilebih" not in isi
    # ringkasan petugas ikut dibersihkan
    with lingkungan():
        h2 = llm.susun(p, t, klien=Tiruan(jawaban(p, t, ringkasan="Pesan\u200b sesuai\u00a0jalur.")))
    assert h2.status == "ai" and h2.ringkasan_petugas == "Pesan sesuai jalur."
    # gejala uji nyata 29 Okt: pemisah tak terlihat di antara "BPJS" dan "Kesehatan" -> dipisah normal
    pb, tb = P_PBI, P_PBI["rute"]
    dasar_pbi = json.loads(jawaban(pb, tb))["pesan_peserta"]
    assert "BPJS Kesehatan" in dasar_pbi
    with lingkungan():
        hp = llm.susun(pb, tb, klien=Tiruan(jawaban(pb, tb, pesan=dasar_pbi.replace("BPJS Kesehatan", "BPJS\u200bKesehatan"))))
    assert hp.status == "ai" and hp.dirapikan == 2, (hp.cadangan, hp.rinci, hp.dirapikan)
    assert "BPJSKesehatan" not in hp.draf[0]["isi"] and "\u200b" not in hp.draf[0]["isi"]
    assert hp.draf[0]["isi"].count("BPJS Kesehatan") == dasar_pbi.count("BPJS Kesehatan") == 2
    # kata terlarang yang disamarkan dengan karakter tak terlihat tetap ditolak
    tolak(p, t, jawaban(p, t, pesan=dasar + " Ini cu\u200brang."), "melanggar_aturan", "curang")


def test_susun_merapikan_spasi_lalu_menilai_teks_rapi():
    p, t, dasar = _dasar()
    kotor = dasar.replace("Informasi lebih lanjut", "Informasi lebihlanjut").replace("lewat REHAB 3.0", "lewatREHAB 3.0")
    assert kotor != dasar
    with lingkungan():
        h = llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=kotor)))
    assert h.status == "ai", (h.cadangan, h.rinci)
    isi = h.draf[0]["isi"]
    assert "lebih lanjut" in isi and "lewat REHAB 3.0" in isi and "lebihlanjut" not in isi and "lewatREHAB" not in isi
    assert h.dirapikan == 2 and "Spasi dirapikan otomatis di 2 tempat." in h.keterangan
    # pesan yang sudah rapi: tidak ada catatan perapian
    with lingkungan():
        h2 = llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=dasar)))
    assert h2.status == "ai" and h2.dirapikan == 0 and "dirapikan" not in h2.keterangan
    # nomor peserta yang menempel pada kata tetap berakhir sebagai nomor asli dengan spasi
    with lingkungan():
        h3 = llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=dasar.replace("peserta JKN ({ID})", "peserta nomor{ID}"))))
    assert h3.status == "ai" and f"nomor {p['id_peserta']}" in h3.draf[0]["isi"], h3.draf[0]["isi"][:80]
    # aturan dinilai pada teks yang sudah rapi: "lewatPBI" ditolak bila dinilai mentah (\bPBI\b tak cocok), lolos setelah dirapikan
    pb, tb = P_PBI, P_PBI["rute"]
    dasar_pbi = json.loads(jawaban(pb, tb))["pesan_peserta"]
    assert "(PBI)" in dasar_pbi
    with lingkungan():
        hp = llm.susun(pb, tb, klien=Tiruan(jawaban(pb, tb, pesan=dasar_pbi.replace("(PBI)", "lewatPBI"))))
    assert hp.status == "ai" and "lewat PBI" in hp.draf[0]["isi"], (hp.cadangan, hp.rinci)
    # perapian tidak melonggarkan penjaga: kata terlarang tetap ditolak
    tolak(p, t, jawaban(p, t, pesan=dasar + " Ini kasus.Jangan curang."), "melanggar_aturan", "curang")
    # prompt meminta ejaan rapi dan perubahan seminimal mungkin
    c = Tiruan(jawaban(p, t))
    with lingkungan():
        llm.susun(p, t, klien=c)
    assert "jangan menggabungkan dua kata" in c.sistem and "Ubah seminimal mungkin" in c.sistem


def test_angka_tidak_dikarang():
    p, t, dasar = _dasar()
    rp = tpl._rp(p["tunggakan_rp"])
    for salah, kode in [(dasar.replace(rp, "Rp1.234"), "nominal_salah"),
                        (dasar.replace(f"selama {int(p['tunggakan_bulan'])} bulan",
                                       f"selama {int(p['tunggakan_bulan']) + 4} bulan"), "bulan_salah"),
                        (dasar + " Hubungi 0812345678901.", "tautan_atau_kontak"),
                        (dasar + " Kunjungi www.bpjs-contoh.id.", "tautan_atau_kontak"),
                        (dasar + " Bayar sebelum 17 November.", "angka_asing"),
                        (dasar + " Bayar Rp 250 ribu saja.", "angka_asing"),
                        (dasar + " Peluang menunggak 82%.", "angka_persen"),
                        (dasar + " {nama}", "penampung_sisa")]:
        tolak(p, t, jawaban(p, t, pesan=salah), "melanggar_aturan", kode)


def test_istilah_internal_dan_panjang():
    p, t, dasar = _dasar()
    for sisip in ("Skor Anda tinggi.", "Anda berisiko menunggak.", "Menurut model AI kami.",
                  "Data DTSEN Anda desil 3.", "Sistem triase menandai Anda."):
        tolak(p, t, jawaban(p, t, pesan=dasar + " " + sisip), "melanggar_aturan", "istilah_internal")
    tolak(p, t, jawaban(p, t, pesan="REHAB 3.0 autodebet."), "melanggar_aturan", "panjang")
    tolak(p, t, jawaban(p, t, pesan=dasar + " " + "Terima kasih. " * 90), "melanggar_aturan", "panjang")


def test_ringkasan_petugas():
    p, t, dasar = _dasar()
    # boleh menyebut skor dan istilah internal di ringkasan untuk petugas
    with lingkungan():
        h = llm.susun(p, t, klien=Tiruan(jawaban(p, t, pesan=dasar, ringkasan="Skor 0,41; menunggak 3 bulan, DTSEN desil 6-10.")))
    assert h.status == "ai"
    tolak(p, t, jawaban(p, t, pesan=dasar, ringkasan="Peserta ini curang."), "melanggar_aturan", "curang@ringkasan")
    tolak(p, t, jawaban(p, t, pesan=dasar, ringkasan="x" * 500), "melanggar_aturan", "panjang_ringkasan")


def test_verifikasi_tanpa_ai():
    c = Tiruan(jawaban(P_VERIF, P_VERIF["rute"]))
    with lingkungan(ANTHROPIC_API_KEY="k"):
        h = llm.susun(P_VERIF, P_VERIF["rute"], klien=c)
    assert c.n == 0 and h.status == "template" and h.cadangan == "tanpa_pesan_peserta"
    assert h.draf[0]["jenis"] == "catatan_petugas"
    with lingkungan():
        assert llm.susun(P_VERIF, "tanpa_tindakan", klien=c).draf == [] and c.n == 0


def test_masukan_ke_ai():
    """Yang meninggalkan sistem: jalur, skor, alasan, fakta angka. Bukan nomor peserta."""
    for p, t in KASUS_AI:
        c = Tiruan(jawaban(p, t))
        with lingkungan():
            llm.susun(p, t, klien=c)
        m = json.loads(c.masukan)
        assert m["jalur"] == t and "alasan" in m and "skor" in m and "fakta" in m
        assert p["id_peserta"] not in c.masukan and p["id_peserta"] not in c.sistem
        assert "{ID}" in m["draf_template"]
        # struktur persis: tanpa wilayah, usia, jenis kelamin, desil, kelas sebagai bidang tersendiri.
        # (teks "alasan" adalah penjelasan model/aturan apa adanya, sesuai permintaan Z09.)
        assert set(m) <= {"jalur", "skor", "alasan", "fakta", "draf_template", "saran"}, set(m)
        assert set(m["fakta"]) == {"tunggakan_bulan", "tunggakan_rp", "iuran_bulanan", "sudah_autodebet"}
        for kunci in ("kode_wilayah", "usia_2023", "jenis_kelamin", "rentang_desil", "indeks_kemiskinan"):
            assert kunci not in c.masukan, kunci
        assert p["kode_wilayah"] not in c.masukan
        if t == "peringatan_dini":
            assert isinstance(m["skor"], float) and m["saran"] == p["ew_saran"]
        else:
            assert m["skor"] is None
        assert "REHAB 3.0" in c.sistem and "curang" in c.sistem


# ------------------------------------------------------------------ lapisan HTTP asli (server lokal)
class _Server:
    def __init__(self, mode="ok", teks=None, bentuk="anthropic", tidur=2):
        self.mode, self.teks, self.bentuk, self.tidur, self.terima = mode, teks, bentuk, tidur, []
        ref = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("content-length", 0))
                ref.terima.append((self.path, dict(self.headers), json.loads(self.rfile.read(n))))
                if ref.mode == "lambat":
                    time.sleep(ref.tidur)
                if ref.mode in ("401", "429", "500", "503") or (ref.mode == "503_lalu_ok" and len(ref.terima) == 1):
                    self.send_response(503 if ref.mode.startswith("503") else int(ref.mode))
                    self.end_headers()
                    return
                isi = ref.badan()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(isi.encode())

            def log_message(self, *a):
                pass

        class Sepi(HTTPServer):
            def handle_error(self, *a):  # klien yang timeout memutus koneksi; itu bagian dari uji
                pass

        self.srv = Sepi(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def badan(self) -> str:
        """Isi respons 200 menurut bentuk penyedia dan mode."""
        if self.mode == "html":
            return "<html>"
        if self.bentuk == "gemini":
            if self.mode == "kosong":   # diblokir sebelum menjawab
                return json.dumps({"promptFeedback": {"blockReason": "SAFETY"}})
            if self.mode == "terpotong":  # berhenti sebelum ada teks (mis. habis di 'berpikir')
                return json.dumps({"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]})
            bagian = [{"text": self.teks}]
            if self.mode == "pikir":    # bagian pemikiran memuat draf JSON lain; bila ikut digabung, jawaban rusak
                konsep = json.dumps({"jalur": "verifikasi_pola_reaktivasi", "pesan_peserta": "Jangan curang.",
                                     "ringkasan_petugas": "konsep"})
                bagian = [{"thought": True, "text": "Konsep awal: " + konsep}] + bagian
            return json.dumps({"candidates": [{"content": {"role": "model", "parts": bagian},
                                               "finishReason": "STOP"}]})
        if self.mode == "kosong":
            return json.dumps({"content": [], "stop_reason": "end_turn"})
        return json.dumps({"content": [{"type": "text", "text": self.teks}]})

    def tutup(self):
        self.srv.shutdown()


def test_http_berhasil_dan_bentuk_permintaan():
    p, t = P_PBI, P_PBI["rute"]
    s = _Server("ok", jawaban(p, t))
    try:
        with lingkungan(ANTHROPIC_API_KEY="kunci-rahasia-123", ANTHROPIC_BASE_URL=s.url, TEPAT_LLM_MODEL="model-uji"):
            h = llm.susun(p, t)
        assert h.status == "ai" and h.model == "model-uji", (h.cadangan, h.rinci)
        jalur, kepala, badan = s.terima[0]
        assert jalur == "/v1/messages" and badan["model"] == "model-uji"
        k = {a.lower(): b for a, b in kepala.items()}
        assert k["x-api-key"] == "kunci-rahasia-123" and k["anthropic-version"] == "2023-06-01"
        assert badan["messages"][0]["role"] == "user" and "REHAB 3.0" in badan["system"]
        assert p["id_peserta"] not in json.dumps(badan)
    finally:
        s.tutup()


def test_http_gagal_jadi_template_tanpa_bocor_kunci():
    p, t = P_PBI, P_PBI["rute"]
    for mode, kode in [("500", "api_error"), ("401", "api_error"), ("html", "api_error"),
                       ("429", "kuota"), ("kosong", "respons_kosong")]:
        s = _Server(mode)
        try:
            with lingkungan(ANTHROPIC_API_KEY="kunci-rahasia-123", ANTHROPIC_BASE_URL=s.url):
                h = llm.susun(p, t)
            assert (h.status, h.cadangan) == ("template", kode) and h.draf, (mode, h)
            assert "kunci-rahasia" not in repr(h)
        finally:
            s.tutup()
    # server mati total
    with lingkungan(ANTHROPIC_API_KEY="k", ANTHROPIC_BASE_URL="http://127.0.0.1:9"):
        h = llm.susun(p, t)
    assert (h.status, h.cadangan) == ("template", "api_error") and h.draf == tpl.susun(p, t)
    # timeout
    s = _Server("lambat")
    try:
        klien = llm.klien_anthropic("k", "m", s.url, batas_waktu=0.3)
        with lingkungan():
            h = llm.susun(p, t, klien=klien)
        assert (h.status, h.cadangan) == ("template", "timeout"), h
    finally:
        s.tutup()


def test_batas_harian():
    p, t = P_PBI, P_PBI["rute"]
    s = _Server("ok", jawaban(p, t))
    try:
        with lingkungan(ANTHROPIC_API_KEY="k", ANTHROPIC_BASE_URL=s.url, TEPAT_AI_BATAS_HARIAN="2"):
            hasil = [llm.susun(p, t) for _ in range(3)]
        assert [h.status for h in hasil] == ["ai", "ai", "template"] and hasil[2].cadangan == "batas_harian"
        assert len(s.terima) == 2
    finally:
        s.tutup()


def test_gemini_berhasil_dan_bentuk_permintaan():
    """Semua jalur lewat klien Gemini asli ke server lokal; bentuk permintaan = yang tertulis di dokumentasi."""
    for p, t in KASUS_AI:
        s = _Server("ok", jawaban(p, t), bentuk="gemini")
        try:
            with lingkungan(GEMINI_API_KEY="kunci-gemini-123", GEMINI_BASE_URL=s.url):
                h = llm.susun(p, t)
            assert h.status == "ai" and h.penyedia == "gemini" and h.model == llm.MODEL_GEMINI, (t, h.cadangan, h.rinci)
            assert "gemini" in h.keterangan.lower()
            jalur, kepala, badan = s.terima[0]
            assert jalur == f"/v1beta/models/{llm.MODEL_GEMINI}:generateContent", jalur
            k = {a.lower(): b for a, b in kepala.items()}
            assert k["x-goog-api-key"] == "kunci-gemini-123" and "authorization" not in k and "x-api-key" not in k
            assert "kunci-gemini" not in jalur, "kunci tidak boleh ada di alamat"
            assert set(badan) == {"system_instruction", "contents", "generationConfig"}, set(badan)
            assert "REHAB 3.0" in badan["system_instruction"]["parts"][0]["text"]
            assert badan["contents"][0]["role"] == "user" and badan["contents"][0]["parts"][0]["text"]
            assert set(badan["generationConfig"]) == {"maxOutputTokens"}
            assert badan["generationConfig"]["maxOutputTokens"] >= 1024
            assert p["id_peserta"] not in json.dumps(badan) and "kunci-gemini" not in json.dumps(badan)
        finally:
            s.tutup()
    s = _Server("ok", jawaban(P_PBI, P_PBI["rute"]), bentuk="gemini")  # model bisa diganti
    try:
        with lingkungan(GEMINI_API_KEY="k", GEMINI_BASE_URL=s.url, TEPAT_LLM_MODEL="gemini-3.5-flash-lite"):
            h = llm.susun(P_PBI, P_PBI["rute"])
        assert h.status == "ai" and s.terima[0][0] == "/v1beta/models/gemini-3.5-flash-lite:generateContent"
    finally:
        s.tutup()


def test_gemini_bagian_pikir_tidak_ikut_jawaban():
    p, t = P_PBI, P_PBI["rute"]
    s = _Server("pikir", jawaban(p, t), bentuk="gemini")  # bagian 'thought' memuat kata terlarang
    try:
        with lingkungan(GEMINI_API_KEY="k", GEMINI_BASE_URL=s.url):
            h = llm.susun(p, t)
        assert h.status == "ai" and "curang" not in h.draf[0]["isi"].lower(), (h.cadangan, h.rinci)
    finally:
        s.tutup()


def test_gemini_gagal_jadi_template():
    p, t = P_PBI, P_PBI["rute"]
    for mode, kode, rinci in [("429", "kuota", "HTTP 429"), ("500", "api_error", "HTTP 500"),
                              ("401", "api_error", "HTTP 401"), ("html", "api_error", ""),
                              ("kosong", "respons_kosong", "SAFETY"), ("terpotong", "respons_kosong", "MAX_TOKENS")]:
        s = _Server(mode, bentuk="gemini")
        try:
            with lingkungan(GEMINI_API_KEY="kunci-gemini-123", GEMINI_BASE_URL=s.url):
                h = llm.susun(p, t)
            assert (h.status, h.cadangan) == ("template", kode), (mode, h)
            assert rinci in h.rinci and h.draf == tpl.susun(p, t) and "kunci-gemini" not in repr(h)
        finally:
            s.tutup()
    with lingkungan(GEMINI_API_KEY="k", GEMINI_BASE_URL="http://127.0.0.1:9"):  # server mati
        h = llm.susun(p, t)
    assert (h.status, h.cadangan) == ("template", "api_error") and h.draf == tpl.susun(p, t)
    s = _Server("lambat", bentuk="gemini")
    try:
        with lingkungan():
            h = llm.susun(p, t, klien=llm.klien_gemini("k", llm.MODEL_GEMINI, s.url, batas_waktu=0.3))
        assert (h.status, h.cadangan) == ("template", "timeout"), h
    finally:
        s.tutup()
    with lingkungan(GEMINI_API_KEY="k", TEPAT_LLM_MODEL="x/../../y"):  # nama model tidak boleh jadi jalur
        h = llm.susun(p, t)
    assert (h.status, h.cadangan) == ("template", "penyedia_salah"), h


def test_pilih_penyedia():
    with lingkungan():
        assert llm.ai_tersedia() == (False, "tanpa_kunci")
    with lingkungan(GEMINI_API_KEY="g"):
        assert llm.pilih_penyedia() == ("gemini", "g") and llm.ai_tersedia() == (True, "")
    with lingkungan(GOOGLE_API_KEY="goog"):
        assert llm.pilih_penyedia() == ("gemini", "goog")
    with lingkungan(GEMINI_API_KEY="g", GOOGLE_API_KEY="goog"):
        assert llm.pilih_penyedia() == ("gemini", "g")
    with lingkungan(ANTHROPIC_API_KEY="a", GEMINI_API_KEY="g"):  # otomatis: perilaku awal dipertahankan
        assert llm.pilih_penyedia() == ("anthropic", "a")
    with lingkungan(ANTHROPIC_API_KEY="a", GEMINI_API_KEY="g", TEPAT_LLM_PROVIDER="Gemini"):
        assert llm.pilih_penyedia() == ("gemini", "g")
    with lingkungan(GEMINI_API_KEY="g", TEPAT_LLM_PROVIDER="anthropic"):
        assert llm.ai_tersedia() == (False, "tanpa_kunci")
    with lingkungan(GEMINI_API_KEY="g", TEPAT_LLM_PROVIDER="openai"):
        assert llm.ai_tersedia() == (False, "penyedia_salah")
        h = llm.susun(P_PBI, P_PBI["rute"])
        assert (h.status, h.cadangan) == ("template", "penyedia_salah") and h.draf
    with lingkungan(GEMINI_API_KEY="g", TEPAT_AI="off"):
        assert llm.ai_tersedia() == (False, "dimatikan")
    for v in ("tanpa_kunci", "penyedia_salah", "kuota", "respons_kosong"):
        assert v in llm.PESAN_CADANGAN


def test_coba_ulang_hanya_untuk_503():
    p, t = P_PBI, P_PBI["rute"]
    for bentuk, env, dasar in (("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"),
                               ("gemini", "GEMINI_API_KEY", "GEMINI_BASE_URL")):
        s = _Server("503_lalu_ok", jawaban(p, t), bentuk=bentuk)  # 503 sekali, lalu sukses
        try:
            with lingkungan(**{env: "k", dasar: s.url}):
                h = llm.susun(p, t)
            assert h.status == "ai" and len(s.terima) == 2, (bentuk, h.cadangan, h.rinci, len(s.terima))
        finally:
            s.tutup()
        s = _Server("503", bentuk=bentuk)                          # 503 terus: dicoba ulang SEKALI, lalu template
        try:
            with lingkungan(**{env: "k", dasar: s.url}):
                h = llm.susun(p, t)
            assert (h.status, h.cadangan) == ("template", "api_error") and h.draf == tpl.susun(p, t)
            assert "HTTP 503" in h.rinci and "dicoba ulang" in h.rinci and len(s.terima) == 2, (h.rinci, len(s.terima))
        finally:
            s.tutup()
        for mode, kode in (("500", "api_error"), ("429", "kuota"), ("401", "api_error")):  # tanpa coba ulang
            s = _Server(mode, bentuk=bentuk)
            try:
                with lingkungan(**{env: "k", dasar: s.url}):
                    h = llm.susun(p, t)
                assert h.cadangan == kode and len(s.terima) == 1, (bentuk, mode, h.cadangan, len(s.terima))
                assert "dicoba ulang" not in h.rinci
            finally:
                s.tutup()


def test_batas_waktu_dapat_diatur():
    with lingkungan():
        assert llm._batas_waktu() == llm.BATAS_WAKTU_DETIK
    for v, hasil in (("30", 30.0), ("abc", llm.BATAS_WAKTU_DETIK), ("0.1", 1.0), ("999", 120.0)):
        with lingkungan(TEPAT_AI_TIMEOUT=v):
            assert llm._batas_waktu() == hasil, v
            assert llm.batas_waktu() == hasil, v  # nama publik untuk teks tunggu di halaman
    s = _Server("lambat", bentuk="gemini", tidur=3)  # server menjawab setelah 3 dtk, batas 1 dtk
    try:
        with lingkungan(GEMINI_API_KEY="k", GEMINI_BASE_URL=s.url, TEPAT_AI_TIMEOUT="1"):
            t0 = time.time()
            h = llm.susun(P_PBI, P_PBI["rute"])
            dt = time.time() - t0
        assert (h.status, h.cadangan) == ("template", "timeout") and "1 dtk" in h.rinci and dt < 2.5, (h, dt)
    finally:
        s.tutup()
    s = _Server("lambat", jawaban(P_PBI, P_PBI["rute"]), bentuk="gemini", tidur=1)  # batas longgar: berhasil
    try:
        with lingkungan(GEMINI_API_KEY="k", GEMINI_BASE_URL=s.url, TEPAT_AI_TIMEOUT="10"):
            assert llm.susun(P_PBI, P_PBI["rute"]).status == "ai"
    finally:
        s.tutup()


def test_modul_ringan():
    """llm.py tidak boleh menarik paket berat (batas memori Streamlit Cloud)."""
    import subprocess
    kode = ("import sys, llm; bad=[m for m in ('pandas','numpy','streamlit','sklearn','matplotlib') "
            "if m in sys.modules]; print(','.join(bad))")
    out = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); %s" % (
        str(Path(__file__).resolve().parent), kode)], capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "", out.stdout + out.stderr


def main() -> int:
    uji = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    gagal = 0
    for n, f in uji:
        t0 = time.time()
        try:
            f()
            print(f"  lulus  {n}  ({time.time() - t0:.1f} dtk)")
        except Exception:
            gagal += 1
            print(f"  GAGAL  {n}")
            traceback.print_exc()
    print(f"\n{len(uji) - gagal}/{len(uji)} uji lulus")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
