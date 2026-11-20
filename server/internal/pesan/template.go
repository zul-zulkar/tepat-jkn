// Package pesan menyusun draf pesan untuk petugas: template (port pesan_template.py) dan lapisan AI yang
// hanya menulis ulang kata-katanya (port llm.py). Template juga jalur cadangan bila AI tidak bisa dipakai.
//
// Aturan yang dijaga:
//   - Pesan tidak pernah mengubah rute. Rute datang dari aturan triase / model peringatan dini.
//   - Tanpa kata "curang", tanpa ancaman, tanpa menyebut skor.
//   - Rute verifikasi TIDAK menghasilkan pesan ke peserta, hanya catatan untuk petugas.
//   - Tagihan per KK belum dimodelkan; nominal di sini per peserta.
package pesan

import (
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Jenis draf.
const (
	PesanPeserta   = "pesan_peserta"
	CatatanPetugas = "catatan_petugas"
)

// Draf adalah satu draf pesan atau catatan.
type Draf struct {
	Sumber string `json:"sumber"`
	Jenis  string `json:"jenis"`
	Judul  string `json:"judul"`
	Isi    string `json:"isi"`
}

// Peserta adalah data yang dibutuhkan template dan lapisan AI. Tidak ada data lain yang dipakai.
type Peserta struct {
	ID             string
	Rute           string
	Alasan         string // alasan mentah dari pipeline
	AlasanRapi     string // alasan untuk tampilan (AlasanRapi(Alasan) di aplikasi)
	TunggakanBulan int
	TunggakanRp    float64
	IuranBulanan   float64
	Autodebet      bool
	EWSkor         *float64 // nil bila tidak dinilai model peringatan dini
	EWAlasan       string
	EWSaran        string
}

const (
	info     = "Informasi lebih lanjut: aplikasi Mobile JKN atau BPJS Kesehatan Care Center 165."
	pembuka  = "Yth. peserta JKN (nomor peserta {id}),"
	tdkPD    = "peringatan_dini"
	rVerif   = "verifikasi_pola_reaktivasi"
	rPBI     = "rujuk_cek_kelayakan_PBI"
	rNonaktf = "nonaktif_lama_tanpa_sinyal"
	rIngat   = "pengingat_autodebet_REHAB"
)

// Angka memformat bilangan bulat dengan titik ribuan, dibulatkan setengah ke genap seperti round() Python.
func Angka(x float64) string {
	s := strconv.FormatFloat(math.RoundToEven(x), 'f', 0, 64)
	neg := strings.HasPrefix(s, "-")
	s = strings.TrimPrefix(s, "-")
	var b strings.Builder
	for i, c := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			b.WriteByte('.')
		}
		b.WriteRune(c)
	}
	if neg {
		return "-" + b.String()
	}
	return b.String()
}

// Rp memformat rupiah: Rp1.234.000.
func Rp(x float64) string { return "Rp" + Angka(x) }

var (
	polaDesimalKali = regexp.MustCompile(`(\d+)\.(\d+)x\b`)
	polaBln         = regexp.MustCompile(`\bbln\b`)
)

// AlasanRapi hanya untuk tampilan: "<=" jadi "≤", "1.48x" jadi "1,48×", "bln" jadi "bulan", huruf pertama
// kapital. Sama dengan tepat_ui.alasan_rapi.
func AlasanRapi(s string) string {
	if s == "" {
		return ""
	}
	s = strings.ReplaceAll(strings.ReplaceAll(s, "<=", "≤"), ">=", "≥")
	s = polaDesimalKali.ReplaceAllString(s, "$1,$2×")
	s = polaBln.ReplaceAllString(s, "bulan")
	r, n := utf8.DecodeRuneInString(s)
	return string(unicode.ToUpper(r)) + s[n:]
}

func sapaan(id string) string { return strings.Replace(pembuka, "{id}", id, 1) }

