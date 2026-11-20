package pesan

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

// Perapian spasi (port llm.rapikan_spasi). Model kelas lite sering menghilangkan satu spasi ("programREHAB 3.0",
// "bulan,Anda", "Bapak/Ibuuntuk"). Tanpa kamus bahasa Indonesia hanya dua jenis perbaikan yang cukup aman:
// (1) pola yang tidak mungkin sah, dan (2) token yang bukan anggota kosakata tertutup tetapi persis gabungan dua
// anggotanya. Hanya spasi yang ditambah; huruf tidak diubah. Kosakata sengaja tidak memuat kata yang bersama
// kata lain membentuk kata sah (mis. "dari" dan "pada", karena "daripada" sah).

var kosakata = func() map[string]bool {
	m := map[string]bool{}
	for _, k := range strings.Fields(`
untuk dengan oleh atau dapat lebih lanjut yang agar bisa terus juga serta jika bila mohon silakan kami anda
ibu bapak mungkin perlu cukup masih sudah belum sedang saat total iuran tunggakan nominal jumlah bulan kartu
peserta program aplikasi layanan kesehatan kepesertaan pembayaran pelunasan melunasi melakukan mengajukan
mendaftarkan mencicil cicilan berkonsultasi menghubungi mengakses informasi bantuan kantor desa kelurahan
setempat pengecekan mengecek membantu terlindungi perlindungan kembali aktif nonaktif otomatis rutin berobat
minimarket bank autodebet pemerintah petugas tercatat dibayar dibayarkan terbayar menyarankan menanyakan
memanfaatkan memenuhi syarat kriteria rujukan proses data
diarahkan disarankan cek ini tindak kelayakan menunggak memiliki sehingga karena namun termasuk kategori`) {
		m[k] = true
	}
	return m
}()

func hurufKecil(b byte) bool { return b >= 'a' && b <= 'z' }
func hurufBesar(b byte) bool { return b >= 'A' && b <= 'Z' }
func huruf(b byte) bool      { return hurufKecil(b) || hurufBesar(b) }
func angkaASCII(b byte) bool { return b >= '0' && b <= '9' }
func kataSebelum(s string, i int) bool {
	r, _ := utf8.DecodeLastRuneInString(s[:i])
	return i > 0 && kataPy(r)
}
func kataSesudah(s string, i int) bool {
	r, _ := utf8.DecodeRuneInString(s[i:])
	return i < len(s) && kataPy(r)
}

// pisahGabungan: token bukan anggota kosakata tetapi gabungan dua anggotanya; bagian pertama terpanjang dulu,
// tiap bagian sedikitnya 3 huruf.
func pisahGabungan(t string) string {
	r := strings.ToLower(t)
	if kosakata[r] {
		return t
	}
	for i := len(r) - 3; i > 2; i-- {
		if kosakata[r[:i]] && kosakata[r[i:]] {
			return t[:i] + " " + t[i:]
		}
	}
	return t
}

// sisip menyisipkan sisipan di tiap posisi yang lolos uji (posisi byte, urut naik) dan menghitungnya.
func sisip(s string, kena func(i int) (pos int, ok bool), sisipan string) (string, int) {
	var b strings.Builder
	n, akhir := 0, 0
	for i := 0; i <= len(s); i++ {
		if pos, ok := kena(i); ok {
			b.WriteString(s[akhir:pos])
			b.WriteString(sisipan)
			akhir = pos
			n++
		}
	}
	b.WriteString(s[akhir:])
	return b.String(), n
}

