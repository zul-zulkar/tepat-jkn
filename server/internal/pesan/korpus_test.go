package pesan

import (
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"os"
	"reflect"
	"slices"
	"testing"
)

// Korpus dibuat server/uji/korpus_pesan.py dari llm.py dan pesan_template.py: semua panggilan selama uji_llm.py
// berjalan, ditambah variasi buatan. Tiap kasus harus memberi jawaban yang sama persis di Go.

type pesertaKorpus struct {
	ID             string   `json:"id_peserta"`
	Rute           string   `json:"rute"`
	Alasan         *string  `json:"alasan"`
	AlasanRapi     *string  `json:"alasan_rapi"`
	TunggakanBulan int      `json:"tunggakan_bulan"`
	TunggakanRp    float64  `json:"tunggakan_rp"`
	IuranBulanan   float64  `json:"iuran_bulanan"`
	Autodebet      bool     `json:"autodebet"`
	EWSkor         *float64 `json:"ew_skor"`
	EWAlasan       *string  `json:"ew_alasan"`
	EWSaran        *string  `json:"ew_saran"`
}

func (k pesertaKorpus) peserta() Peserta {
	s := func(p *string) string {
		if p == nil {
			return ""
		}
		return *p
	}
	return Peserta{ID: k.ID, Rute: k.Rute, Alasan: s(k.Alasan), AlasanRapi: s(k.AlasanRapi),
		TunggakanBulan: k.TunggakanBulan, TunggakanRp: k.TunggakanRp, IuranBulanan: k.IuranBulanan,
		Autodebet: k.Autodebet, EWSkor: k.EWSkor, EWAlasan: s(k.EWAlasan), EWSaran: s(k.EWSaran)}
}

type korpus struct {
	Periksa []struct {
		Teks      string   `json:"teks"`
		Kode      string   `json:"kode"`
		Bulan     int      `json:"bulan"`
		Nominal   []int    `json:"nominal"`
		OpsiBoleh []string `json:"opsi_boleh"`
		Hasil     []string `json:"hasil"`
	} `json:"periksa"`
	Rapikan []struct {
		Teks  string `json:"teks"`
		Hasil string `json:"hasil"`
		N     int    `json:"n"`
	} `json:"rapikan"`
	Bersihkan []struct{ Teks, Hasil string } `json:"bersihkan"`
	Ringkasan []struct {
		Teks  string   `json:"teks"`
		Hasil []string `json:"hasil"`
	} `json:"ringkasan"`
	Opsi []struct {
		Teks  string   `json:"teks"`
		Hasil []string `json:"hasil"`
	} `json:"opsi"`
	Templat []struct {
		P        pesertaKorpus `json:"p"`
		Tindakan string        `json:"tindakan"`
		Draf     []Draf        `json:"draf"`
	} `json:"templat"`
	Sistem map[string]string `json:"sistem"`
	Urai   []struct {
		Mentah string            `json:"mentah"`
		Hasil  map[string]string `json:"hasil"`
		Galat  string            `json:"galat"`
		Rinci  string            `json:"rinci"`
	} `json:"urai"`
	Susun []struct {
		P        pesertaKorpus     `json:"p"`
		Tindakan string            `json:"tindakan"`
		PakaiAI  bool              `json:"pakai_ai"`
		Env      map[string]string `json:"env"`
		Klien    bool              `json:"klien"`
		Sistem   *string           `json:"sistem"`
		Masukan  *string           `json:"masukan"`
		Balas    *string           `json:"balas"`
		Galat    *struct {
			Kode, Rinci, Lain string
		} `json:"galat"`
		Hasil struct {
			Status, Cadangan, Rinci, Ringkasan, Keterangan string
			Draf                                           []Draf
			Dirapikan                                      int
		} `json:"hasil"`
	} `json:"susun"`
}

func bacaKorpus(t *testing.T) korpus {
	t.Helper()
	f, err := os.Open("testdata/korpus.json.gz")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		t.Fatal(err)
	}
	var k korpus
	if err := json.NewDecoder(gz).Decode(&k); err != nil {
		t.Fatal(err)
	}
	return k
}

func kosongJikaNil(xs []string) []string {
	if xs == nil {
		return []string{}
	}
	return xs
}

func TestKorpusAturan(t *testing.T) {
	k := bacaKorpus(t)
	beda := 0
	for _, c := range k.Periksa {
		var opsi []string
		if c.OpsiBoleh != nil {
			opsi = c.OpsiBoleh
		}
		got := PeriksaPesanPeserta(c.Teks, c.Kode, c.Bulan, c.Nominal, opsi)
		if !slices.Equal(got, kosongJikaNil(c.Hasil)) {
			if beda++; beda <= 15 {
				t.Errorf("periksa %q [%s]:\n go %v\n py %v", c.Teks, c.Kode, got, c.Hasil)
			}
		}
	}
	for _, c := range k.Ringkasan {
		if got := PeriksaRingkasan(c.Teks); !slices.Equal(kosongJikaNil(got), kosongJikaNil(c.Hasil)) {
			if beda++; beda <= 15 {
				t.Errorf("ringkasan %q: go %v py %v", c.Teks, got, c.Hasil)
			}
		}
	}
	for _, c := range k.Opsi {
		if got := OpsiDalam(c.Teks); !slices.Equal(kosongJikaNil(got), kosongJikaNil(c.Hasil)) {
			if beda++; beda <= 15 {
				t.Errorf("opsi %q: go %v py %v", c.Teks, got, c.Hasil)
			}
		}
	}
	t.Logf("%d periksa, %d ringkasan, %d opsi; %d beda", len(k.Periksa), len(k.Ringkasan), len(k.Opsi), beda)
}

