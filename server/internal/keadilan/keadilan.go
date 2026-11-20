// Package keadilan menghitung panel keadilan: seberapa sering tiap kelompok peserta masuk jalur verifikasi
// dan masuk daftar yang diperiksa, dibanding rata-rata semua peserta. Port dari halaman/keadilan.py.
//
// Tanpa label: yang dihitung semua peserta di jalur, bukan hanya yang jujur. Angka seluruh jalur diambil dari
// bukti/hasil/beban_strata.csv dan dicocokkan baris demi baris dengan hitungan ulang di sini.
//
// Ambang 2x dikunci di pra-registrasi (uji T4). "Perlu perhatian" (>= 1,25x, batas bawah selang Wilson 95% di
// atas 1x) dan "jarang diperiksa" (<= 0,8x, batas atas di bawah 1x) ditambahkan sesudah hasil dilihat.
package keadilan

import (
	"cmp"
	"math"
	"slices"
	"strconv"

	"github.com/zul-zulkar/tepat-jkn/server/internal/acaknp"
	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
	"github.com/zul-zulkar/tepat-jkn/server/internal/triase"
)

// Parameter panel (sama dengan halaman/keadilan.py).
const (
	KPorsi          = 0.01 // kapasitas periksa: 1% peserta (pra-registrasi bagian 3a)
	AmbangPra       = 2.0  // pra-registrasi T4
	AmbangPerhatian = 1.25 // ditambahkan sesudah melihat hasil
	z95             = 1.96
)

// AmbangJarang = 1 / AmbangPerhatian (0,8x).
var AmbangJarang = 1 / AmbangPerhatian

// Status satu kelompok.
const (
	Wajar     = "wajar"
	Perhatian = "perhatian"
	DiAtas    = "di_atas"
)

// Baris adalah satu kelompok di satu dimensi.
type Baris struct {
	Dimensi       string   `json:"dimensi"`
	Kelompok      string   `json:"kelompok"`
	N             int      `json:"n"`
	NJalur        int      `json:"n_jalur"`
	NPeriksa      int      `json:"n_periksa"`
	PorsiJalur    float64  `json:"porsi_jalur"`
	PorsiPeriksa  float64  `json:"porsi_periksa"`
	RasioJalur    float64  `json:"rasio_jalur"`
	RasioPeriksa  float64  `json:"rasio_periksa"`
	StatusJalur   string   `json:"status_jalur"`
	StatusPeriksa string   `json:"status_periksa"`
	JarangJalur   bool     `json:"jarang_jalur"`
	JarangPeriksa bool     `json:"jarang_periksa"`
	PorsiPop      float64  `json:"porsi_pop"`
	BagianJalur   float64  `json:"bagian_jalur"`
	BagianPeriksa float64  `json:"bagian_periksa"`
	BatasAtas     float64  `json:"batas_atas"`
	LuarJalur     *float64 `json:"luar_jalur"`   // nil bila tidak terhingga atau tidak terdefinisi
	LuarPeriksa   *float64 `json:"luar_periksa"` // idem
}

// Info adalah angka ringkas panel.
type Info struct {
	N           int     `json:"n"`
	Isi         int     `json:"isi"`
	K           int     `json:"k"`
	M           int     `json:"m"`
	BarisCSV    int     `json:"baris_csv"`
	Cocok       int     `json:"cocok"`
	RataJalur   float64 `json:"rata_j"`
	RataPeriksa float64 `json:"rata_p"`
	NWilayah    int     `json:"n_wilayah"`
	WilMin      int     `json:"wil_min"`
	WilMaks     int     `json:"wil_maks"`
}

// Hasil panel.
type Hasil struct {
	Tabel []Baris `json:"tabel"`
	Info  Info    `json:"info"`
}

type peserta struct {
	id        string
	skor      float64
	jalur     bool
	diperiksa bool
	wilayah   string
	kelompok  map[string]string // dimensi -> kelompok
}

