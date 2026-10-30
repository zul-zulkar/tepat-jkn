"""Lapisan AI untuk draf pesan (Z09). AI hanya menulis ulang kata-katanya; petugas yang memutuskan.

Aturan yang dijaga KODE ini, bukan cuma permintaan di prompt (jawaban AI yang melanggar dibuang,
lalu template dipakai):
- Jalur tidak pernah berubah. Jalur datang dari aturan triase / model peringatan dini; AI hanya
  diminta menyalin kodenya, dan jawaban dibuang bila beda. Fungsi ini tidak menulis ke data peserta.
- Tanpa kata "curang" atau tuduhan, tanpa ancaman atau tekanan.
- Pesan harus menyebut opsi yang sesuai jalur (REHAB 3.0, autodebet, atau cek PBI). "REHAB" saja
  tanpa "3.0" ditolak.
- Angka di pesan hanya yang ada di data peserta (jumlah bulan, nominal), ditambah 165 (Care Center).
- Tanpa skor, persen, atau istilah internal di pesan ke peserta.
- AI tidak pernah menerima nomor peserta; pesan memakai {ID} yang diganti di sini.
- Rute verifikasi tidak menghasilkan pesan ke peserta, jadi AI tidak dipanggil untuk rute itu.

Cadangan: kunci kosong, API mati, timeout, JSON rusak, pelanggaran aturan, atau saklar TEPAT_AI=off
=> pesan dari pesan_template.py. Fungsi susun() tidak pernah melempar galat.

Penyedia: Anthropic (Messages API) atau Google Gemini (generateContent, ada tier gratis). Semua aturan
di atas sama untuk keduanya karena dijaga di sini, bukan oleh penyedia.

Pengaturan lewat lingkungan (di Streamlit Cloud: menu Secrets):
  GEMINI_API_KEY           kunci Gemini (GOOGLE_API_KEY juga dibaca; GEMINI_API_KEY didahulukan)
  ANTHROPIC_API_KEY        kunci Anthropic
  TEPAT_LLM_PROVIDER       anthropic | gemini. Kosong = otomatis: Anthropic bila kuncinya ada, selain itu
                           Gemini. Tanpa kunci apa pun, AI tidak dipakai (template).
  TEPAT_AI=off             saklar mati (juga: 0, false, mati)
  TEPAT_LLM_MODEL          bawaan: MODEL_BAWAAN (Anthropic) atau MODEL_GEMINI. Bila diisi, pastikan cocok
                           dengan penyedia yang dipilih.
  ANTHROPIC_BASE_URL / GEMINI_BASE_URL   alamat dasar (untuk uji)
  TEPAT_AI_TIMEOUT         batas tunggu per panggilan dalam detik (1-120), bawaan BATAS_WAKTU_DETIK
  TEPAT_AI_BATAS_HARIAN    batas panggilan per hari per proses, bawaan 300

Modul ini sengaja tidak mengimpor streamlit, pandas, atau paket pihak ketiga lain.
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import pesan_template as tpl

MODEL_BAWAAN = "claude-haiku-5-5"                  # Anthropic
URL_BAWAAN = "https://api.anthropic.com"
# Dipilih dari uji panggilan nyata (29 Okt 2026, tier gratis, jalur penuh lewat susun()):
#   gemini-3.1-flash-lite  6/6 sukses; 2,7-6,7 dtk, kecuali panggilan pertama tiap sesi ±25-31 dtk
#   gemini-3.5-flash-lite  5/5 sukses tapi 21-56 dtk
#   gemini-3.8-flash       sering 503 "high demand" atau menggantung
MODEL_GEMINI = "gemini-3.1-flash-lite"
URL_GEMINI = "https://generativelanguage.googleapis.com"
PENYEDIA = ("anthropic", "gemini")                 # urutan = prioritas pemilihan otomatis
BATAS_WAKTU_DETIK = 45          # panggilan pertama model bisa ±31 dtk (terukur); 12 dan 20 dtk terbukti terlalu ketat
COBA_ULANG = 1                  # coba ulang khusus galat sementara di sisi server (503/529)
JEDA_ULANG_DETIK = 1.2
KODE_SEMENTARA = {503, 529}
BATAS_HARIAN_BAWAAN = 300
MIN_PANJANG, MAKS_PANJANG = 60, 1000
MAKS_RINGKASAN = 400

Klien = Callable[[str, str], str]  # (instruksi_sistem, masukan_pengguna) -> teks mentah dari model


class AIGagal(Exception):
    """kode: kunci pada PESAN_CADANGAN; rinci: keterangan teknis tanpa data peserta."""

    def __init__(self, kode: str, rinci: str = ""):
        super().__init__(kode, rinci)
        self.kode, self.rinci = kode, rinci


PESAN_CADANGAN = {
    "dimatikan": "AI dimatikan",
    "tanpa_kunci": "kunci API belum diisi",
    "penyedia_salah": "pengaturan penyedia AI tidak dikenal",
    "batas_harian": "batas panggilan harian tercapai",
    "kuota": "kuota API terlampaui, coba lagi sebentar",
    "api_error": "API tidak bisa dihubungi",
    "timeout": "API terlalu lama menjawab",
    "respons_kosong": "AI tidak memberi jawaban",
    "json_rusak": "jawaban AI bukan JSON yang valid",
    "jalur_berubah": "jawaban AI mengubah jalur",
    "melanggar_aturan": "jawaban AI melanggar aturan pesan",
    "kesalahan_tak_terduga": "galat tak terduga",
    "tanpa_pesan": "tidak ada pesan bulan ini",
    "tanpa_pesan_peserta": "rute ini tidak mengirim pesan ke peserta",
}


@dataclass
class Hasil:
    jalur: str                       # selalu sama dengan tindakan masukan
    draf: list[dict]                 # bentuk sama dengan pesan_template.susun: sumber, jenis, judul, isi
    status: str = "template"         # "ai" | "template"
    cadangan: str = ""               # kode PESAN_CADANGAN bila status "template"
    rinci: str = ""                  # kode pelanggaran, mis. "ancaman,angka_asing"; atau "ringkasan_dibuang:..." (status ai)
    ringkasan_petugas: str = ""      # hanya bila status "ai"
    model: str = ""
    penyedia: str = ""               # "anthropic" | "gemini" bila status "ai"
    dirapikan: int = 0               # jumlah perbaikan spasi otomatis pada pesan AI (lihat rapikan_spasi)

    @property
    def keterangan(self) -> str:
        if self.status == "ai":
            nama = f" ({self.model})" if self.model else ""
            rapi = f" Spasi dirapikan otomatis di {self.dirapikan} tempat." if self.dirapikan else ""
            return f"Disusun AI{nama} dari template. Rute tidak berubah; sunting sebelum dikirim.{rapi}"
        alasan = PESAN_CADANGAN.get(self.cadangan, self.cadangan)
        return f"Memakai template ({alasan})." if alasan else "Memakai template."


# ----------------------------------------------------------------------------------------------
# Pengaturan dan klien

def _ambil(nama: str) -> str:
    v = os.environ.get(nama, "").strip()
    if v:
        return v
    try:  # Streamlit Cloud: Secrets; diimpor malas supaya modul ini tetap ringan dan bisa diuji
        import streamlit as st
        return str(st.secrets.get(nama, "")).strip()
    except Exception:
        return ""


def ai_dimatikan() -> bool:
    return _ambil("TEPAT_AI").lower() in {"off", "0", "false", "mati", "no"}


_NAMA_KUNCI = {"anthropic": ("ANTHROPIC_API_KEY",), "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY")}


def _kunci_penyedia(nama: str) -> str:
    for v in _NAMA_KUNCI[nama]:
        k = _ambil(v)
        if k:
            return k
    return ""


def pilih_penyedia() -> tuple[str, str]:
    """(nama penyedia, kunci). Melempar AIGagal: dimatikan | penyedia_salah | tanpa_kunci."""
    if ai_dimatikan():
        raise AIGagal("dimatikan")
    pilihan = _ambil("TEPAT_LLM_PROVIDER").lower()
    if pilihan:
        if pilihan not in PENYEDIA:
            raise AIGagal("penyedia_salah", pilihan[:20])
        kunci = _kunci_penyedia(pilihan)
        if not kunci:
            raise AIGagal("tanpa_kunci", pilihan)
        return pilihan, kunci
    for nama in PENYEDIA:  # otomatis: Anthropic dulu (perilaku awal), lalu Gemini
        kunci = _kunci_penyedia(nama)
        if kunci:
            return nama, kunci
    raise AIGagal("tanpa_kunci")


def ai_tersedia() -> tuple[bool, str]:
    """(bisa dipakai, kode alasan bila tidak). Tidak memanggil jaringan."""
    try:
        pilih_penyedia()
        return True, ""
    except AIGagal as e:
        return False, e.kode


_pemakaian = {"tgl": None, "n": 0}


def _ambil_jatah() -> None:
    hari = date.today()
    if _pemakaian["tgl"] != hari:
        _pemakaian.update(tgl=hari, n=0)
    try:
        batas = int(_ambil("TEPAT_AI_BATAS_HARIAN") or BATAS_HARIAN_BAWAAN)
    except ValueError:
        batas = BATAS_HARIAN_BAWAAN
    if _pemakaian["n"] >= batas:
        raise AIGagal("batas_harian", f"{batas} panggilan")
    _pemakaian["n"] += 1


def _batas_waktu() -> float:
    try:
        v = float(_ambil("TEPAT_AI_TIMEOUT") or BATAS_WAKTU_DETIK)
    except ValueError:
        v = BATAS_WAKTU_DETIK
    return min(max(v, 1.0), 120.0)


batas_waktu = _batas_waktu  # nama publik: halaman memakainya untuk teks tunggu yang jujur


def _kirim(req: urllib.request.Request, batas_waktu: float) -> dict:
    """Satu tempat untuk HTTP dan pemetaan galat, dipakai semua penyedia. Pesan galat tidak pernah
    memuat alamat, header, atau kunci. Galat sementara di sisi server (503/529) dicoba ulang COBA_ULANG kali
    setelah jeda, sesuai saran dokumentasi; 429 dan galat klien (4xx) tidak dicoba ulang."""
    for percobaan in range(COBA_ULANG + 1):
        try:
            with urllib.request.urlopen(req, timeout=batas_waktu) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code in KODE_SEMENTARA and percobaan < COBA_ULANG:
                time.sleep(JEDA_ULANG_DETIK)
                continue
            rinci = f"HTTP {e.code}" + (" (sudah dicoba ulang)" if percobaan else "")
            raise AIGagal("kuota" if e.code == 429 else "api_error", rinci) from None
        except (socket.timeout, TimeoutError):
            raise AIGagal("timeout", f"{batas_waktu:g} dtk") from None
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise AIGagal("timeout", f"{batas_waktu:g} dtk") from None
            raise AIGagal("api_error", "tidak terhubung") from None
        except (OSError, ValueError):
            raise AIGagal("api_error", "respons tidak terbaca") from None
    if not isinstance(data, dict):
        raise AIGagal("api_error", "respons tidak terbaca")
    return data


def klien_anthropic(kunci: str, model: str, url: str = URL_BAWAAN,
                    batas_waktu: float = BATAS_WAKTU_DETIK) -> Klien:
    """Klien HTTP tipis ke Messages API."""
    alamat = url.rstrip("/") + "/v1/messages"

    def panggil(sistem: str, masukan: str) -> str:
        _ambil_jatah()
        badan = json.dumps({"model": model, "max_tokens": 900, "system": sistem,
                            "messages": [{"role": "user", "content": masukan}]}).encode("utf-8")
        req = urllib.request.Request(alamat, data=badan, method="POST", headers={
            "content-type": "application/json", "x-api-key": kunci, "anthropic-version": "2023-06-01"})
        data = _kirim(req, batas_waktu)
        teks = "".join(b.get("text", "") for b in data.get("content", []) if isinstance(b, dict)
                       and b.get("type") == "text")
        if not teks.strip():
            raise AIGagal("respons_kosong", str(data.get("stop_reason") or "")[:40])
        return teks

    return panggil


def klien_gemini(kunci: str, model: str, url: str = URL_GEMINI,
                 batas_waktu: float = BATAS_WAKTU_DETIK) -> Klien:
    """Klien HTTP tipis ke Gemini generateContent (v1beta). Kunci lewat header, bukan alamat.

    Hanya field yang tertulis di dokumentasi resmi: system_instruction, contents (role user), dan
    generationConfig.maxOutputTokens. Tanpa temperature (model Gemini baru mengabaikannya) dan tanpa
    pengaturan mode JSON (nama field-nya beda antar halaman dokumentasi): JSON dijaga oleh prompt, lalu
    _urai() dan validator. maxOutputTokens dibuat longgar karena model bisa 'berpikir' dulu."""
    if not re.fullmatch(r"[\w.\-]+", model):
        raise AIGagal("penyedia_salah", "nama model tidak valid")
    alamat = f"{url.rstrip('/')}/v1beta/models/{model}:generateContent"

    def panggil(sistem: str, masukan: str) -> str:
        _ambil_jatah()
        badan = json.dumps({"system_instruction": {"parts": [{"text": sistem}]},
                            "contents": [{"role": "user", "parts": [{"text": masukan}]}],
                            "generationConfig": {"maxOutputTokens": 2048}}).encode("utf-8")
        req = urllib.request.Request(alamat, data=badan, method="POST", headers={
            "content-type": "application/json", "x-goog-api-key": kunci})
        data = _kirim(req, batas_waktu)
        kandidat = [c for c in (data.get("candidates") or []) if isinstance(c, dict)]
        bagian = ((kandidat[0].get("content") or {}).get("parts") or []) if kandidat else []
        teks = "".join(b.get("text", "") for b in bagian if isinstance(b, dict) and not b.get("thought"))
        if not teks.strip():
            sebab = ((data.get("promptFeedback") or {}).get("blockReason")
                     or (kandidat[0].get("finishReason") if kandidat else "") or "")
            raise AIGagal("respons_kosong", str(sebab)[:40])
        return teks

    return panggil


def klien_dari_lingkungan() -> tuple[Klien, str, str]:
    """(klien, penyedia, model) dari kunci dan pengaturan lingkungan. Melempar AIGagal bila tidak bisa."""
    nama, kunci = pilih_penyedia()
    batas = _batas_waktu()
    if nama == "gemini":
        model = _ambil("TEPAT_LLM_MODEL") or MODEL_GEMINI
        return klien_gemini(kunci, model, _ambil("GEMINI_BASE_URL") or URL_GEMINI, batas), nama, model
    model = _ambil("TEPAT_LLM_MODEL") or MODEL_BAWAAN
    return klien_anthropic(kunci, model, _ambil("ANTHROPIC_BASE_URL") or URL_BAWAAN, batas), nama, model


# ----------------------------------------------------------------------------------------------
# Aturan pesan

# Opsi yang sesuai jalur: tiap grup harus terwakili oleh sedikitnya satu istilah.
WAJIB_SEBUT: dict[str, list[list[str]]] = {
    "rujuk_cek_kelayakan_PBI": [["PBI"]],
    "nonaktif_lama_tanpa_sinyal": [["REHAB 3.0", "PBI"]],
    "pengingat_autodebet_REHAB": [["REHAB 3.0", "autodebet"]],
    "peringatan_dini:pengingat_H-5_dan_tawaran_autodebet": [["autodebet"]],
    "peringatan_dini:pengingat_saldo_autodebet": [["autodebet"]],
    "peringatan_dini:cek_kelayakan_PBI": [["PBI"]],
}
ISTILAH_BOLEH = ["REHAB 3.0", "autodebet", "PBI"]

# Jalur yang tidak boleh mendorong peserta membayar: peserta diarahkan ke pengecekan PBI. Temuan uji model
# asli 29 Okt: 3 dari 3 draf jalur PBI (dua model, dua run) menyelipkan autodebet/REHAB. Dijaga di dua
# tempat: prompt (SISTEM {dilarang}) agar model patuh, dan validator agar pelanggaran ditolak.
TANPA_OPSI_BAYAR = frozenset({"rujuk_cek_kelayakan_PBI"})
CATATAN_TANPA_OPSI_BAYAR = (" Peserta ini diarahkan ke pengecekan PBI dan tidak sedang diminta membayar: "
                            "jangan menyebut autodebet, REHAB 3.0, cicilan, atau angsuran.")
_OPSI_BAYAR = re.compile(r"auto[\s-]?debet|rehab|\w*cicil\w*|\w*angsur\w*", re.I)

# Ringkasan untuk petugas pada jalur PBI harus menyebut tindak lanjutnya sebagai "cek kelayakan PBI". Temuan uji
# aplikasi publik 30 Okt: model menulis "mengecek kepesertaan PBI", yang artinya lain (memeriksa apakah peserta
# sudah terdaftar PBI). Ringkasan tidak memuat keputusan keselamatan, jadi pelanggaran aturan ini tidak menolak
# seluruh draf: ringkasannya dibuang, pesan ke peserta tetap dipakai. Teks AI tidak ditulis ulang.
_KELAYAKAN_PBI = re.compile(r"\bkelayakan\s+PBI\b", re.I)
RINGKASAN_WAJIB = {"rujuk_cek_kelayakan_PBI": _KELAYAKAN_PBI, "peringatan_dini:cek_kelayakan_PBI": _KELAYAKAN_PBI}
CATATAN_RINGKASAN_PBI = ('\n10. Di "ringkasan_petugas" sebut tindak lanjut peserta ini persis "cek kelayakan PBI". '
                         'Jangan menulis "kepesertaan PBI": artinya lain.')

# Opsi yang boleh disebut pesan AI = opsi yang disebut draf template jalur itu untuk peserta itu. Template sudah
# memuat aturan kelayakan (REHAB 3.0 hanya bila ada tunggakan, autodebet tidak untuk peserta nonaktif, PBI hanya
# untuk jalur yang relevan), jadi AI tidak perlu mengulang aturannya. Temuan uji model asli 29 Okt: draf jalur
# nonaktif menambah "autodebet" yang tidak ada di template. Satu aturan umum menggantikan daftar larangan per jalur.
_POLA_OPSI = {
    "REHAB 3.0": re.compile(r"\brehab(?![a-z])", re.I),  # bukan "rehabilitasi"
    "autodebet": re.compile(r"auto[\s-]?debet", re.I),
    "PBI": re.compile(r"\bPBI\b", re.I),  # larangan: lebih peka daripada syarat wajib (\bPBI\b, huruf besar)
}


def opsi_dalam(teks: str) -> frozenset[str]:
    """Opsi (REHAB 3.0 / autodebet / PBI) yang disebut sebuah teks."""
    t = _norm(teks)
    return frozenset(k for k, pola in _POLA_OPSI.items() if pola.search(t))

_CURANG = re.compile(r"curang|fraud", re.I)
_TUDUHAN = re.compile(
    r"\b(sengaja|pura-?pura|bohong|membohongi|menipu|penipu\w*|manipulasi|memanipulasi|melanggar|"
    r"pelanggaran|menyalahgunakan|penyalahgunaan|mengakali|akal-?akalan|menghindar\w*|mangkir)\b", re.I)
_ANCAMAN = re.compile(  # \w* di belakang: tangkap imbuhan (konsekuensinya, dendanya, sanksinya)
    r"\b(?:denda|sanksi|hukuman|dihukum|pidana|dipidana|penjara|dipenjara|polisi|kepolisian|"
    r"(?:proses|jalur|tindakan|akibat) hukum|dilaporkan|melaporkan anda|ditindak|tindakan tegas|tindak tegas|"
    r"diblokir|dicabut|pencabutan|dibekukan|diputus|kehilangan hak|konsekuensi|dikenai|dikenakan|"
    r"ultimatum|peringatan terakhir|kesempatan terakhir|jangan sampai|awas)\w*", re.I)
_INTERNAL = re.compile(
    r"\b(skor|score|peluang|probabilitas|risiko|berisiko|peringatan dini|triase|rute|jalur|model|algoritma|"
    r"prediksi|diprediksi|kecerdasan buatan|desil|dtsen|reaktivasi|verifikasi|klaim)\b", re.I)
# Penguat kepastian: draf template sengaja berhati-hati ("mungkin memenuhi syarat"). Temuan uji model asli 30 Okt:
# draf PBI menjadi "besar kemungkinan Anda memenuhi syarat" dan lolos semua aturan. Hanya frasa yang benar-benar
# menaikkan kepastian; "pastikan"/"memastikan" (dipakai template: "Pastikan saldo rekening cukup") dan "Jaminan
# Kesehatan Nasional" tidak kena. Pelemahan hedge tanpa kata di daftar ini ("mungkin" dibuang) tidak terdeteksi.
_KEPASTIAN = re.compile(
    r"\b(?:(?:sudah|hampir)\s+pasti|pasti|dipastikan|(?:besar|tinggi)\s+kemungkinan|kemungkinan\s+(?:besar|tinggi)|"
    r"(?:sangat|amat)\s+mungkin)\b", re.I)
_AI_KAPITAL = re.compile(r"\bAI\b")
_PERSEN = re.compile(r"\d\s*%|\bpersen\b", re.I)
_TAUTAN = re.compile(r"https?://|www\.|@\w|\b[\w-]+\.(?:com|id|co|net|org)\b|(?:\+62|\b0)8\d{6,}", re.I)
_REHAB_LAMA = re.compile(r"REHAB(?!\s?3\.0)")
_ANGKA = re.compile(r"\d+(?:[.,]\d+)*")
_RUPIAH = re.compile(r"Rp\.?\s*(\d+(?:[.,]\d+)*)", re.I)
_BULAN = re.compile(r"(\d+)\s+bulan\b", re.I)
_SATUAN_UANG = re.compile(r"\b\d[\d.,]*\s*(?:ribu|rb|juta|jt|rupiah)\b", re.I)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).replace(" ", " ")
    s = re.sub(r"[​-‏⁠﻿]", "", s)
    return s


_TAK_TERLIHAT = re.compile("[\u00ad\u200b-\u200f\u2060\ufeff]")  # sama dengan yang dibuang _norm, ditambah soft hyphen


def bersihkan_karakter(teks: str) -> str:
    """Buang karakter tak terlihat (zero-width, soft hyphen, BOM) dan ganti spasi non-pecah dengan spasi biasa.
    Validator menilai teks yang sudah dinormalisasi (_norm); tanpa ini petugas menerima teks berbeda dari yang
    dinilai, dan karakter tak terlihat di antara dua kata membuat kata tampak menempel serta lolos perapian spasi."""
    return _TAK_TERLIHAT.sub("", teks.replace("\u00a0", " ").replace("\u202f", " "))


def _rapat(s: str) -> str:
    """Hanya huruf kecil tanpa aksen, untuk menangkap 'c u r a n g' atau 'c.u.r.a.n.g'."""
    d = unicodedata.normalize("NFKD", _norm(s))
    return re.sub(r"[^a-z]", "", "".join(c for c in d if not unicodedata.combining(c)).lower())


def _int(angka: str) -> int:
    return int(re.sub(r"[.,]", "", angka))


def _kode_aturan(tindakan: str, saran: str | None) -> str:
    return f"peringatan_dini:{saran}" if tindakan == "peringatan_dini" else tindakan


def periksa_kata(teks: str) -> list[str]:
    """Kata terlarang untuk semua teks buatan AI (pesan dan ringkasan petugas)."""
    t, hasil = _norm(teks), []
    if _CURANG.search(t) or "curang" in _rapat(t):
        hasil.append("curang")
    if _TUDUHAN.search(t):
        hasil.append("tuduhan")
    if _ANCAMAN.search(t) or any(k in _rapat(t) for k in ("sanksi", "pidana", "penjara", "dilaporkan")):
        hasil.append("ancaman")
    return hasil


def periksa_pesan_peserta(teks: str, *, kode_aturan: str, bulan: int, nominal: list[int],
                          opsi_boleh: frozenset[str] | None = None) -> list[str]:
    """Daftar pelanggaran (kosong = lolos) untuk pesan ke peserta. teks masih berisi {ID}.

    opsi_boleh: opsi yang disebut template; bila diberikan, opsi lain di teks ditolak. None = tidak diperiksa."""
    t = _norm(teks)
    p = list(periksa_kata(t))
    if not (MIN_PANJANG <= len(t.strip()) <= MAKS_PANJANG):
        p.append("panjang")
    if _INTERNAL.search(t) or _AI_KAPITAL.search(t):
        p.append("istilah_internal")
    if _PERSEN.search(t):
        p.append("angka_persen")
    if _KEPASTIAN.search(t):
        p.append("klaim_pasti")
    if _TAUTAN.search(t):
        p.append("tautan_atau_kontak")
    if _REHAB_LAMA.search(t):
        p.append("rehab_tanpa_3.0")
    for grup in WAJIB_SEBUT.get(kode_aturan, []):
        if not any(re.search(r"\bPBI\b" if k == "PBI" else re.escape(k), t, 0 if k in ("PBI", "REHAB 3.0")
                             else re.I) for k in grup):
            p.append("tanpa_opsi:" + "/".join(grup))
    if kode_aturan in TANPA_OPSI_BAYAR and _OPSI_BAYAR.search(t):
        p.append("opsi_bayar_di_jalur_pbi")
    if opsi_boleh is not None:
        luar = opsi_dalam(t) - opsi_boleh
        if luar:
            p.append("opsi_di_luar_template:" + "/".join(sorted(luar)))
    # angka: hanya yang ada di data peserta, 165 (Care Center), tanggal 10 (jatuh tempo), 5 (H-5)
    sisa = t.replace("{ID}", " ").replace("REHAB 3.0", " ")
    boleh = {int(bulan), 165, 10, 5} | set(nominal)
    if _SATUAN_UANG.search(sisa):
        p.append("angka_asing")
    else:
        for m in _RUPIAH.finditer(sisa):
            if _int(m.group(1)) not in set(nominal):
                p.append("nominal_salah")
                break
        for m in _BULAN.finditer(sisa):
            if int(m.group(1)) != int(bulan):
                p.append("bulan_salah")
                break
        if any(_int(m.group(0)) not in boleh for m in _ANGKA.finditer(_RUPIAH.sub(" ", sisa))):
            p.append("angka_asing")
    if re.search(r"[{}]", sisa):
        p.append("penampung_sisa")
    return list(dict.fromkeys(p))


def periksa_ringkasan(teks: str) -> list[str]:
    p = periksa_kata(teks)
    if not teks.strip() or len(teks) > MAKS_RINGKASAN:
        p.append("panjang_ringkasan")
    return p


# ----------------------------------------------------------------------------------------------
# Perapian spasi
#
# Model kelas lite sering menghilangkan satu spasi: 7 dari 12 draf asli pada uji 29 Okt punya sedikitnya
# satu kata menempel ("layanankesehatan", "bulan,Anda", "programREHAB 3.0", "Bapak/Ibuuntuk"). Tanpa kamus
# bahasa Indonesia hanya dua jenis perbaikan yang cukup aman. (1) Pola yang tidak mungkin sah: tanda baca
# langsung disusul huruf, huruf kecil langsung disusul singkatan kapital, "Rp" dan {ID} menempel pada kata.
# (2) Kosakata tertutup domain pesan ini (kata fungsi dan kata inti pesan JKN): token panjang yang BUKAN
# anggota kosakata tetapi persis gabungan dua anggotanya dipisah. Tabel tujuh bentuk yang pernah dilihat
# terbukti tidak cukup: pada uji berikutnya ia menangkap 0 dari 2 kata menempel baru.
# Kata menempel di luar kosakata tidak dikenali; kotak sunting petugas tetap penjaganya. Hanya spasi yang
# ditambah, huruf tidak diubah, jadi aturan pesan dinilai pada teks yang sudah rapi.
# Kosakata sengaja tidak memuat kata yang bersama kata lain membentuk kata sah (mis. "dari" dan "pada",
# karena "daripada" sah). uji_llm.py menjaga itu: tak ada anggota yang gabungan dua anggota lain.

_KOSAKATA = frozenset("""
untuk dengan oleh atau dapat lebih lanjut yang agar bisa terus juga serta jika bila mohon silakan kami anda
ibu bapak mungkin perlu cukup masih sudah belum sedang saat total iuran tunggakan nominal jumlah bulan kartu
peserta program aplikasi layanan kesehatan kepesertaan pembayaran pelunasan melunasi melakukan mengajukan
mendaftarkan mencicil cicilan berkonsultasi menghubungi mengakses informasi bantuan kantor desa kelurahan
setempat pengecekan mengecek membantu terlindungi perlindungan kembali aktif nonaktif otomatis rutin berobat
minimarket bank autodebet pemerintah petugas tercatat dibayar dibayarkan terbayar menyarankan menanyakan
memanfaatkan memenuhi syarat kriteria rujukan proses data
""".split())
_TOKEN_PANJANG = re.compile(r"\b[A-Za-z]{8,}\b")
_POLA_SPASI = [  # (pola, pengganti); semuanya hanya menyisipkan spasi
    (re.compile(r"(?<=[a-z0-9])([.,;:!?])(?=[A-Z])"), r"\1 "),               # "Rp450.000.Selama", "bulan,Anda"
    (re.compile(r"(?<=[A-Za-z])([,;:])(?=[a-z])"), r"\1 "),                  # "bulan,anda"
    (re.compile(r"(?<=[a-z]{2})(?=[A-Z]{2,}\b)"), " "),                      # "programREHAB"
    (re.compile(r"\b(BPJS|JKN|PBI|NIK|KIS|REHAB)(?=[A-Z][a-z])"), r"\1 "),   # "BPJSKesehatan"
    (re.compile(r"(Bapak/Ibu)(?!nda|ku|mu|nya)(?=[a-z])"), r"\1 "),          # "Bapak/Ibumungkin"
    (re.compile(r"(?<=[a-z])(?=Rp\d)"), " "),                                # "tunggakanRp450.000"
    (re.compile(r"(?<=[A-Za-z0-9])(?=\{ID\})"), " "),                        # "nomor{ID}"
    (re.compile(r"(?<=\{ID\})(?=[A-Za-z])"), " "),                           # "{ID}iuran"
]


def _pisah_gabungan(t: str) -> str:
    """Token bukan anggota kosakata tetapi gabungan dua anggotanya: sisipkan satu spasi (huruf asli utuh)."""
    r = t.lower()
    if r in _KOSAKATA:
        return t
    for i in range(len(r) - 3, 2, -1):  # bagian pertama terpanjang dulu; tiap bagian sedikitnya 3 huruf
        if r[:i] in _KOSAKATA and r[i:] in _KOSAKATA:
            return t[:i] + " " + t[i:]
    return t


def rapikan_spasi(teks: str) -> tuple[str, int]:
    """(teks_rapi, jumlah_perbaikan). Idempoten; teks yang sudah rapi tidak berubah sama sekali."""
    n = 0

    def pisah(m: re.Match) -> str:
        nonlocal n
        hasil = _pisah_gabungan(m.group(0))
        n += hasil != m.group(0)
        return hasil

    teks = _TOKEN_PANJANG.sub(pisah, teks)
    for pola, ganti in _POLA_SPASI:
        teks, k = pola.subn(ganti, teks)
        n += k
    return teks, n


# ----------------------------------------------------------------------------------------------
# Prompt

SISTEM = """Kamu penyusun draf pesan WhatsApp untuk petugas BPJS Kesehatan. Petugas yang menyunting dan memutuskan \
mengirim; kamu hanya menulis draf.

