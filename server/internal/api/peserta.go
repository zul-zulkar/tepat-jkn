package api

import (
	"net/http"
	"slices"

	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
	"github.com/zul-zulkar/tepat-jkn/server/internal/pesan"
	"github.com/zul-zulkar/tepat-jkn/server/internal/triase"
)

type responPeserta struct {
	ID                 string       `json:"id"`
	TglDaftar          string       `json:"tgl_daftar"`
	Kelas              int          `json:"kelas"`
	Segmen             string       `json:"segmen"`
	KodeWilayah        string       `json:"kode_wilayah"`
	IuranBulanan       int          `json:"iuran_bulanan"`
	Autodebet          bool         `json:"autodebet"`
	RentangDesil       string       `json:"rentang_desil"`
	StatusAkhir        string       `json:"status_akhir"`
	StatusSejak        *string      `json:"status_sejak"`
	Rute               string       `json:"rute"`
	Alasan             string       `json:"alasan"`
	TunggakanBulan     int          `json:"tunggakan_bulan"`
	TunggakanRp        int          `json:"tunggakan_rp"`
	NReaktivasi        int          `json:"n_reaktivasi"`
	NReaktTerkaitKlaim int          `json:"n_reakt_terkait_klaim"`
	RasioHariAktif     float64      `json:"rasio_hari_aktif"`
	RasioKlaimIuran    *float64     `json:"rasio_klaim_iuran"`
	KlaimRp            float64      `json:"klaim_rp"`
	IuranRp            float64      `json:"iuran_rp"`
	EW                 *responEW    `json:"ew"`
	Utama              string       `json:"utama"`
	MasukEW            bool         `json:"masuk_ew"`
	NEWDaftar          int          `json:"n_ew_daftar"`
	Juga               []string     `json:"juga"`
	Linimasa           linimasa     `json:"linimasa"`
	Draf               []pesan.Draf `json:"draf"`
	Keputusan          *Keputusan   `json:"keputusan"`
}

type responEW struct {
	Skor       float64           `json:"skor"`
	Peringkat  int               `json:"peringkat"`
	NDinilai   int               `json:"n_dinilai"`
	Bulan      string            `json:"bulan"`
	Alasan     string            `json:"alasan"`
	Saran      string            `json:"saran"`
	Kontribusi []data.Kontribusi `json:"kontribusi"`
}

type linimasa struct {
	Status   []map[string]any  `json:"status"`
	Bayar    []map[string]any  `json:"bayar"`
	Klaim    []map[string]any  `json:"klaim"`
	Reakt    []map[string]any  `json:"reaktivasi"`
	Pasangan []triase.Pasangan `json:"pasangan"`
}

