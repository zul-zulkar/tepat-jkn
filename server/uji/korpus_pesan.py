"""Buat korpus uji untuk port Go lapisan pesan (server/internal/pesan) dari llm.py dan pesan_template.py.

Korpus berisi masukan dan jawaban fungsi Python: semua panggilan selama uji_llm.py berjalan (direkam), ditambah
variasi buatan (kata terlarang, angka, kata menempel, karakter Unicode). Uji Go membandingkan jawabannya satu
per satu, jadi aturan pesan di Go dijamin sama dengan llm.py pada seluruh korpus.

Dari folder repo:  python server/uji/korpus_pesan.py
Keluaran: server/internal/pesan/testdata/korpus.json.gz (data sintetis, tanpa kunci API).
"""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import random
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR))
KELUAR = AKAR / "server" / "internal" / "pesan" / "testdata" / "korpus.json.gz"

import llm  # noqa: E402
import pesan_template as tpl  # noqa: E402

REKAM: dict[str, list] = {k: [] for k in ("periksa", "rapikan", "bersihkan", "ringkasan", "opsi", "susun")}
KOLOM_P = ("id_peserta", "rute", "alasan", "alasan_rapi", "tunggakan_bulan", "tunggakan_rp", "iuran_bulanan",
           "autodebet", "ew_skor", "ew_alasan", "ew_saran")


def peserta_json(p: dict) -> dict:
    d = {}
    for k in KOLOM_P:
        v = p.get(k)
        if hasattr(v, "item"):
            v = v.item()
        if isinstance(v, float) and v != v:
            v = None
        d[k] = v
    return d


def rekam_fungsi():
    asli = {n: getattr(llm, n) for n in ("periksa_pesan_peserta", "rapikan_spasi", "bersihkan_karakter",
                                        "periksa_ringkasan", "opsi_dalam", "susun")}

    def periksa(teks, *, kode_aturan, bulan, nominal, opsi_boleh=None):
        h = asli["periksa_pesan_peserta"](teks, kode_aturan=kode_aturan, bulan=bulan, nominal=nominal,
                                          opsi_boleh=opsi_boleh)
        REKAM["periksa"].append(dict(teks=teks, kode=kode_aturan, bulan=int(bulan), nominal=[int(x) for x in nominal],
                                     opsi_boleh=None if opsi_boleh is None else sorted(opsi_boleh), hasil=list(h)))
        return h

    def rapikan(teks):
        h = asli["rapikan_spasi"](teks)
        REKAM["rapikan"].append(dict(teks=teks, hasil=h[0], n=h[1]))
        return h

    def bersihkan(teks):
        h = asli["bersihkan_karakter"](teks)
        REKAM["bersihkan"].append(dict(teks=teks, hasil=h))
        return h

    def ringkasan(teks):
        h = asli["periksa_ringkasan"](teks)
        REKAM["ringkasan"].append(dict(teks=teks, hasil=list(h)))
        return h

    def opsi(teks):
        h = asli["opsi_dalam"](teks)
        REKAM["opsi"].append(dict(teks=teks, hasil=sorted(h)))
        return h

    def susun(p, tindakan, *, klien=None, pakai_ai=True):
        h = asli["susun"](p, tindakan, klien=klien, pakai_ai=pakai_ai)
        env = {k: os.environ[k] for k in ("TEPAT_AI",) if k in os.environ}
        ada_kunci = any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"))
        balas = getattr(klien, "balas", None)
        if klien is not None and balas is None:
            return h  # klien lain (HTTP tiruan): tidak diputar ulang
        if klien is None and ada_kunci and pakai_ai:
            return h
        rek = dict(p=peserta_json(p), tindakan=tindakan, pakai_ai=pakai_ai, env=env, klien=klien is not None,
                   sistem=getattr(klien, "sistem", None), masukan=getattr(klien, "masukan", None),
                   hasil=dict(status=h.status, cadangan=h.cadangan, rinci=h.rinci, draf=h.draf,
                              ringkasan=h.ringkasan_petugas, dirapikan=h.dirapikan, keterangan=h.keterangan))
        if isinstance(balas, llm.AIGagal):
            rek["galat"] = dict(kode=balas.kode, rinci=balas.rinci)
        elif isinstance(balas, BaseException):
            rek["galat"] = dict(lain=type(balas).__name__)
        elif balas is not None:
            rek["balas"] = balas
        REKAM["susun"].append(rek)
        return h

    llm.periksa_pesan_peserta, llm.rapikan_spasi, llm.bersihkan_karakter = periksa, rapikan, bersihkan
    llm.periksa_ringkasan, llm.opsi_dalam, llm.susun = ringkasan, opsi, susun


