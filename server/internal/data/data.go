// Package data memuat app_data (parquet dan manifest.json) dan bukti/hasil (CSV) ke memori, sekali saat
// server mulai. Tidak ada aturan rute atau skor di sini: semua angka sudah dihitung pipeline Python
// (siapkan_app.py, bukti/*.py). Label evaluasi (evaluasi_label.parquet) sengaja tidak dibaca.
//
// Bentuk data mengikuti tepat_ui.tabel_peserta: satu baris per peserta mandiri (peserta.parquet), digabung
// dengan daftar_kerja.parquet dan ew_daftar.parquet, ditambah status per 31 Des 2025 dari linimasa_status.
package data

import (
	"time"
)

// Manifest adalah bagian manifest.json yang dipakai server dan antarmuka.
type Manifest struct {
	TriasePerTanggal   string `json:"triase_per_tanggal"`
	EWBulanOperasional string `json:"ew_bulan_operasional"`
	EWKPersenDaftar    int    `json:"ew_k_persen_daftar"`
	EWKOrangDaftar     int    `json:"ew_k_orang_daftar"`
	EWNDinilai         int    `json:"ew_n_dinilai"`
}

// Kontribusi satu ciri terhadap skor peringatan dini (kolom kontribusi_* di ew_daftar.parquet).
type Kontribusi struct {
	Fitur string  `json:"fitur"`
	Nilai float64 `json:"nilai"`
}

// EW adalah posisi peserta di model peringatan dini (ew_daftar.parquet). Nil bila peserta tidak dinilai.
type EW struct {
	Peringkat   int
	Skor        float64
	Bulan       string
	MasukDaftar bool // masuk daftar kanonik (k 5%) di siapkan_app.py
	Alasan      string
	Saran       string
	Kontribusi  []Kontribusi // urutan kolom di berkas
}

// Peserta adalah satu baris tepat_ui.tabel_peserta.
type Peserta struct {
	// peserta.parquet
	ID               string
	TglDaftar        time.Time
	Kelas            int
	IuranBulanan     int
	Usia2023         int
	JenisKelamin     string
	KodeWilayah      string
	Autodebet        bool
	Segmen           string // segmen_kepesertaan
	PembayarIuran    string
	IndeksKemiskinan float64
	RentangDesil     string

	// linimasa_status: status terakhir menurut tgl_mulai; tanpa riwayat = "nonaktif"
	StatusAkhir string

	// daftar_kerja.parquet
	Rute               string
	Alasan             string
	TunggakanBulan     int
	TunggakanRp        int
	NReaktivasi        int
	NReaktTerkaitKlaim int
	RasioHariAktif     float64
	RasioKlaimIuran    *float64 // nil bila tidak terdefinisi (iuran nol)
	KlaimRp            float64
	IuranRp            float64

	EW *EW
}

// Status adalah satu periode status kepesertaan (linimasa_status.parquet).
type Status struct {
	Mulai   time.Time
	Selesai time.Time
	Status  string
}

// Bayar adalah satu pembayaran iuran (linimasa_bayar.parquet).
type Bayar struct {
	Tanggal      time.Time
	PeriodeAwal  string
	PeriodeAkhir string
	JumlahBulan  int
	Nominal      int
	Kanal        string
}

// Klaim adalah satu klaim layanan (linimasa_klaim.parquet).
type Klaim struct {
	ID              string
	Episode         string
	TglMasuk        time.Time
	TglKeluar       time.Time
	JenisLayanan    string
	CaraMasuk       string
	KelompokLayanan string
	KelasRawat      int
	BiayaKlaim      int
	DendaPelayanan  int
}

// Reaktivasi adalah satu kali peserta aktif kembali (linimasa_reaktivasi.parquet).
type Reaktivasi struct {
	Tanggal         time.Time
	BulanTertunggak int
}

// LonjakanHarian adalah satu baris bunching_harian.parquet (grafik uji lonjakan hari ke-45).
type LonjakanHarian struct {
	CaraMasuk  string  `json:"cara_masuk"`
	Hari       int     `json:"hari"`
	Hitung     int     `json:"hitung"`
	CF         float64 `json:"cf"`
	Jendela    string  `json:"jendela"`
	DipakaiFit bool    `json:"dipakai_fit"`
}

// LonjakanRingkasan adalah satu baris bunching_ringkasan.parquet, dikunci cara_masuk ("terjadwal", "IGD").
type LonjakanRingkasan struct {
	NKasus           int      `json:"n_kasus"`
	NHari0           int      `json:"n_hari0"`
	Lebih            float64  `json:"lebih"`
	LebihIKBawah     float64  `json:"lebih_ik_bawah"`
	LebihIKAtas      float64  `json:"lebih_ik_atas"`
	Kurang           float64  `json:"kurang"`
	Lompat           float64  `json:"lompat"`
	LompatIKBawah    float64  `json:"lompat_ik_bawah"`
	LompatIKAtas     float64  `json:"lompat_ik_atas"`
	IKLompatMencakup bool     `json:"ik_lompat_mencakup_0"`
	DendaTerhindarRp *float64 `json:"denda_terhindar_rp"`
	BatasHari        int      `json:"batas_hari"`
	NBootstrap       int      `json:"n_bootstrap"`
}

// SkorVerifikasi adalah satu baris bukti/hasil/skor_verifikasi.csv.
type SkorVerifikasi struct {
	ID   string
	Skor float64
	Rute string
}

// BebanStrata adalah satu baris bukti/hasil/beban_strata.csv (kolom strata = Dimensi).
type BebanStrata struct {
	Dimensi      string
	Kelompok     string
	NPeserta     int
	NJalur       int
	PorsiJalur   float64
	RasioKeRata2 float64
}

// Store menyimpan seluruh data di memori. Hanya dibaca setelah Muat, jadi aman dipakai banyak goroutine.
type Store struct {
	Manifest          Manifest
	Peserta           []*Peserta // urutan peserta.parquet
	LonjakanHarian    []LonjakanHarian
	LonjakanRingkasan map[string]LonjakanRingkasan
	SkorVerifikasi    []SkorVerifikasi // urut id_peserta (pra-registrasi 3a)
	BebanStrata       []BebanStrata    // urutan berkas

	indeks map[string]*Peserta
	status map[string][]Status
	bayar  map[string][]Bayar
	klaim  map[string][]Klaim
	reakt  map[string][]Reaktivasi
}

// Cari mengembalikan peserta dengan ID persis (sudah dinormalkan, mis. "P-002329"), atau nil.
func (s *Store) Cari(id string) *Peserta { return s.indeks[id] }

// Status mengembalikan riwayat status peserta, urut tanggal mulai.
func (s *Store) Status(id string) []Status { return s.status[id] }

// Bayar mengembalikan pembayaran iuran peserta, urut tanggal bayar.
func (s *Store) Bayar(id string) []Bayar { return s.bayar[id] }

// Klaim mengembalikan klaim peserta, urut tanggal masuk.
func (s *Store) Klaim(id string) []Klaim { return s.klaim[id] }

// Reaktivasi mengembalikan reaktivasi peserta, urut tanggal.
func (s *Store) Reaktivasi(id string) []Reaktivasi { return s.reakt[id] }
