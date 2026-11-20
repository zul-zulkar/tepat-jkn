package pesan

import (
	"regexp"
	"slices"
	"strconv"
	"strings"
)

// Aturan pesan yang dijaga KODE, bukan hanya prompt (port llm.py). Jawaban AI yang melanggar dibuang dan
// template dipakai. Semua pola dijalankan pada proyeksi ASCII (lihat teks.go).

// Batas panjang pesan dan ringkasan, dalam karakter.
const (
	MinPanjang    = 60
	MaksPanjang   = 1000
	MaksRingkasan = 400
)

// WajibSebut: opsi yang sesuai jalur; tiap grup harus terwakili sedikitnya satu istilah.
var WajibSebut = map[string][][]string{
	"rujuk_cek_kelayakan_PBI":                             {{"PBI"}},
	"nonaktif_lama_tanpa_sinyal":                          {{"REHAB 3.0", "PBI"}},
	"pengingat_autodebet_REHAB":                           {{"REHAB 3.0", "autodebet"}},
	"peringatan_dini:pengingat_H-5_dan_tawaran_autodebet": {{"autodebet"}},
	"peringatan_dini:pengingat_saldo_autodebet":           {{"autodebet"}},
	"peringatan_dini:cek_kelayakan_PBI":                   {{"PBI"}},
}

var istilahBoleh = []string{"REHAB 3.0", "autodebet", "PBI"}

// Jalur yang tidak boleh mendorong peserta membayar: peserta diarahkan ke pengecekan PBI. Uji model asli
// 29 Okt: 3 dari 3 draf jalur PBI menyelipkan autodebet/REHAB.
var tanpaOpsiBayar = map[string]bool{"rujuk_cek_kelayakan_PBI": true}

const catatanTanpaOpsiBayar = " Peserta ini diarahkan ke pengecekan PBI dan tidak sedang diminta membayar: " +
	"jangan menyebut autodebet, REHAB 3.0, cicilan, atau angsuran."

// Ringkasan petugas jalur PBI wajib menyebut "kelayakan PBI" (uji 30 Okt: model menulis "kepesertaan PBI",
// artinya lain). Pelanggaran hanya membuang ringkasan, bukan seluruh draf.
var polaKelayakanPBI = regexp.MustCompile(`(?i)\bkelayakan\s+PBI\b`)

var ringkasanWajib = map[string]*regexp.Regexp{
	"rujuk_cek_kelayakan_PBI":           polaKelayakanPBI,
	"peringatan_dini:cek_kelayakan_PBI": polaKelayakanPBI,
}

const catatanRingkasanPBI = "\n10. Di \"ringkasan_petugas\" sebut tindak lanjut peserta ini persis \"cek kelayakan PBI\". " +
	"Jangan menulis \"kepesertaan PBI\": artinya lain."