func TestKorpusTeks(t *testing.T) {
	k := bacaKorpus(t)
	beda := 0
	for _, c := range k.Rapikan {
		got, n := RapikanSpasi(c.Teks)
		if got != c.Hasil || n != c.N {
			if beda++; beda <= 15 {
				t.Errorf("rapikan %q:\n go %q (%d)\n py %q (%d)", c.Teks, got, n, c.Hasil, c.N)
			}
		}
	}
	for _, c := range k.Bersihkan {
		if got := BersihkanKarakter(c.Teks); got != c.Hasil {
			if beda++; beda <= 15 {
				t.Errorf("bersihkan %q: go %q py %q", c.Teks, got, c.Hasil)
			}
		}
	}
	t.Logf("%d rapikan, %d bersihkan; %d beda", len(k.Rapikan), len(k.Bersihkan), beda)
}

func TestKorpusTemplatDanPrompt(t *testing.T) {
	k := bacaKorpus(t)
	for _, c := range k.Templat {
		got := Template(c.P.peserta(), c.Tindakan)
		if c.Draf == nil {
			c.Draf = []Draf{}
		}
		if !reflect.DeepEqual(got, c.Draf) {
			t.Errorf("template %s %s:\n go %+v\n py %+v", c.P.ID, c.Tindakan, got, c.Draf)
		}
	}
	for kode, harap := range k.Sistem {
		if got := Sistem(kode); got != harap {
			t.Errorf("prompt sistem %s beda", kode)
		}
	}
	for _, c := range k.Urai {
		got, err := urai(c.Mentah)
		var g *Gagal
		switch {
		case c.Galat != "":
			if !errors.As(err, &g) || g.Kode != c.Galat || g.Rinci != c.Rinci {
				t.Errorf("urai %q: harap galat %s, dapat %v", c.Mentah, c.Galat, err)
			}
		case err != nil || !reflect.DeepEqual(got, c.Hasil):
			t.Errorf("urai %q: go %v %v, py %v", c.Mentah, got, err, c.Hasil)
		}
	}
}

func TestKorpusSusun(t *testing.T) {
	k := bacaKorpus(t)
	for _, v := range []string{"ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "TEPAT_LLM_PROVIDER",
		"TEPAT_LLM_MODEL", "TEPAT_AI_BATAS_HARIAN", "TEPAT_AI_TIMEOUT"} {
		t.Setenv(v, "")
	}
	for i, c := range k.Susun {
		t.Setenv("TEPAT_AI", c.Env["TEPAT_AI"])
		var sistem, masukan string
		o := Opsi{PakaiAI: c.PakaiAI}
		if c.Klien {
			o.Klien = func(_ context.Context, s, m string) (string, error) {
				sistem, masukan = s, m
				switch {
				case c.Galat != nil && c.Galat.Lain != "":
					return "", errors.New(c.Galat.Lain)
				case c.Galat != nil:
					return "", &Gagal{c.Galat.Kode, c.Galat.Rinci}
				case c.Balas != nil:
					return *c.Balas, nil
				}
				return "", errors.New("korpus tanpa balasan")
			}
		}
		h := Susun(context.Background(), c.P.peserta(), c.Tindakan, o)
		w := c.Hasil
		if w.Draf == nil {
			w.Draf = []Draf{}
		}
		lain := c.Galat != nil && c.Galat.Lain != ""
		if h.Status != w.Status || h.Cadangan != w.Cadangan || (!lain && h.Rinci != w.Rinci) ||
			h.RingkasanPetugas != w.Ringkasan || h.Dirapikan != w.Dirapikan || !reflect.DeepEqual(h.Draf, w.Draf) ||
			(!lain && h.Keterangan() != w.Keterangan) {
			t.Errorf("susun #%d %s %s:\n go %s/%s %q rapi=%d %q\n py %s/%s %q rapi=%d %q", i, c.P.ID, c.Tindakan,
				h.Status, h.Cadangan, h.Rinci, h.Dirapikan, h.RingkasanPetugas,
				w.Status, w.Cadangan, w.Rinci, w.Dirapikan, w.Ringkasan)
		}
		if c.Sistem != nil && sistem != *c.Sistem {
			t.Errorf("susun #%d: prompt sistem beda", i)
		}
		if c.Masukan != nil && masukan != *c.Masukan {
			t.Errorf("susun #%d: masukan beda:\n go %s\n py %s", i, masukan, *c.Masukan)
		}
	}
	t.Logf("%d panggilan susun diputar ulang", len(k.Susun))
}