// Hitung panel dari skor_verifikasi.csv (urut id_peserta), atribut peserta, dan beban_strata.csv.
func Hitung(s *data.Store) Hasil {
	d := make([]peserta, 0, len(s.SkorVerifikasi))
	for _, sv := range s.SkorVerifikasi {
		p := s.Cari(sv.ID)
		if p == nil {
			continue // halaman Python berhenti dengan assert; di sini peserta tanpa atribut dilewati
		}
		d = append(d, peserta{id: sv.ID, skor: sv.Skor, jalur: sv.Rute == triase.Verifikasi, wilayah: p.KodeWilayah,
			kelompok: map[string]string{"kelas": "kelas_" + strconv.Itoa(p.Kelas), "usia": kelompokUsia(p.Usia2023),
				"jk": p.JenisKelamin}})
	}
	// kemiskinan wilayah: tiga kelompok menurut peringkat indeks (pd.qcut atas rank(method="first"))
	tiga := kemiskinanTiga(s, d)
	for i := range d {
		d[i].kelompok["kemiskinan"] = tiga[d[i].wilayah]
	}

	n := len(d)
	isi := 0
	for _, p := range d {
		if p.jalur {
			isi++
		}
	}
	k := int(math.Ceil(math.Round(KPorsi*float64(n)*1e9) / 1e9))
	m := min(k, isi)

	// yang diperiksa: pra-registrasi 3a, skor + (1 + u) x 1e-6, u dari default_rng([7, 1]), urut stabil
	g := acaknp.Baru(7, 1)
	skorDaftar := make([]float64, n)
	for i, p := range d {
		u := g.Float64()
		if p.jalur {
			skorDaftar[i] = p.skor + (1+u)*1e-6
		}
	}
	urut := make([]int, n)
	for i := range urut {
		urut[i] = i
	}
	slices.SortStableFunc(urut, func(a, b int) int { return cmp.Compare(-skorDaftar[a], -skorDaftar[b]) })
	for _, i := range urut[:m] {
		d[i].diperiksa = true
	}

	type hitungan struct{ n, jalur, periksa int }
	ulang := map[[2]string]*hitungan{}
	for _, p := range d {
		for dim, kel := range p.kelompok {
			h := ulang[[2]string{dim, kel}]
			if h == nil {
				h = &hitungan{}
				ulang[[2]string{dim, kel}] = h
			}
			h.n++
			if p.jalur {
				h.jalur++
			}
			if p.diperiksa {
				h.periksa++
			}
		}
	}

	info := Info{N: n, Isi: isi, K: k, M: m, BarisCSV: len(s.BebanStrata)}
	info.RataJalur, info.RataPeriksa = float64(isi)/float64(n), float64(m)/float64(n)

	// baris yang ada di CSV dan di hitungan ulang, urut (dimensi, kelompok) seperti merge pandas
	var tabel []Baris
	for _, b := range s.BebanStrata {
		h := ulang[[2]string{b.Dimensi, b.Kelompok}]
		if h == nil {
			continue
		}
		if h.n == b.NPeserta && h.jalur == b.NJalur {
			info.Cocok++
		}
		tabel = append(tabel, baris(b, h.periksa, n, isi, m, info.RataJalur, info.RataPeriksa))
	}
	slices.SortFunc(tabel, func(a, b Baris) int {
		return cmp.Or(cmp.Compare(a.Dimensi, b.Dimensi), cmp.Compare(a.Kelompok, b.Kelompok))
	})

	perWil := map[string]int{}
	semuaWil := map[string]bool{}
	for _, p := range d {
		semuaWil[p.wilayah] = true
		if p.jalur {
			perWil[p.wilayah]++
		}
	}
	info.NWilayah = len(semuaWil)
	info.WilMin, info.WilMaks = math.MaxInt, 0
	for _, v := range perWil {
		info.WilMin, info.WilMaks = min(info.WilMin, v), max(info.WilMaks, v)
	}
	return Hasil{Tabel: tabel, Info: info}
}