var (
	polaOpsiBayar = regexp.MustCompile(`(?i)auto[\s-]?debet|rehab|\w*cicil\w*|\w*angsur\w*`)

	// Opsi yang disebut sebuah teks. "rehab" tidak boleh diikuti huruf (bukan "rehabilitasi").
	polaOpsi = []struct {
		nama string
		pola *regexp.Regexp
	}{
		{"REHAB 3.0", regexp.MustCompile(`(?i)\brehab(?:[^a-z]|$)`)},
		{"autodebet", regexp.MustCompile(`(?i)auto[\s-]?debet`)},
		{"PBI", regexp.MustCompile(`(?i)\bPBI\b`)},
	}

	polaCurang  = regexp.MustCompile(`(?i)curang|fraud`)
	polaTuduhan = regexp.MustCompile(`(?i)\b(sengaja|pura-?pura|bohong|membohongi|menipu|penipu\w*|manipulasi|` +
		`memanipulasi|melanggar|pelanggaran|menyalahgunakan|penyalahgunaan|mengakali|akal-?akalan|menghindar\w*|mangkir)\b`)
	polaAncaman = regexp.MustCompile(`(?i)\b(?:denda|sanksi|hukuman|dihukum|pidana|dipidana|penjara|dipenjara|polisi|` +
		`kepolisian|(?:proses|jalur|tindakan|akibat) hukum|dilaporkan|melaporkan anda|ditindak|tindakan tegas|tindak tegas|` +
		`diblokir|dicabut|pencabutan|dibekukan|diputus|kehilangan hak|konsekuensi|dikenai|dikenakan|` +
		`ultimatum|peringatan terakhir|kesempatan terakhir|jangan sampai|awas)\w*`)
	polaInternal = regexp.MustCompile(`(?i)\b(skor|score|peluang|probabilitas|risiko|berisiko|peringatan dini|triase|` +
		`rute|jalur|model|algoritma|prediksi|diprediksi|kecerdasan buatan|desil|dtsen|reaktivasi|verifikasi|klaim)\b`)
	// Penguat kepastian: template sengaja berhati-hati ("mungkin memenuhi syarat"). "pastikan"/"memastikan"
	// dan "Jaminan Kesehatan Nasional" tidak kena.
	polaKepastian = regexp.MustCompile(`(?i)\b(?:(?:sudah|hampir)\s+pasti|pasti|dipastikan|(?:besar|tinggi)\s+kemungkinan|` +
		`kemungkinan\s+(?:besar|tinggi)|(?:sangat|amat)\s+mungkin)\b`)
	polaAIKapital = regexp.MustCompile(`\bAI\b`)
	polaPersen    = regexp.MustCompile(`(?i)\d\s*%|\bpersen\b`)
	polaTautan    = regexp.MustCompile(`(?i)https?://|www\.|@\w|\b[\w-]+\.(?:com|id|co|net|org)\b|(?:\+62|\b0)8\d{6,}`)
	polaAngka     = regexp.MustCompile(`\d+(?:[.,]\d+)*`)
	polaRupiah    = regexp.MustCompile(`(?i)Rp\.?\s*(\d+(?:[.,]\d+)*)`)
	polaBulan     = regexp.MustCompile(`(?i)(\d+)\s+bulan\b`)
	polaSatuan    = regexp.MustCompile(`(?i)\b\d[\d.,]*\s*(?:ribu|rb|juta|jt|rupiah)\b`)
	polaPBI       = regexp.MustCompile(`\bPBI\b`)
	polaKurawal   = regexp.MustCompile(`[{}]`)
)

// OpsiDalam mengembalikan opsi (REHAB 3.0 / autodebet / PBI) yang disebut teks, urut nama.
func OpsiDalam(teks string) []string {
	t := proyeksi(normal(teks), true)
	var hasil []string
	for _, o := range polaOpsi {
		if o.pola.MatchString(t) {
			hasil = append(hasil, o.nama)
		}
	}
	slices.Sort(hasil)
	return hasil
}

// rehabLama: "REHAB" yang tidak diikuti "3.0" (boleh satu spasi di antaranya).
func rehabLama(t string) bool {
	for i := 0; ; {
		j := strings.Index(t[i:], "REHAB")
		if j < 0 {
			return false
		}
		sisa := t[i+j+5:]
		if len(sisa) > 0 && spasiPy(rune(sisa[0])) {
			sisa = sisa[1:]
		}
		if !strings.HasPrefix(sisa, "3.0") {
			return true
		}
		i += j + 5
	}
}

// PeriksaKata: kata terlarang untuk semua teks buatan AI (pesan dan ringkasan petugas).
func PeriksaKata(teks string) []string {
	t := normal(teks)
	ci := proyeksi(t, true)
	r := rapat(t)
	var hasil []string
	if polaCurang.MatchString(ci) || strings.Contains(r, "curang") {
		hasil = append(hasil, "curang")
	}
	if polaTuduhan.MatchString(ci) {
		hasil = append(hasil, "tuduhan")
	}
	if polaAncaman.MatchString(ci) || slices.ContainsFunc([]string{"sanksi", "pidana", "penjara", "dilaporkan"},
		func(k string) bool { return strings.Contains(r, k) }) {
		hasil = append(hasil, "ancaman")
	}
	return hasil
}

