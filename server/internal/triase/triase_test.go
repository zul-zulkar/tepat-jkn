package triase

import (
	"os"
	"regexp"
	"strconv"
	"strings"
	"testing"

	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
)

// Konstanta harus sama dengan cek_sinyal.py (satu sumber aturan "klaim besar").
func TestKonstantaSamaDenganPython(t *testing.T) {
	isi, err := os.ReadFile("../../../cek_sinyal.py")
	if err != nil {
		t.Skip("cek_sinyal.py tidak ada:", err)
	}
	for nama, harap := range map[string]int{"KLAIM_BESAR": KlaimBesar, "JEDA_KAIT": JedaKait, "DERAJAT": Derajat} {
		m := regexp.MustCompile(`(?m)^` + nama + `\s*=\s*([\d_]+)`).FindSubmatch(isi)
		if m == nil {
			t.Fatalf("%s tidak ditemukan di cek_sinyal.py", nama)
		}
		v, _ := strconv.Atoi(strings.ReplaceAll(string(m[1]), "_", ""))
		if v != harap {
			t.Errorf("%s: Go %d, Python %d", nama, harap, v)
		}
	}
}

func TestTindakanUtama(t *testing.T) {
	kasus := []struct {
		rute    string
		masukEW bool
		harap   string
	}{
		{Verifikasi, true, Verifikasi},
		{CekPBI, true, CekPBI},
		{NonaktifLama, false, NonaktifLama},
		{Pengingat, true, PeringatanDini},
		{Pengingat, false, Pengingat},
		{TanpaTindakan, true, PeringatanDini},
		{TanpaTindakan, false, TanpaTindakan},
	}
	for _, k := range kasus {
		if got := TindakanUtama(k.rute, k.masukEW); got != k.harap {
			t.Errorf("TindakanUtama(%s, %v) = %s, harap %s", k.rute, k.masukEW, got, k.harap)
		}
	}
}

// k = max(1, round(n * k / 100)) dengan round Python (setengah ke genap): 50 peserta x 5% = 2,5 -> 2.
func TestDaftarEWPembulatan(t *testing.T) {
	var ps []*data.Peserta
	for i := range 50 {
		ps = append(ps, &data.Peserta{ID: strconv.Itoa(i), EW: &data.EW{Peringkat: 50 - i}})
	}
	for _, k := range []struct{ persen, harap int }{{5, 2}, {1, 1}, {3, 2}, {7, 4}, {20, 10}} {
		d, n := DaftarEW(ps, nil, k.persen)
		if n != 50 || len(d) != k.harap {
			t.Errorf("k=%d%%: %d orang, harap %d", k.persen, len(d), k.harap)
		}
		if len(d) > 0 && d[0].EW.Peringkat != 1 {
			t.Errorf("daftar harus urut peringkat")
		}
	}
}
