"""Uji akun demo (Pusat/Cabang) dengan streamlit.testing.v1.AppTest. Jalankan: python uji_akun.py"""
import sys

from streamlit.testing.v1 import AppTest

import akun
import tepat_ui as ui

HASIL = []


def cek(nama: str, ok: bool, rinci: str = "") -> None:
    HASIL.append(ok)
    print(("LULUS " if ok else "GAGAL ") + nama + (f"  [{rinci}]" if rinci else ""))


def baru() -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=90)
    return at


def klik(at, label):
    [b for b in at.button if b.label == label][0].click().run()


def teks_semua(at) -> str:
    return " ".join(str(getattr(e, "value", "")) for e in at.markdown) + " " + " ".join(i.value for i in at.info) + " " + " ".join(c.value for c in at.caption)


T = ui.tabel_peserta()
A = akun.AKUN["cabang_a"]["wilayah"]
n_wil_a = int(T["kode_wilayah"].isin(A).sum())
utama_a = None

# (a) tanpa akun
at = baru().run()
cek("a. tanpa akun: tanpa exception", not at.exception)
cek("a. tombol Masuk ada, tombol Ganti akun tidak", any(b.label == "Masuk" for b in at.button)
    and not any(b.label == "Ganti akun" for b in at.button))
cek("a. radio akun bawaan Pusat", at.radio(key="pilih_akun").value == "pusat")

# (b) Pusat
klik(at, "Masuk")
cek("b. masuk Pusat", at.session_state["_akun"] == "pusat" and not at.exception)
for hal in ["halaman/daftar_kerja.py", "halaman/profil_peserta.py", "halaman/kebijakan.py",
            "halaman/keadilan.py"]:
    at.switch_page(hal).run()
    cek(f"b. Pusat {hal} tanpa exception", not at.exception, str([e.value for e in at.exception][:1]))
at.switch_page("halaman/daftar_kerja.py").run()
at.session_state["f_daftar"] = "ew"
at.run()
cek("b. slider k aktif untuk Pusat", not at.slider(key="f_k").disabled)
at.slider(key="f_k").set_value(8).run()
cek("b. Pusat ubah k=8", at.session_state["f_k"] == 8 and not at.exception)
at.slider(key="f_k").set_value(5).run()
at.session_state["f_daftar"] = "triase"
at.run()
ms = at.multiselect(key="f_wilayah")
cek("b. multiselect Pusat berisi 40 wilayah", len(ms.options) == 40, str(len(ms.options)))

# (c) Cabang A
at = baru().run()
at.radio(key="pilih_akun").set_value("cabang_a").run()
klik(at, "Masuk")
cek("c. masuk Cabang A", at.session_state["_akun"] == "cabang_a" and not at.exception)
at.switch_page("halaman/daftar_kerja.py").run()
cek("c. Daftar kerja tanpa exception", not at.exception)
cek("c. multiselect hanya wilayah cabang A", sorted(at.multiselect(key="f_wilayah").options) == sorted(A))
df = at.dataframe[0].value
# tabel triase: peserta wilayah A yang punya tindakan utama; bandingkan dengan hitungan independen
ew, _ = ui.daftar_ew(T[T["kode_wilayah"].isin(A)], A, 5)
Tw = T[T["kode_wilayah"].isin(A)]
ew_ids = set(ew["id_peserta"])
utama = ui.tindakan_utama(Tw["rute"], Tw["id_peserta"].isin(ew_ids))
n_triase = int(utama.isin(ui.RUTE_AKSI).sum())
cek("c. baris tabel triase = peserta wilayah A bertindakan triase", len(df) == n_triase, f"{len(df)} vs {n_triase}")
cek("c. semua baris tabel ber-Wilayah di cabang A", set(df["Wilayah"]) <= set(A))
html_alur = " ".join(str(getattr(e, "value", "")) for e in at.get("html"))
cek("c. flowchart memuat total peserta wilayah A", f"{n_wil_a:,}".replace(",", ".") in html_alur
    or str(n_wil_a) in html_alur, f"{n_wil_a} peserta")
at.session_state["f_daftar"] = "ew"
at.run()
cek("c. slider k disabled", at.slider(key="f_k").disabled)
cek("c. keterangan kapasitas Pusat", any("Kapasitas ditetapkan Kantor Pusat: 5%" in c.value for c in at.caption))
dfe = at.dataframe[0].value
n_ew_a = len(ew[ew["id_peserta"].isin(set(Tw.loc[utama == ui.PERINGATAN_DINI, "id_peserta"]))])
cek("c. daftar berisiko menunggak hanya wilayah A, jumlah cocok", set(dfe["Wilayah"]) <= set(A) and len(dfe) == n_ew_a,
    f"{len(dfe)} vs {n_ew_a}")