# ------------------------------------------------------------------ variasi buatan
SISIPAN = [
    "curang", "c u r a n g", "c.u.r.a.n.g", "cürang", "fraud", "sengaja", "pura-pura", "berpura-pura", "menghindari",
    "menghindar", "denda", "dendanya", "sanksi", "s a n k s i", "pidana", "pıdana", "PİDANA", "dilaporkan",
    "kesempatan terakhir", "jangan sampai", "konsekuensinya", "skor", "peluang", "risiko", "model", "AI", "Ai",
    "jalur", "klaim", "reaktivasi", "DTSEN", "desil", "pasti", "dipastikan", "pastikan", "memastikan", "kepastian",
    "besar kemungkinan", "kemungkinan besar", "sangat mungkin", "hampir pasti", "sudah  pasti", "50%", "50 %",
    "persen", "https://bpjs.id", "www.bpjs-kesehatan.go.id", "bpjs.co", "@bpjs", "08123456789", "+628123456789",
    "REHAB", "REHAB 3.0", "REHAB3.0", "rehabilitasi", "Rehab 3.0", "autodebet", "auto-debet", "auto debet",
    "AUTODEBET", "PBI", "pbi", "PBIku", "cicilan", "angsuran", "mencicil", "Rp100.000", "Rp 50.000", "Rp.75.000",
    "10 bulan", "3 bulan", "2 juta", "500 ribu", "rupiah", "165", "tanggal 10", "H-5", "12", "2026", "1,5",
    "{ID}", "{nama}", "}", "Jaminan Kesehatan Nasional", "kelayakan PBI", "kepesertaan PBI", "kelayakan  PBI",
    "​curang", "cur​ang", "san­ksi", "pi⁠dana", " denda", "ｄｅｎｄａ", "１２ bulan", "٣ bulan",
    "٢٠", "curanǵ", "é", "naïf", "café", "ſanksi", "Konsekuensi", "x" * 20, "\U0001F600",
]


def mutasi(rng: random.Random, teks: str) -> str:
    t = teks
    for _ in range(rng.randint(1, 3)):
        jenis = rng.random()
        if jenis < 0.45:
            kata = rng.choice(SISIPAN)
            i = rng.randrange(len(t) + 1)
            sambung = rng.choice([" ", "", " ", "\n", ", "])
            t = t[:i] + sambung + kata + sambung + t[i:]
        elif jenis < 0.75:  # buang spasi: kata menempel
            pos = [i for i, c in enumerate(t) if c == " "]
            for i in sorted(rng.sample(pos, min(len(pos), rng.randint(1, 4))), reverse=True):
                t = t[:i] + t[i + 1:]
        elif jenis < 0.85:
            t = t.upper() if rng.random() < 0.3 else t.replace("Anda", rng.choice(["anda", "Bapak/Ibu", "Bapak/Ibunda"]))
        else:
            t = t[: rng.randint(0, len(t))]
    return t


