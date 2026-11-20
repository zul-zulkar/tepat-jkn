package api

import (
	"fmt"
	"net/http"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/zul-zulkar/tepat-jkn/server/internal/akun"
	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
	"github.com/zul-zulkar/tepat-jkn/server/internal/triase"
)

type lingkup struct {
	akun      akun.Akun
	k         int
	semua     []*data.Peserta // peserta akun (cabang: wilayahnya saja)
	wilayah   []string        // wilayah efektif; kosong = semua
	terpilih  []*data.Peserta // peserta di wilayah efektif
	ew        []*data.Peserta // daftar peringatan dini pada kapasitas k
	nDinilai  int
	masukEW   map[string]bool
	keputusan map[string]Keputusan
}

func (s *Server) lingkup(r *http.Request) lingkup {
	a, k, kep := sesiDari(r).salin()
	l := lingkup{akun: *a, k: k, keputusan: kep, masukEW: map[string]bool{}}
	for _, p := range s.data.Peserta {
		if a.AdalahPusat() || slices.Contains(a.Wilayah, p.KodeWilayah) {
			l.semua = append(l.semua, p)
		}
	}
	var pilihan []string
	for _, w := range strings.Split(r.URL.Query().Get("wilayah"), ",") {
		if w = strings.TrimSpace(w); w != "" {
			pilihan = append(pilihan, w)
		}
	}
	l.wilayah = a.WilayahEfektif(pilihan)
	set := map[string]bool{}
	for _, w := range l.wilayah {
		set[w] = true
	}
	for _, p := range l.semua {
		if len(set) == 0 || set[p.KodeWilayah] {
			l.terpilih = append(l.terpilih, p)
		}
	}
	l.ew, l.nDinilai = triase.DaftarEW(l.semua, set, k)
	for _, p := range l.ew {
		l.masukEW[p.ID] = true
	}
	return l
}

func (l lingkup) utama(p *data.Peserta) string { return triase.TindakanUtama(p.Rute, l.masukEW[p.ID]) }

type barisTriase struct {
	ID             string `json:"id"`
	Rute           string `json:"rute"`
	Alasan         string `json:"alasan"`
	StatusAkhir    string `json:"status_akhir"`
	TunggakanBulan int    `json:"tunggakan_bulan"`
	TunggakanRp    int    `json:"tunggakan_rp"`
	KodeWilayah    string `json:"kode_wilayah"`
	RentangDesil   string `json:"rentang_desil"`
	JugaEW         bool   `json:"juga_ew"`
}

type barisEW struct {
	Urut        int     `json:"urut"`
	Peringkat   int     `json:"peringkat"`
	ID          string  `json:"id"`
	Skor        float64 `json:"skor"`
	Alasan      string  `json:"alasan"`
	Saran       string  `json:"saran"`
	KodeWilayah string  `json:"kode_wilayah"`
	Rute        string  `json:"rute"`
}

func (s *Server) daftar(w http.ResponseWriter, r *http.Request) {
	l := s.lingkup(r)
	jumlah := map[string]int{}
	var tri []barisTriase
	pindah := 0
	for _, p := range l.terpilih {
		u := l.utama(p)
		jumlah[u]++
		if p.Rute == triase.Pengingat && u == triase.PeringatanDini {
			pindah++
		}
		if slices.Contains(triase.RuteAksi, u) {
			tri = append(tri, barisTriase{ID: p.ID, Rute: p.Rute, Alasan: p.Alasan, StatusAkhir: p.StatusAkhir,
				TunggakanBulan: p.TunggakanBulan, TunggakanRp: p.TunggakanRp, KodeWilayah: p.KodeWilayah,
				RentangDesil: p.RentangDesil, JugaEW: l.masukEW[p.ID]})
		}
	}
	// urut rute, tunggakan terbesar, lalu ID (halaman/daftar_kerja.py)
	slices.SortStableFunc(tri, func(a, b barisTriase) int {
		if d := triase.UrutRute(a.Rute) - triase.UrutRute(b.Rute); d != 0 {
			return d
		}
		if a.TunggakanRp != b.TunggakanRp {
			return b.TunggakanRp - a.TunggakanRp
		}
		return strings.Compare(a.ID, b.ID)
	})
	ew := []barisEW{}
	for i, p := range l.ew {
		if l.utama(p) == triase.PeringatanDini {
			ew = append(ew, barisEW{Urut: i + 1, Peringkat: p.EW.Peringkat, ID: p.ID, Skor: p.EW.Skor,
				Alasan: p.EW.Alasan, Saran: p.EW.Saran, KodeWilayah: p.KodeWilayah, Rute: p.Rute})
		}
	}
	tersedia := slices.Clone(l.akun.Wilayah)
	if l.akun.AdalahPusat() {
		ada := map[string]bool{}
		tersedia = nil
		for _, p := range l.semua {
			if !ada[p.KodeWilayah] {
				ada[p.KodeWilayah] = true
				tersedia = append(tersedia, p.KodeWilayah)
			}
		}
		slices.Sort(tersedia)
	}
	if tri == nil {
		tri = []barisTriase{}
	}
	kirimJSON(w, map[string]any{
		"k": l.k, "total": len(l.terpilih), "jumlah_utama": jumlah, "pindah": pindah,
		"n_dinilai": l.nDinilai, "n_ew_daftar": len(l.ew), "triase": tri, "ew": ew,
		"keputusan": l.keputusan, "wilayah_tersedia": tersedia, "wilayah_efektif": l.wilayah,
	})
}

var polaID = regexp.MustCompile(`^(?:P-?)?(\d{1,6})$`)

// NormalkanID: "2329", "p2329", "P-2329" jadi "P-002329" (tepat_ui.normalkan_id).
func NormalkanID(s string) string {
	s = strings.ToUpper(strings.ReplaceAll(strings.TrimSpace(s), " ", ""))
	if m := polaID.FindStringSubmatch(s); m != nil {
		n, _ := strconv.Atoi(m[1])
		return fmt.Sprintf("P-%06d", n)
	}
	return s
}

func tgl(t time.Time) string { return t.Format(time.DateOnly) }