at.session_state["f_daftar"] = "triase"
at.run()
# pilih satu wilayah A dan satu non-A tidak tersedia; pilih W29 saja
at.multiselect(key="f_wilayah").set_value(["W29"]).run()
cek("c. filter W29 -> hanya W29", set(at.dataframe[0].value["Wilayah"]) == {"W29"} and not at.exception)
at.multiselect(key="f_wilayah").set_value([]).run()

# profil: P-005882 simpan setuju
at.switch_page("halaman/profil_peserta.py").run()
cek("c. Profil tanpa id tidak error", not at.exception)
at.text_input(key="cari_id").set_value("P-005882").run()
cek("c. Profil P-005882 terbuka", at.session_state["_pid_terakhir"] == "P-005882" if "_pid_terakhir" in at.session_state else False)
at.radio(key="kep_P-005882").set_value("setuju").run()
[b for b in at.button if b.label == "Simpan keputusan"][0].click().run()
rek = at.session_state["_keputusan"].get("P-005882")
cek("c. keputusan tersimpan dengan dicatat_oleh", bool(rek) and rek["keputusan"] == "setuju"
    and rek["dicatat_oleh"] == "Kantor Cabang A (contoh)", str(rek))
# peserta luar wilayah
luar = T[~T["kode_wilayah"].isin(A)].iloc[0]["id_peserta"]
at.text_input(key="cari_id").set_value(luar).run()
cek("c. peserta luar wilayah -> info", any("di luar wilayah kantor cabang Anda" in i.value for i in at.info)
    and not at.exception, luar)
cek("c. luar wilayah: tidak ada tombol simpan", not any(b.label == "Simpan keputusan" for b in at.button))
# contoh peserta untuk cabang hanya wilayahnya: reset id
at.session_state["_pid_terakhir"] = None
at.query_params.pop("id", None)
at.run()
contoh = [b.label for b in at.button if b.key and b.key.startswith("contoh_")]
cek("c. contoh peserta hanya wilayah A", all(T.set_index("id_peserta").loc[i, "kode_wilayah"] in A for i in contoh),
    str(contoh))
# CSV: kolom dicatat_oleh dan keputusan pada unduhan -> uji lewat logika yang sama
at.switch_page("halaman/daftar_kerja.py").run()
cek("c. kolom Keputusan tampil di tabel cabang", "Keputusan" in at.dataframe[0].value.columns
    and "Dicatat oleh" not in at.dataframe[0].value.columns)
keputusan_tersimpan = dict(at.session_state["_keputusan"])

# (d) ganti akun ke Pusat
klik(at, "Ganti akun")
cek("d. Ganti akun -> halaman Masuk", at.session_state["_akun"] is None
    and any(b.label == "Masuk" for b in at.button) and not at.exception)
cek("d. keputusan tetap ada", at.session_state["_keputusan"] == keputusan_tersimpan)
at.radio(key="pilih_akun").set_value("pusat").run()
klik(at, "Masuk")
at.switch_page("halaman/daftar_kerja.py").run()
df = at.dataframe[0].value
cek("d. Pusat melihat keputusan di tabel", "Keputusan" in df.columns and "Dicatat oleh" in df.columns)
at.switch_page("halaman/profil_peserta.py").run()
at.text_input(key="cari_id").set_value("P-005882").run()
tk = teks_semua(at)
cek("d. Pusat profil: keputusan hanya-baca + pencatat", "Dicatat oleh Kantor Cabang A (contoh)" in tk
    and "Keputusan dicatat oleh petugas kantor cabang" in tk
    and not any(b.label == "Simpan keputusan" for b in at.button))
cek("d. Pusat boleh buka peserta luar wilayah A", not any("di luar wilayah" in i.value for i in at.info))
at.text_input(key="cari_id").set_value(luar).run()
cek("d. Pusat buka peserta lain tanpa error", not at.exception and at.session_state["_pid_terakhir"] == luar)

# (e) query param
for k in ["cabang_a", "pusat", "cabang_d"]:
    at = baru()
    at.query_params["akun"] = k
    at.run()
    cek(f"e. ?akun={k} langsung masuk", at.session_state["_akun"] == k and not at.exception
        and any(b.label == "Ganti akun" for b in at.button))
at = baru()
at.query_params["akun"] = "ngawur"
at.run()
cek("e. ?akun tak dikenal -> tetap di Masuk", at.session_state["_akun"] is None if "_akun" in at.session_state else True)

print(f"\n{sum(HASIL)}/{len(HASIL)} lulus")
sys.exit(0 if all(HASIL) else 1)