// PeriksaPesanPeserta mengembalikan daftar pelanggaran (kosong = lolos). teks masih berisi {ID}.
// opsiBoleh: opsi yang disebut template; nil = tidak diperiksa.
func PeriksaPesanPeserta(teks, kodeAturan string, bulan int, nominal []int, opsiBoleh []string) []string {
	t := normal(teks)
	ci, cs := proyeksi(t, true), proyeksi(t, false)
	p := PeriksaKata(t)
	if n := panjang(trimPy(t)); n < MinPanjang || n > MaksPanjang {
		p = append(p, "panjang")
	}
	if polaInternal.MatchString(ci) || polaAIKapital.MatchString(cs) {
		p = append(p, "istilah_internal")
	}
	if polaPersen.MatchString(ci) {
		p = append(p, "angka_persen")
	}
	if polaKepastian.MatchString(ci) {
		p = append(p, "klaim_pasti")
	}
	if polaTautan.MatchString(ci) {
		p = append(p, "tautan_atau_kontak")
	}
	if rehabLama(cs) {
		p = append(p, "rehab_tanpa_3.0")
	}
	for _, grup := range WajibSebut[kodeAturan] {
		ada := slices.ContainsFunc(grup, func(k string) bool {
			switch k {
			case "PBI":
				return polaPBI.MatchString(cs)
			case "REHAB 3.0":
				return strings.Contains(cs, k)
			}
			return strings.Contains(strings.ToLower(ci), strings.ToLower(k))
		})
		if !ada {
			p = append(p, "tanpa_opsi:"+strings.Join(grup, "/"))
		}
	}
	if tanpaOpsiBayar[kodeAturan] && polaOpsiBayar.MatchString(ci) {
		p = append(p, "opsi_bayar_di_jalur_pbi")
	}
	if opsiBoleh != nil {
		var luar []string
		for _, o := range OpsiDalam(t) {
			if !slices.Contains(opsiBoleh, o) {
				luar = append(luar, o)
			}
		}
		if len(luar) > 0 {
			p = append(p, "opsi_di_luar_template:"+strings.Join(luar, "/"))
		}
	}

	// angka: hanya yang ada di data peserta, 165 (Care Center), tanggal 10 (jatuh tempo), 5 (H-5)
	// berurutan seperti llm.py: {ID} dulu, lalu "REHAB 3.0"
	ganti := func(s string) string {
		return strings.ReplaceAll(strings.ReplaceAll(s, "{ID}", " "), "REHAB 3.0", " ")
	}
	sisa := ganti(ci)
	boleh := map[int]bool{bulan: true, 165: true, 10: true, 5: true}
	nom := map[int]bool{}
	for _, n := range nominal {
		boleh[n], nom[n] = true, true
	}
	if polaSatuan.MatchString(sisa) {
		p = append(p, "angka_asing")
	} else {
		for _, m := range polaRupiah.FindAllStringSubmatch(sisa, -1) {
			if v, ok := keInt(m[1]); !ok || !nom[v] {
				p = append(p, "nominal_salah")
				break
			}
		}
		for _, m := range polaBulan.FindAllStringSubmatch(sisa, -1) {
			if v, ok := keInt(m[1]); !ok || v != bulan {
				p = append(p, "bulan_salah")
				break
			}
		}
		for _, m := range polaAngka.FindAllString(polaRupiah.ReplaceAllString(sisa, " "), -1) {
			if v, ok := keInt(m); !ok || !boleh[v] {
				p = append(p, "angka_asing")
				break
			}
		}
	}
	if polaKurawal.MatchString(ganti(cs)) {
		p = append(p, "penampung_sisa")
	}
	return unik(p)
}

// PeriksaRingkasan menilai ringkasan untuk petugas.
func PeriksaRingkasan(teks string) []string {
	p := PeriksaKata(teks)
	if trimPy(teks) == "" || panjang(teks) > MaksRingkasan {
		p = append(p, "panjang_ringkasan")
	}
	return p
}

func keInt(s string) (int, bool) {
	v, err := strconv.Atoi(strings.NewReplacer(".", "", ",", "").Replace(s))
	return v, err == nil
}

func unik(xs []string) []string {
	hasil := []string{}
	for _, x := range xs {
		if !slices.Contains(hasil, x) {
			hasil = append(hasil, x)
		}
	}
	return hasil
}
