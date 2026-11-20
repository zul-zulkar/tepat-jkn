package pesan

import (
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

// Regex Go (RE2) memakai \b, \w, \d, dan \s versi ASCII, sedangkan llm.py memakai versi Unicode Python.
// Supaya hasil penilaian sama, pola dijalankan pada "proyeksi ASCII" teks: tiap karakter non-ASCII diganti
// satu karakter ASCII yang berperan sama bagi pola-pola di sini. Huruf dan angka lain jadi "_" (karakter kata
// yang tidak muncul di kata kunci mana pun), angka desimal jadi angka ASCII yang nilainya sama, spasi jadi
// spasi, sisanya "#". Untuk pola tanpa beda huruf besar-kecil, "İ" dan "ı" jadi "i" karena re.IGNORECASE
// Python menyamakan keduanya dengan "i" ("ſ" dan tanda Kelvin sudah jadi ASCII lewat NFKC). Proyeksi hanya
// untuk mencocokkan; panjang dan teks yang dikembalikan memakai teks asli.

// kataPy: karakter yang dihitung \w oleh Python (huruf, angka, garis bawah).
func kataPy(r rune) bool {
	return r == '_' || unicode.IsLetter(r) || unicode.IsNumber(r)
}

// spasiPy: karakter yang dihitung str.isspace() oleh Python.
func spasiPy(r rune) bool {
	switch {
	case r == ' ' || (r >= '\t' && r <= '\r') || (r >= 0x1c && r <= 0x1f) || r == 0x85:
		return true
	case r < 0x80:
		return false
	}
	return unicode.Is(unicode.Z, r)
}

// nilaiDigit memberi nilai angka desimal Unicode (kategori Nd); blok Nd selalu sepuluh kode berurutan.
func nilaiDigit(r rune) rune {
	awal := r
	for unicode.IsDigit(awal - 1) {
		awal--
	}
	return '0' + (r-awal)%10
}

func proyeksi(s string, abaikanKapital bool) string {
	ascii := true
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x80 || s[i] == '\v' || (s[i] >= 0x1c && s[i] <= 0x1f) {
			ascii = false
			break
		}
	}
	if ascii {
		return s
	}
	var b strings.Builder
	for _, r := range s {
		switch {
		case r == '\v' || (r >= 0x1c && r <= 0x1f):
			b.WriteByte(' ')
		case r < 0x80:
			b.WriteRune(r)
		case abaikanKapital && (r == 0x130 || r == 0x131):
			b.WriteByte('i')
		case unicode.IsDigit(r):
			b.WriteRune(nilaiDigit(r))
		case kataPy(r):
			b.WriteByte('_')
		case spasiPy(r):
			b.WriteByte(' ')
		default:
			b.WriteByte('#')
		}
	}
	return b.String()
}

func trimPy(s string) string { return strings.TrimFunc(s, spasiPy) }

func panjang(s string) int { return len([]rune(s)) }

// tanpaLebar: karakter yang dibuang _norm (zero-width, BOM).
func tanpaLebar(r rune) bool { return (r >= 0x200b && r <= 0x200f) || r == 0x2060 || r == 0xfeff }

// normal = llm._norm: NFKC, spasi non-pecah jadi spasi, karakter tanpa lebar dibuang.
func normal(s string) string {
	s = strings.ReplaceAll(norm.NFKC.String(s), " ", " ")
	return strings.Map(func(r rune) rune {
		if tanpaLebar(r) {
			return -1
		}
		return r
	}, s)
}

// BersihkanKarakter membuang karakter tak terlihat (zero-width, soft hyphen, BOM) dan mengganti spasi
// non-pecah dengan spasi biasa. Validator menilai teks yang sudah dinormalisasi; tanpa ini petugas menerima
// teks yang berbeda dari yang dinilai.
func BersihkanKarakter(s string) string {
	return strings.Map(func(r rune) rune {
		switch {
		case r == 0x00a0 || r == 0x202f:
			return ' '
		case r == 0x00ad || tanpaLebar(r):
			return -1
		}
		return r
	}, s)
}

// rapat: hanya huruf kecil a-z tanpa aksen, untuk menangkap "c u r a n g" atau "c.u.r.a.n.g".
func rapat(s string) string {
	d := norm.NFKD.String(normal(s))
	var b strings.Builder
	for _, r := range d {
		if norm.NFKD.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		for _, l := range strings.ToLower(string(r)) {
			if l >= 'a' && l <= 'z' {
				b.WriteRune(l)
			}
		}
	}
	return b.String()
}
