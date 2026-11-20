// Package akun berisi akun demo TEPAT (peran Pusat dan Cabang) dan pembatasan wilayahnya.
// Tanpa kata sandi; semua data sintetis. Untuk pilot, masuk lewat SSO BPJS (di luar prototipe ini).
package akun

import (
	"fmt"
	"slices"
)

// Peran akun.
const (
	Pusat  = "pusat"
	Cabang = "cabang"
)

// Akun adalah satu akun demo.
type Akun struct {
	Kunci   string   `json:"kunci"`
	Nama    string   `json:"nama"`
	Peran   string   `json:"peran"`
	Wilayah []string `json:"wilayah"`
}

// Pembagian wilayah ilustratif, sama dengan akun.py. Peserta demo P-002329 (W06), P-005882 (W29),
// P-004192 (W36) ada di Kantor Cabang A. Empat cabang membagi 40 wilayah, masing-masing 10.
var (
	cabangA = []string{"W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08", "W29", "W36"}
	cabangB = []string{"W09", "W10", "W11", "W12", "W13", "W14", "W15", "W16", "W17", "W18"}
	cabangC = []string{"W19", "W20", "W21", "W22", "W23", "W24", "W25", "W26", "W27", "W28"}
	cabangD = []string{"W30", "W31", "W32", "W33", "W34", "W35", "W37", "W38", "W39", "W40"}
)

// SemuaWilayah W01..W40.
var SemuaWilayah = func() []string {
	w := make([]string, 40)
	for i := range w {
		w[i] = fmt.Sprintf("W%02d", i+1)
	}
	return w
}()

// Daftar akun demo, urutan tampil di halaman Masuk.
var Daftar = []Akun{
	{"pusat", "Kantor Pusat · Manajemen Kolektibilitas", Pusat, SemuaWilayah},
	{"cabang_a", "Kantor Cabang A (contoh)", Cabang, cabangA},
	{"cabang_b", "Kantor Cabang B (contoh)", Cabang, cabangB},
	{"cabang_c", "Kantor Cabang C (contoh)", Cabang, cabangC},
	{"cabang_d", "Kantor Cabang D (contoh)", Cabang, cabangD},
}

// Cari akun menurut kunci.
func Cari(kunci string) (Akun, bool) {
	i := slices.IndexFunc(Daftar, func(a Akun) bool { return a.Kunci == kunci })
	if i < 0 {
		return Akun{}, false
	}
	return Daftar[i], true
}

// AdalahPusat melaporkan apakah akun berperan Pusat.
func (a Akun) AdalahPusat() bool { return a.Peran == Pusat }

// Boleh melaporkan apakah akun boleh membuka peserta di wilayah itu.
func (a Akun) Boleh(kodeWilayah string) bool {
	return a.AdalahPusat() || slices.Contains(a.Wilayah, kodeWilayah)
}

// WilayahEfektif adalah wilayah yang dipakai menyaring data. Pusat: pilihan apa adanya (kosong = semua).
// Cabang: pilihan yang masih di wilayahnya; kosong = semua wilayah cabang itu.
func (a Akun) WilayahEfektif(pilihan []string) []string {
	if a.AdalahPusat() {
		return append([]string{}, pilihan...)
	}
	sah := []string{}
	for _, w := range pilihan {
		if slices.Contains(a.Wilayah, w) {
			sah = append(sah, w)
		}
	}
	if len(sah) == 0 {
		return slices.Clone(a.Wilayah)
	}
	return sah
}
