package akun

import (
	"slices"
	"testing"
)

func TestCabangMembagiSemuaWilayah(t *testing.T) {
	var gabung []string
	for _, a := range Daftar {
		if a.Peran == Cabang {
			gabung = append(gabung, a.Wilayah...)
		}
	}
	slices.Sort(gabung)
	if !slices.Equal(gabung, SemuaWilayah) {
		t.Fatalf("wilayah cabang tidak membagi W01..W40 tepat sekali: %v", gabung)
	}
}

func TestWilayahEfektif(t *testing.T) {
	a, _ := Cari("cabang_a")
	if got := a.WilayahEfektif([]string{"W09", "W06"}); !slices.Equal(got, []string{"W06"}) {
		t.Errorf("cabang hanya boleh wilayahnya: %v", got)
	}
	if got := a.WilayahEfektif(nil); !slices.Equal(got, a.Wilayah) {
		t.Errorf("cabang tanpa pilihan = semua wilayahnya: %v", got)
	}
	p, _ := Cari("pusat")
	if got := p.WilayahEfektif(nil); len(got) != 0 {
		t.Errorf("pusat tanpa pilihan = semua (kosong): %v", got)
	}
	if !p.Boleh("W40") || a.Boleh("W40") || !a.Boleh("W36") {
		t.Error("aturan Boleh salah")
	}
}
