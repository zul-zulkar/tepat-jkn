"""Draf pesan dari template. Ini juga jalur cadangan lapisan AI (llm.py, Z09).

Aturan yang dijaga (sama untuk versi AI nanti):
- Pesan tidak pernah mengubah rute. Rute datang dari aturan triase / model peringatan dini.
- Tanpa kata "curang", tanpa ancaman, tanpa menyebut skor.
- Rute verifikasi TIDAK menghasilkan pesan ke peserta, hanya catatan untuk petugas.
- Tagihan per KK belum dimodelkan; nominal di sini per peserta.

Keluaran: list of dict(sumber, jenis, judul, isi). jenis = "pesan_peserta" | "catatan_petugas".
"""
from __future__ import annotations


def _angka(x) -> str:
    return f"{round(float(x)):,}".replace(",", ".")


def _rp(x) -> str:
    return "Rp" + _angka(x)


INFO = "Informasi lebih lanjut: aplikasi Mobile JKN atau BPJS Kesehatan Care Center 165."
PEMBUKA = "Yth. peserta JKN (nomor peserta {id}),"


def _triase(p: dict) -> dict | None:
    rute, n, pid = p["rute"], int(p["tunggakan_bulan"]), p["id_peserta"]
    if rute == "verifikasi_pola_reaktivasi":
        return dict(
            sumber="Triase", jenis="catatan_petugas", judul="Catatan untuk petugas",
            isi=(f"Bukan untuk dikirim ke peserta.\n\n"
                 f"Pola yang terlihat: {p['alasan_rapi'].rstrip('.')}.\n\n"
                 "Sebelum menindaklanjuti:\n"
                 "1. Cocokkan tanggal aktif kembali dengan tanggal klaim di linimasa.\n"
                 "2. Cek penjelasan lain yang wajar: jatuh miskin karena sakit, pasien penyakit kronis, "
                 "pembayar musiman. Bila klaimnya rawat inap IGD di hari yang sama dengan pelunasan, "
                 "kemungkinan peserta melunasi karena darurat.\n"
                 "3. Bila peserta ternyata tidak mampu, ubah tindak lanjut menjadi rujukan cek kelayakan PBI.\n\n"
                 "Dalam komunikasi dengan peserta, jangan memakai kata yang menuduh."))
    if rute == "rujuk_cek_kelayakan_PBI":
        return dict(
            sumber="Triase", jenis="pesan_peserta", judul="Pesan ke peserta",
            isi=(PEMBUKA.format(id=pid) + "\n\n"
                 f"iuran JKN Anda tercatat belum dibayar selama {n} bulan. Keluarga Anda mungkin "
                 "memenuhi syarat sebagai peserta yang iurannya dibayar pemerintah (PBI).\n\n"
                 "Silakan datang ke kantor desa atau kelurahan, atau Dinas Sosial setempat, untuk "
                 "pengecekan data. Petugas BPJS Kesehatan dapat membantu proses rujukannya.\n\n" + INFO))
    if rute == "nonaktif_lama_tanpa_sinyal":
        return dict(
            sumber="Triase", jenis="pesan_peserta", judul="Pesan ke peserta",
            isi=(PEMBUKA.format(id=pid) + "\n\n"
                 f"kepesertaan JKN Anda sudah lama nonaktif, dengan tunggakan {n} bulan "
                 f"({_rp(p['tunggakan_rp'])}). Kami ingin membantu Anda kembali terlindungi.\n\n"
                 "Bila iuran terasa berat, Anda bisa mengajukan cicilan tunggakan lewat program REHAB 3.0, "
                 "atau menanyakan kemungkinan bantuan iuran (PBI) di kantor desa atau kelurahan.\n\n" + INFO))
    if rute == "pengingat_autodebet_REHAB":
        if n > 0:
            isi = (PEMBUKA.format(id=pid) + "\n\n"
                   f"iuran JKN Anda tercatat belum dibayar selama {n} bulan ({_rp(p['tunggakan_rp'])}). "
                   "Selama iuran belum dibayar, kartu JKN belum bisa dipakai untuk berobat.\n\n"
                   "Pilihan yang bisa Anda ambil:\n"
                   "- melunasi lewat Mobile JKN, bank, atau minimarket;\n"
                   "- mengajukan cicilan tunggakan lewat program REHAB 3.0;\n"
                   "- mendaftarkan autodebet agar iuran terbayar otomatis tiap bulan.\n\n" + INFO)
        else:
            isi = (PEMBUKA.format(id=pid) + "\n\n"
                   "terima kasih, iuran JKN Anda saat ini sudah lunas. Catatan kami menunjukkan iuran "
                   "beberapa kali terlambat sehingga kepesertaan sempat nonaktif.\n\n"
                   f"Agar tidak terulang, daftarkan autodebet lewat Mobile JKN atau bank Anda. Iuran "
                   f"{_rp(p['iuran_bulanan'])} per bulan dibayar paling lambat tanggal 10.\n\n" + INFO)
        return dict(sumber="Triase", jenis="pesan_peserta", judul="Pesan ke peserta", isi=isi)
    return None


def _ew(p: dict) -> dict | None:
    s, pid, iuran = p.get("ew_saran"), p["id_peserta"], _rp(p["iuran_bulanan"])
    if s == "pengingat_H-5_dan_tawaran_autodebet":
        isi = ("iuran JKN bulan depan jatuh tempo tanggal 10. Agar tidak terlewat, Anda bisa "
               f"mendaftarkan autodebet lewat Mobile JKN atau bank Anda, sehingga iuran {iuran} "
               "terbayar otomatis setiap bulan.\n\nTerima kasih sudah menjaga kepesertaan tetap aktif.")
    elif s == "pengingat_saldo_autodebet":
        isi = (f"iuran JKN Anda dibayar lewat autodebet. Pastikan saldo rekening cukup ({iuran}) "
               "sebelum tanggal 10 agar pembayaran tidak gagal dan kepesertaan tetap aktif.")
    elif s == "cek_kelayakan_PBI":
        isi = ("bila iuran mulai terasa berat, keluarga Anda mungkin memenuhi syarat sebagai peserta "
               "yang iurannya dibayar pemerintah (PBI). Silakan cek ke kantor desa atau kelurahan, "
               "atau Dinas Sosial setempat.")
    else:
        return None
    return dict(sumber="Berisiko menunggak", jenis="pesan_peserta", judul="Pesan pencegahan",
                isi=PEMBUKA.format(id=pid) + "\n\n" + isi + "\n\n" + INFO)


def susun(p: dict, tindakan: str) -> list[dict]:
    """Draf untuk tindakan utama peserta saja (satu peserta, satu tindakan; lihat tepat_ui.PRIORITAS).
    tindakan = kode rute triase atau "peringatan_dini"."""
    if tindakan == "peringatan_dini":
        d = _ew(p)
    elif tindakan == p["rute"]:
        d = _triase(p)
    else:
        d = None
    return [d] if d else []