func baris(b data.BebanStrata, nPeriksa, n, isi, m int, rataJ, rataP float64) Baris {
	r := Baris{Dimensi: b.Dimensi, Kelompok: b.Kelompok, N: b.NPeserta, NJalur: b.NJalur, NPeriksa: nPeriksa}
	fn := float64(r.N)
	r.PorsiJalur, r.PorsiPeriksa = float64(r.NJalur)/fn, float64(r.NPeriksa)/fn
	r.RasioJalur, r.RasioPeriksa = r.PorsiJalur/rataJ, r.PorsiPeriksa/rataP
	r.StatusJalur, r.StatusPeriksa = status(r.NJalur, r.N, rataJ), status(r.NPeriksa, r.N, rataP)
	r.JarangJalur, r.JarangPeriksa = terlaluJarang(r.NJalur, r.N, rataJ), terlaluJarang(r.NPeriksa, r.N, rataP)
	r.PorsiPop = fn / float64(n)
	r.BagianJalur, r.BagianPeriksa = float64(r.NJalur)/float64(isi), float64(r.NPeriksa)/float64(m)
	r.BatasAtas = float64(n) / fn
	if sisa := float64(n - r.N); sisa > 0 {
		r.LuarJalur = terhingga(r.PorsiJalur / (float64(isi-r.NJalur) / sisa))
		r.LuarPeriksa = terhingga(r.PorsiPeriksa / (float64(m-r.NPeriksa) / sisa))
	}
	return r
}

// WilsonBawah adalah batas bawah selang 95% Wilson untuk porsi x/n.
func WilsonBawah(x, n int) float64 {
	fn := float64(n)
	p, z2 := float64(x)/fn, z95*z95
	pusat := (p + z2/float64(2*n)) / (1 + z2/fn)
	sisi := z95 * math.Sqrt(p*(1-p)/fn+z2/float64(4*n*n)) / (1 + z2/fn)
	return pusat - sisi
}

// WilsonAtas adalah batas atas selang 95% Wilson untuk porsi x/n.
func WilsonAtas(x, n int) float64 { return 1 - WilsonBawah(n-x, n) }

func status(x, n int, rata float64) string {
	r := (float64(x) / float64(n)) / rata
	switch {
	case r > AmbangPra:
		return DiAtas
	case r >= AmbangPerhatian && WilsonBawah(x, n)/rata > 1:
		return Perhatian
	}
	return Wajar
}

func terlaluJarang(x, n int, rata float64) bool {
	return (float64(x)/float64(n))/rata <= AmbangJarang && WilsonAtas(x, n)/rata < 1
}

func kelompokUsia(u int) string {
	switch {
	case u > 0 && u <= 35:
		return "<=35"
	case u > 35 && u <= 55:
		return "36-55"
	case u > 55 && u <= 200:
		return ">55"
	}
	return "nan"
}

// kemiskinanTiga membagi wilayah ke tiga kelompok sama besar menurut peringkat indeks kemiskinan. Peringkat
// seri dipecah menurut urutan kode wilayah (rank method="first" setelah urut kode), lalu dipotong pada
// kuantil 1/3 dan 2/3 dengan interpolasi linear, batas kanan tertutup (pd.qcut).
func kemiskinanTiga(s *data.Store, d []peserta) map[string]string {
	indeks := map[string]float64{}
	for _, p := range d {
		if _, ada := indeks[p.wilayah]; !ada {
			indeks[p.wilayah] = s.Cari(p.id).IndeksKemiskinan
		}
	}
	wil := make([]string, 0, len(indeks))
	for w := range indeks {
		wil = append(wil, w)
	}
	slices.Sort(wil)
	urut := slices.Clone(wil)
	slices.SortStableFunc(urut, func(a, b string) int { return cmp.Compare(indeks[a], indeks[b]) })
	peringkat := map[string]int{}
	for i, w := range urut {
		peringkat[w] = i + 1
	}
	// batas ke-j = 1 + j(n-1)/3; dibandingkan secara pecahan supaya batas yang tepat bilangan bulat
	// (n = 40: 14 dan 27) tidak bergeser karena galat pembulatan
	n := len(wil)
	dalam := func(r, j int) bool { return 3*(r-1) <= j*(n-1) }
	hasil := map[string]string{}
	for _, w := range wil {
		switch r := peringkat[w]; {
		case dalam(r, 1):
			hasil[w] = "rendah"
		case dalam(r, 2):
			hasil[w] = "sedang"
		default:
			hasil[w] = "tinggi"
		}
	}
	return hasil
}

func terhingga(v float64) *float64 {
	if math.IsInf(v, 0) || math.IsNaN(v) {
		return nil
	}
	return &v
}