Tugas: tulis ulang "draf_template" menjadi pesan WhatsApp yang sopan, hangat, dan jelas untuk peserta JKN \
mandiri. Isi dan fakta harus sama dengan template; yang boleh berubah hanya pilihan kata dan urutan kalimat. \
Ubah seminimal mungkin: pertahankan paragraf, daftar pilihan, dan sebagian besar kalimat template; yang diubah \
terutama sapaan dan kalimat penghubung agar terasa hangat.

Aturan keras. Jawaban yang melanggar dibuang otomatis oleh sistem:
1. Jalur sudah ditetapkan sistem dan tidak boleh kamu ubah. Salin nilai "jalur" apa adanya ke jawaban.
2. Jangan memakai kata "curang" atau tuduhan terselubung (sengaja, pura-pura, menghindar, melanggar). \
Peserta tidak sedang dituduh apa pun.
3. Jangan mengancam atau menekan: tanpa denda, sanksi, hukuman, pelaporan, pemblokiran, atau "kesempatan terakhir".
4. Sebut opsi hanya dengan nama persis ini: "REHAB 3.0" (tulis lengkap, bukan "REHAB"), "autodebet", "PBI". \
Pesan harus menyebut sedikitnya satu dari: {wajib}. \
Jangan menambah opsi yang tidak ada di draf_template.{dilarang}
5. Angka hanya yang ada di "fakta" (jumlah bulan, nominal Rupiah berformat Rp1.234.000) dan nomor 165. \
Jangan mengarang angka, tanggal, tautan, atau nomor telepon.
6. Jangan menyebut skor, persen, peluang, risiko, model, AI, DTSEN, atau istilah internal lain di pesan ke peserta. \
"skor" dan "alasan" hanya agar kamu paham konteks.
7. Tulis {{ID}} (persis, dengan kurung kurawal) bila ingin menyebut nomor peserta. Jangan menulis nomor sendiri.
8. Bahasa Indonesia baku yang ramah, tanpa emoji, tanpa markdown, paling banyak 700 karakter. Ejaan harus rapi: \
setiap kata dipisah satu spasi, jangan menggabungkan dua kata, dan beri spasi setelah titik dan koma.
9. Jangan menaikkan kepastian di atas draf_template. Bila template memakai "mungkin" atau "kemungkinan", \
pertahankan; jangan menulis "pasti", "dipastikan", "besar kemungkinan", atau "kemungkinan besar".{ringkasan}