func (s *Server) peserta(w http.ResponseWriter, r *http.Request) {
	id := NormalkanID(r.PathValue("id"))
	p := s.data.Cari(id)
	if p == nil {
		galat(w, http.StatusNotFound, "tidak_ada")
		return
	}
	l := s.lingkup(r)
	if !l.akun.Boleh(p.KodeWilayah) {
		galat(w, http.StatusForbidden, "di_luar_wilayah")
		return
	}
	utama := l.utama(p)
	out := responPeserta{ID: p.ID, TglDaftar: tgl(p.TglDaftar), Kelas: p.Kelas, Segmen: p.Segmen,
		KodeWilayah: p.KodeWilayah, IuranBulanan: p.IuranBulanan, Autodebet: p.Autodebet,
		RentangDesil: p.RentangDesil, StatusAkhir: p.StatusAkhir, Rute: p.Rute, Alasan: p.Alasan,
		TunggakanBulan: p.TunggakanBulan, TunggakanRp: p.TunggakanRp, NReaktivasi: p.NReaktivasi,
		NReaktTerkaitKlaim: p.NReaktTerkaitKlaim, RasioHariAktif: p.RasioHariAktif,
		RasioKlaimIuran: p.RasioKlaimIuran, KlaimRp: p.KlaimRp, IuranRp: p.IuranRp,
		Utama: utama, MasukEW: l.masukEW[p.ID], NEWDaftar: len(l.ew), Juga: []string{},
		Draf: pesan.Template(untukPesan(p), utama)}
	if kep, ok := l.keputusan[p.ID]; ok {
		out.Keputusan = &kep
	}
	if p.Rute != triase.TanpaTindakan && p.Rute != utama {
		out.Juga = append(out.Juga, p.Rute)
	}
	if out.MasukEW && utama != triase.PeringatanDini {
		out.Juga = append(out.Juga, triase.PeringatanDini)
	}
	if e := p.EW; e != nil {
		out.EW = &responEW{Skor: e.Skor, Peringkat: e.Peringkat, NDinilai: s.data.Manifest.EWNDinilai,
			Bulan: e.Bulan, Alasan: e.Alasan, Saran: e.Saran, Kontribusi: tigaTerbesar(e.Kontribusi)}
	}

	st := s.data.Status(p.ID)
	if len(st) > 0 {
		sejak := tgl(st[len(st)-1].Mulai)
		out.StatusSejak = &sejak
	}
	lm := linimasa{Status: []map[string]any{}, Bayar: []map[string]any{}, Klaim: []map[string]any{},
		Reakt: []map[string]any{}}
	for _, x := range st {
		lm.Status = append(lm.Status, map[string]any{"mulai": tgl(x.Mulai), "selesai": tgl(x.Selesai), "status": x.Status})
	}
	for _, x := range s.data.Bayar(p.ID) {
		lm.Bayar = append(lm.Bayar, map[string]any{"tgl": tgl(x.Tanggal), "periode_awal": x.PeriodeAwal,
			"periode_akhir": x.PeriodeAkhir, "jumlah_bulan": x.JumlahBulan, "nominal": x.Nominal, "kanal": x.Kanal})
	}
	klaim := s.data.Klaim(p.ID)
	for _, x := range klaim {
		lm.Klaim = append(lm.Klaim, map[string]any{"tgl_masuk": tgl(x.TglMasuk), "jenis_layanan": x.JenisLayanan,
			"cara_masuk": x.CaraMasuk, "kelompok_layanan": x.KelompokLayanan, "biaya": x.BiayaKlaim,
			"denda": x.DendaPelayanan})
	}
	reakt := s.data.Reaktivasi(p.ID)
	for _, x := range reakt {
		lm.Reakt = append(lm.Reakt, map[string]any{"tgl": tgl(x.Tanggal), "bulan_tertunggak": x.BulanTertunggak})
	}
	lm.Pasangan = triase.PasanganReaktivasiKlaim(reakt, klaim)
	out.Linimasa = lm
	kirimJSON(w, out)
}

// tigaTerbesar: tiga kontribusi positif terbesar (urutan kolom dipertahankan bila seri).
func tigaTerbesar(xs []data.Kontribusi) []data.Kontribusi {
	var pos []data.Kontribusi
	for _, k := range xs {
		if k.Nilai > 0 {
			pos = append(pos, k)
		}
	}
	slices.SortStableFunc(pos, func(a, b data.Kontribusi) int {
		switch {
		case a.Nilai > b.Nilai:
			return -1
		case a.Nilai < b.Nilai:
			return 1
		}
		return 0
	})
	if len(pos) > 3 {
		pos = pos[:3]
	}
	if pos == nil {
		pos = []data.Kontribusi{}
	}
	return pos
}

func (s *Server) contoh(w http.ResponseWriter, r *http.Request) {
	l := s.lingkup(r)
	type item struct {
		ID       string `json:"id"`
		Tindakan string `json:"tindakan"`
	}
	hasil := []item{}
	for _, rute := range triase.RuteAksi {
		var pilih *data.Peserta
		for _, p := range l.semua {
			if p.Rute != rute || (rute == triase.Pengingat && p.TunggakanBulan <= 0) {
				continue
			}
			if pilih == nil || p.TunggakanRp > pilih.TunggakanRp || (p.TunggakanRp == pilih.TunggakanRp && p.ID < pilih.ID) {
				pilih = p
			}
		}
		if pilih != nil {
			hasil = append(hasil, item{pilih.ID, rute})
		}
	}
	for _, p := range l.semua {
		if p.EW != nil && p.EW.Peringkat == 1 {
			hasil = append(hasil, item{p.ID, triase.PeringatanDini})
			break
		}
	}
	kirimJSON(w, hasil)
}