func triase(p Peserta) *Draf {
	n := strconv.Itoa(p.TunggakanBulan)
	switch p.Rute {
	case rVerif:
		return &Draf{Sumber: "Triase", Jenis: CatatanPetugas, Judul: "Catatan untuk petugas",
			Isi: "Bukan untuk dikirim ke peserta.\n\n" +
				"Pola yang terlihat: " + strings.TrimRight(p.AlasanRapi, ".") + ".\n\n" +
				"Sebelum menindaklanjuti:\n" +
				"1. Cocokkan tanggal aktif kembali dengan tanggal klaim di linimasa.\n" +
				"2. Cek penjelasan lain yang wajar: jatuh miskin karena sakit, pasien penyakit kronis, " +
				"pembayar musiman. Bila klaimnya rawat inap IGD di hari yang sama dengan pelunasan, " +
				"kemungkinan peserta melunasi karena darurat.\n" +
				"3. Bila peserta ternyata tidak mampu, ubah tindak lanjut menjadi rujukan cek kelayakan PBI.\n\n" +
				"Dalam komunikasi dengan peserta, jangan memakai kata yang menuduh."}
	case rPBI:
		return &Draf{Sumber: "Triase", Jenis: PesanPeserta, Judul: "Pesan ke peserta",
			Isi: sapaan(p.ID) + "\n\n" +
				"iuran JKN Anda tercatat belum dibayar selama " + n + " bulan. Keluarga Anda mungkin " +
				"memenuhi syarat sebagai peserta yang iurannya dibayar pemerintah (PBI).\n\n" +
				"Silakan datang ke kantor desa atau kelurahan, atau Dinas Sosial setempat, untuk " +
				"pengecekan data. Petugas BPJS Kesehatan dapat membantu proses rujukannya.\n\n" + info}
	case rNonaktf:
		return &Draf{Sumber: "Triase", Jenis: PesanPeserta, Judul: "Pesan ke peserta",
			Isi: sapaan(p.ID) + "\n\n" +
				"kepesertaan JKN Anda sudah lama nonaktif, dengan tunggakan " + n + " bulan " +
				"(" + Rp(p.TunggakanRp) + "). Kami ingin membantu Anda kembali terlindungi.\n\n" +
				"Bila iuran terasa berat, Anda bisa mengajukan cicilan tunggakan lewat program REHAB 3.0, " +
				"atau menanyakan kemungkinan bantuan iuran (PBI) di kantor desa atau kelurahan.\n\n" + info}
	case rIngat:
		var isi string
		if p.TunggakanBulan > 0 {
			isi = sapaan(p.ID) + "\n\n" +
				"iuran JKN Anda tercatat belum dibayar selama " + n + " bulan (" + Rp(p.TunggakanRp) + "). " +
				"Selama iuran belum dibayar, kartu JKN belum bisa dipakai untuk berobat.\n\n" +
				"Pilihan yang bisa Anda ambil:\n" +
				"- melunasi lewat Mobile JKN, bank, atau minimarket;\n" +
				"- mengajukan cicilan tunggakan lewat program REHAB 3.0;\n" +
				"- mendaftarkan autodebet agar iuran terbayar otomatis tiap bulan.\n\n" + info
		} else {
			isi = sapaan(p.ID) + "\n\n" +
				"terima kasih, iuran JKN Anda saat ini sudah lunas. Catatan kami menunjukkan iuran " +
				"beberapa kali terlambat sehingga kepesertaan sempat nonaktif.\n\n" +
				"Agar tidak terulang, daftarkan autodebet lewat Mobile JKN atau bank Anda. Iuran " +
				Rp(p.IuranBulanan) + " per bulan dibayar paling lambat tanggal 10.\n\n" + info
		}
		return &Draf{Sumber: "Triase", Jenis: PesanPeserta, Judul: "Pesan ke peserta", Isi: isi}
	}
	return nil
}

func pencegahan(p Peserta) *Draf {
	iuran := Rp(p.IuranBulanan)
	var isi string
	switch p.EWSaran {
	case "pengingat_H-5_dan_tawaran_autodebet":
		isi = "iuran JKN bulan depan jatuh tempo tanggal 10. Agar tidak terlewat, Anda bisa " +
			"mendaftarkan autodebet lewat Mobile JKN atau bank Anda, sehingga iuran " + iuran + " " +
			"terbayar otomatis setiap bulan.\n\nTerima kasih sudah menjaga kepesertaan tetap aktif."
	case "pengingat_saldo_autodebet":
		isi = "iuran JKN Anda dibayar lewat autodebet. Pastikan saldo rekening cukup (" + iuran + ") " +
			"sebelum tanggal 10 agar pembayaran tidak gagal dan kepesertaan tetap aktif."
	case "cek_kelayakan_PBI":
		isi = "bila iuran mulai terasa berat, keluarga Anda mungkin memenuhi syarat sebagai peserta " +
			"yang iurannya dibayar pemerintah (PBI). Silakan cek ke kantor desa atau kelurahan, " +
			"atau Dinas Sosial setempat."
	default:
		return nil
	}
	return &Draf{Sumber: "Berisiko menunggak", Jenis: PesanPeserta, Judul: "Pesan pencegahan",
		Isi: sapaan(p.ID) + "\n\n" + isi + "\n\n" + info}
}

// Template menyusun draf untuk tindakan utama peserta saja (satu peserta, satu tindakan).
// tindakan = kode rute triase atau "peringatan_dini".
func Template(p Peserta, tindakan string) []Draf {
	var d *Draf
	switch {
	case tindakan == tdkPD:
		d = pencegahan(p)
	case tindakan == p.Rute:
		d = triase(p)
	}
	if d == nil {
		return []Draf{}
	}
	return []Draf{*d}
}