Jawab HANYA dengan satu objek JSON tanpa teks lain, persis berbentuk:
{{"jalur": "<salin jalur>", "pesan_peserta": "<pesan untuk peserta>", \
"ringkasan_petugas": "<1-2 kalimat untuk petugas: mengapa peserta ini mendapat pesan ini; boleh menyebut skor>"}}"""


def _rp(x) -> str:
    return tpl._rp(x)


def _fakta(p: dict) -> dict:
    return {"tunggakan_bulan": int(p["tunggakan_bulan"]), "tunggakan_rp": _rp(p["tunggakan_rp"]),
            "iuran_bulanan": _rp(p["iuran_bulanan"]), "sudah_autodebet": bool(p.get("autodebet"))}


def _nominal(p: dict) -> list[int]:
    return [round(float(p["tunggakan_rp"])), round(float(p["iuran_bulanan"]))]


def bangun_masukan(p: dict, tindakan: str, draf_template: str) -> dict:
    """Satu-satunya data peserta yang meninggalkan sistem. Tanpa nomor peserta; jalur, skor, alasan
    seperti permintaan Z09, plus fakta angka supaya AI tidak perlu mengarang."""
    ew = tindakan == "peringatan_dini"
    skor = p.get("ew_skor") if ew else None
    alasan = p.get("ew_alasan") if ew else p.get("alasan_rapi") or p.get("alasan")
    masuk = {"jalur": tindakan,
             "skor": None if skor is None or skor != skor else round(float(skor), 3),
             "alasan": str(alasan or ""),
             "fakta": _fakta(p),
             "draf_template": draf_template.replace(str(p["id_peserta"]), "{ID}")}
    if ew:
        masuk["saran"] = p.get("ew_saran")
    return masuk


def _urai(mentah: str) -> dict:
    t = mentah.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise AIGagal("json_rusak", "tanpa objek JSON")
    try:
        d = json.loads(t[a:b + 1])
    except ValueError:
        raise AIGagal("json_rusak", "JSON tidak valid") from None
    if not isinstance(d, dict) or not all(isinstance(d.get(k), str) for k in ("jalur", "pesan_peserta",
                                                                              "ringkasan_petugas")):
        raise AIGagal("json_rusak", "kunci jalur/pesan_peserta/ringkasan_petugas tidak lengkap")
    return d


# ----------------------------------------------------------------------------------------------
# Titik masuk

def susun(p: dict, tindakan: str, *, klien: Klien | None = None, pakai_ai: bool = True) -> Hasil:
    """Draf untuk tindakan utama peserta. Selalu mengembalikan draf dari template bila AI tidak bisa
    dipakai atau jawabannya ditolak. Tidak melempar galat dan tidak mengubah p.

    klien: untuk uji; bila None dipakai klien dari lingkungan (kunci API)."""
    templat = tpl.susun(p, tindakan)
    hasil = Hasil(jalur=tindakan, draf=templat)
    if not templat:
        hasil.cadangan = "tanpa_pesan"
        return hasil
    if templat[0]["jenis"] != "pesan_peserta":
        hasil.cadangan = "tanpa_pesan_peserta"
        return hasil
    if not pakai_ai:
        hasil.cadangan = "dimatikan"
        return hasil
    try:
        model = penyedia = ""
        if klien is None:
            klien, penyedia, model = klien_dari_lingkungan()
        elif ai_dimatikan():
            raise AIGagal("dimatikan")
        saran = p.get("ew_saran") if tindakan == "peringatan_dini" else None
        kode = _kode_aturan(tindakan, saran)
        wajib = " / ".join(" atau ".join(f'"{k}"' for k in g) for g in WAJIB_SEBUT.get(kode, [ISTILAH_BOLEH]))
        masukan = bangun_masukan(p, tindakan, templat[0]["isi"])
        dilarang = CATATAN_TANPA_OPSI_BAYAR if kode in TANPA_OPSI_BAYAR else ""
        catatan = CATATAN_RINGKASAN_PBI if kode in RINGKASAN_WAJIB else ""
        mentah = klien(SISTEM.format(wajib=wajib, dilarang=dilarang, ringkasan=catatan),
                       json.dumps(masukan, ensure_ascii=False))
        d = _urai(mentah)
        if d["jalur"].strip() != tindakan:
            raise AIGagal("jalur_berubah", f"{d['jalur'][:40]!r}")
        pesan, dirapikan = rapikan_spasi(bersihkan_karakter(d["pesan_peserta"]))
        pelanggaran = periksa_pesan_peserta(pesan, kode_aturan=kode, bulan=int(p["tunggakan_bulan"]),
                                            nominal=_nominal(p), opsi_boleh=opsi_dalam(templat[0]["isi"]))
        pelanggaran += [x + "@ringkasan" for x in periksa_ringkasan(d["ringkasan_petugas"])]
        if pelanggaran:
            raise AIGagal("melanggar_aturan", ",".join(pelanggaran))
        isi = pesan.strip().replace("{ID}", str(p["id_peserta"]))
        hasil.draf = [dict(templat[0], isi=isi, judul="Pesan ke peserta (draf AI)")]
        hasil.status, hasil.model, hasil.penyedia, hasil.dirapikan = "ai", model, penyedia, dirapikan
        ringkasan = bersihkan_karakter(d["ringkasan_petugas"]).strip()
        if kode in RINGKASAN_WAJIB and not RINGKASAN_WAJIB[kode].search(ringkasan):
            ringkasan, hasil.rinci = "", "ringkasan_dibuang:tanpa_kelayakan_PBI"
        hasil.ringkasan_petugas = ringkasan
    except AIGagal as e:
        hasil.cadangan, hasil.rinci = e.kode, e.rinci
    except Exception as e:  # jaring terakhir: halaman petugas tidak boleh gagal karena AI
        hasil.cadangan, hasil.rinci = "kesalahan_tak_terduga", type(e).__name__
    return hasil