def main() -> int:
    rekam_fungsi()
    import uji_llm  # memuat data contoh dan uji
    with contextlib.redirect_stdout(io.StringIO()):
        hasil_uji = uji_llm.main()
    if hasil_uji:
        print("uji_llm.py gagal; korpus tidak ditulis")
        return 1
    rng = random.Random(2026)

    # template untuk peserta contoh: tiap rute dan tiap saran, termasuk tunggakan 0
    T = uji_llm.T
    contoh = []
    for rute in ["verifikasi_pola_reaktivasi", "rujuk_cek_kelayakan_PBI", "pengingat_autodebet_REHAB",
                 "nonaktif_lama_tanpa_sinyal", "tanpa_tindakan"]:
        d = T[T["rute"] == rute]
        contoh += [r for _, r in d.sample(min(30, len(d)), random_state=7).iterrows()]
    contoh += [r for _, r in T[T["tunggakan_bulan"] == 0].sample(15, random_state=8).iterrows()]
    for s in ["pengingat_H-5_dan_tawaran_autodebet", "pengingat_saldo_autodebet", "cek_kelayakan_PBI"]:
        d = T[T["ew_saran"] == s]
        contoh += [r for _, r in d.sample(min(20, len(d)), random_state=9).iterrows()]
    templat = []
    for r in contoh:
        p = r.to_dict()
        p["alasan_rapi"] = p["alasan"]  # uji_llm memakai alasan apa adanya
        for t in sorted({p["rute"], "peringatan_dini"}):
            d = tpl.susun(p, t)
            templat.append(dict(p=peserta_json(p), tindakan=t, draf=d))
            if not d or d[0]["jenis"] != "pesan_peserta":
                continue
            # aturan dan perapian pada variasi template
            kode = llm._kode_aturan(t, p.get("ew_saran"))
            dasar = d[0]["isi"].replace(str(p["id_peserta"]), "{ID}")
            nominal = llm._nominal(p)
            for _ in range(10):
                v = mutasi(rng, dasar)
                llm.periksa_pesan_peserta(v, kode_aturan=kode, bulan=int(p["tunggakan_bulan"]), nominal=nominal,
                                          opsi_boleh=llm.opsi_dalam(d[0]["isi"]))
                llm.rapikan_spasi(v)
                llm.periksa_ringkasan(v[: rng.randint(0, 450)])
                llm.bersihkan_karakter(v)
            llm.periksa_pesan_peserta(dasar, kode_aturan=kode, bulan=int(p["tunggakan_bulan"]), nominal=nominal)
    for t in uji_llm.DRAF_ASLI_RAPI:
        llm.rapikan_spasi(t)

    sistem = {k: llm.SISTEM.format(
        wajib=" / ".join(" atau ".join(f'"{x}"' for x in g) for g in llm.WAJIB_SEBUT.get(k, [llm.ISTILAH_BOLEH])),
        dilarang=llm.CATATAN_TANPA_OPSI_BAYAR if k in llm.TANPA_OPSI_BAYAR else "",
        ringkasan=llm.CATATAN_RINGKASAN_PBI if k in llm.RINGKASAN_WAJIB else "")
        for k in list(llm.WAJIB_SEBUT) + ["verifikasi_pola_reaktivasi", "lain"]}

    urai = []
    for mentah in ['{"jalur": "a", "pesan_peserta": "b", "ringkasan_petugas": "c"}',
                   '```json\n{"jalur": "a", "pesan_peserta": "b", "ringkasan_petugas": "c"}\n```',
                   '```JSON {"jalur": "a", "pesan_peserta": "b", "ringkasan_petugas": "c"}```',
                   'Berikut: {"jalur": "a", "pesan_peserta": "b", "ringkasan_petugas": "c"} selesai',
                   '{"jalur": "a", "pesan_peserta": 1, "ringkasan_petugas": "c"}', "tanpa json", "{rusak}", "",
                   '{"jalur": "a", "pesan_peserta": "b"}', '```\n{"jalur": "x", "pesan_peserta": "y", '
                   '"ringkasan_petugas": "z"}\n```', "```json```"]:
        try:
            urai.append(dict(mentah=mentah, hasil=llm._urai(mentah)))
        except llm.AIGagal as e:
            urai.append(dict(mentah=mentah, galat=e.kode, rinci=e.rinci))

    korpus = dict(REKAM, templat=templat, sistem=sistem, urai=urai)
    KELUAR.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(KELUAR, "wt", encoding="utf-8") as f:
        json.dump(korpus, f, ensure_ascii=False)
    print({k: len(v) for k, v in korpus.items()}, f"{KELUAR.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