// RapikanSpasi mengembalikan teks rapi dan jumlah perbaikan. Idempoten; teks yang sudah rapi tidak berubah.
func RapikanSpasi(teks string) (string, int) {
	total := 0

	// token huruf ASCII >= 6 dengan batas kata Unicode di kedua sisi (\b[A-Za-z]{6,}\b)
	var b strings.Builder
	for i := 0; i < len(teks); {
		if !huruf(teks[i]) || kataSebelum(teks, i) {
			_, w := utf8.DecodeRuneInString(teks[i:])
			b.WriteString(teks[i : i+w])
			i += w
			continue
		}
		j := i
		for j < len(teks) && huruf(teks[j]) {
			j++
		}
		tok := teks[i:j]
		if len(tok) >= 6 && !kataSesudah(teks, j) {
			if h := pisahGabungan(tok); h != tok {
				tok = h
				total++
			}
		}
		b.WriteString(tok)
		i = j
	}
	teks = b.String()

	langkah := []func(s string) (string, int){
		// "Rp450.000.Selama", "bulan,Anda": tanda baca setelah huruf kecil/angka, sebelum huruf besar
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				ok := i > 0 && i+1 < len(s) && strings.IndexByte(".,;:!?", s[i]) >= 0 &&
					(hurufKecil(s[i-1]) || angkaASCII(s[i-1])) && hurufBesar(s[i+1])
				return i + 1, ok
			}, " ")
		},
		// "bulan,anda"
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				ok := i > 0 && i+1 < len(s) && strings.IndexByte(",;:", s[i]) >= 0 && huruf(s[i-1]) && hurufKecil(s[i+1])
				return i + 1, ok
			}, " ")
		},
		// "programREHAB": dua huruf kecil lalu singkatan kapital (>= 2 huruf) yang berakhir di batas kata
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				if i < 2 || !hurufKecil(s[i-2]) || !hurufKecil(s[i-1]) {
					return i, false
				}
				j := i
				for j < len(s) && hurufBesar(s[j]) {
					j++
				}
				return i, j-i >= 2 && !kataSesudah(s, j)
			}, " ")
		},
		// "BPJSKesehatan": singkatan di awal kata menempel pada kata berhuruf kapital
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				if i >= len(s) || !hurufBesar(s[i]) || kataSebelum(s, i) {
					return i, false
				}
				for _, a := range []string{"BPJS", "JKN", "PBI", "NIK", "KIS", "REHAB"} {
					j := i + len(a)
					if strings.HasPrefix(s[i:], a) && j+1 < len(s) && hurufBesar(s[j]) && hurufKecil(s[j+1]) {
						return j, true
					}
				}
				return i, false
			}, " ")
		},
		// "Bapak/Ibumungkin", tetapi bukan "Bapak/Ibunda", "-ku", "-mu", "-nya"
		func(s string) (string, int) {
			const sapa = "Bapak/Ibu"
			return sisip(s, func(i int) (int, bool) {
				j := i + len(sapa)
				if !strings.HasPrefix(s[i:], sapa) || j >= len(s) || !hurufKecil(s[j]) {
					return i, false
				}
				for _, akhiran := range []string{"nda", "ku", "mu", "nya"} {
					if strings.HasPrefix(s[j:], akhiran) {
						return i, false
					}
				}
				return j, true
			}, " ")
		},
		// "tunggakanRp450.000"
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				if i == 0 || !hurufKecil(s[i-1]) || !strings.HasPrefix(s[i:], "Rp") {
					return i, false
				}
				r, _ := utf8.DecodeRuneInString(s[i+2:])
				return i, i+2 < len(s) && unicode.IsDigit(r)
			}, " ")
		},
		// "nomor{ID}"
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				return i, i > 0 && (huruf(s[i-1]) || angkaASCII(s[i-1])) && strings.HasPrefix(s[i:], "{ID}")
			}, " ")
		},
		// "{ID}iuran"
		func(s string) (string, int) {
			return sisip(s, func(i int) (int, bool) {
				return i, i >= 4 && i < len(s) && s[i-4:i] == "{ID}" && huruf(s[i])
			}, " ")
		},
	}
	for _, f := range langkah {
		var n int
		teks, n = f(teks)
		total += n
	}
	return teks, total
}
