// Package triase menerapkan aturan "satu peserta, satu tindakan" di atas rute dan skor yang sudah
// dihitung pipeline Python. Tidak ada aturan rute baru di sini; hanya urutan prioritas (tepat_ui.PRIORITAS),
// pemotongan daftar peringatan dini ke kapasitas k, dan pasangan reaktivasi-klaim untuk linimasa.
package triase

import (
	"math"
	"slices"
	"time"

	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
)

// Kode rute triase (kolom rute di daftar_kerja.parquet) dan kode tindakan peringatan dini.
const (
	Verifikasi     = "verifikasi_pola_reaktivasi"
	CekPBI         = "rujuk_cek_kelayakan_PBI"
	Pengingat      = "pengingat_autodebet_REHAB"
	NonaktifLama   = "nonaktif_lama_tanpa_sinyal"
	TanpaTindakan  = "tanpa_tindakan"
	PeringatanDini = "peringatan_dini"
)

// Konstanta yang sama dengan cek_sinyal.py. Uji paket ini mencocokkannya dengan berkas Python.
const (
	KlaimBesar = 1_000_000 // RITL apa pun, atau RJTL >= Rp1 juta
	JedaKait   = 90        // reaktivasi "terkait" bila klaim besar <= 90 hari sesudahnya
	Derajat    = 4         // derajat kurva perkiraan uji lonjakan
)

// Rute adalah urutan tampil rute triase; RuteAksi tanpa "tanpa_tindakan".
var (
	Rute     = []string{Verifikasi, CekPBI, Pengingat, NonaktifLama, TanpaTindakan}
	RuteAksi = []string{Verifikasi, CekPBI, Pengingat, NonaktifLama}
)

// Prioritas satu peserta, satu tindakan (disepakati 24 Okt 2026). Jawaban "ya" pertama menang.
var Prioritas = []string{Verifikasi, CekPBI, NonaktifLama, PeringatanDini, Pengingat}

// UrutRute memberi posisi rute di Rute (untuk pengurutan daftar kerja).
func UrutRute(r string) int { return slices.Index(Rute, r) }

// TindakanUtama memilih satu tindakan menurut Prioritas. masukEW: peserta masuk daftar peringatan dini
// pada kapasitas dan filter wilayah yang sedang dipakai.
func TindakanUtama(rute string, masukEW bool) string {
	for _, t := range Prioritas {
		if (t == PeringatanDini && masukEW) || (t != PeringatanDini && rute == t) {
			return t
		}
	}
	return TanpaTindakan
}

// DaftarEW adalah peserta aktif yang dinilai model, di wilayah terpilih (kosong = semua), urut peringkat,
// dipotong ke k persen. Aturan k sama dengan siapkan_app.py: max(1, round(n * k / 100)), round Python
// (setengah ke genap). Mengembalikan daftar dan jumlah yang dinilai.
func DaftarEW(semua []*data.Peserta, wilayah map[string]bool, kPersen int) ([]*data.Peserta, int) {
	var d []*data.Peserta
	for _, p := range semua {
		if p.EW != nil && (len(wilayah) == 0 || wilayah[p.KodeWilayah]) {
			d = append(d, p)
		}
	}
	slices.SortStableFunc(d, func(a, b *data.Peserta) int { return a.EW.Peringkat - b.EW.Peringkat })
	n := len(d)
	if n == 0 {
		return nil, 0
	}
	k := max(1, int(math.RoundToEven(float64(n)*float64(kPersen)/100)))
	return d[:min(k, n)], n
}

// Pasangan adalah satu reaktivasi dengan klaim besar PERTAMA pada/sesudah tanggalnya (merge_asof forward
// di cek_sinyal.fitur_peserta). Terkait bila jaraknya paling lama JedaKait hari.
type Pasangan struct {
	TglReakt     time.Time  `json:"tgl_reakt"`
	TglMasuk     *time.Time `json:"tgl_masuk"`
	JenisLayanan string     `json:"jenis_layanan"`
	CaraMasuk    string     `json:"cara_masuk"`
	Hari         *int       `json:"hari"`
	Terkait      bool       `json:"terkait"`
}

// KlaimBesarKah: rawat inap apa pun, atau klaim lain dengan biaya paling sedikit KlaimBesar.
func KlaimBesarKah(k data.Klaim) bool { return k.JenisLayanan == "RITL" || k.BiayaKlaim >= KlaimBesar }

// PasanganReaktivasiKlaim memasangkan tiap reaktivasi (urut tanggal) dengan klaim besar berikutnya.
func PasanganReaktivasiKlaim(reakt []data.Reaktivasi, klaim []data.Klaim) []Pasangan {
	var besar []data.Klaim
	for _, k := range klaim {
		if KlaimBesarKah(k) {
			besar = append(besar, k)
		}
	}
	slices.SortStableFunc(besar, func(a, b data.Klaim) int { return a.TglMasuk.Compare(b.TglMasuk) })
	hasil := make([]Pasangan, 0, len(reakt))
	for _, r := range reakt {
		ps := Pasangan{TglReakt: r.Tanggal}
		i, _ := slices.BinarySearchFunc(besar, r.Tanggal, func(k data.Klaim, t time.Time) int { return k.TglMasuk.Compare(t) })
		if i < len(besar) {
			k := besar[i]
			hari := int(k.TglMasuk.Sub(r.Tanggal).Hours() / 24)
			ps.TglMasuk, ps.JenisLayanan, ps.CaraMasuk, ps.Hari = &k.TglMasuk, k.JenisLayanan, k.CaraMasuk, &hari
			ps.Terkait = hari <= JedaKait
		}
		hasil = append(hasil, ps)
	}
	return hasil
}
