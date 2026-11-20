package api

import (
	"context"
	"net/http"

	"github.com/zul-zulkar/tepat-jkn/server/internal/akun"
	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
	"github.com/zul-zulkar/tepat-jkn/server/internal/pesan"
	"github.com/zul-zulkar/tepat-jkn/server/internal/triase"
)

type konteksAkun struct{}

func (s *Server) perluAkun(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ss := s.sesi.ambil(w, r)
		a, _, _ := ss.salin()
		if a == nil {
			galat(w, http.StatusUnauthorized, "belum_masuk")
			return
		}
		h(w, r.WithContext(context.WithValue(r.Context(), konteksAkun{}, ss)))
	}
}

func (s *Server) perluPusat(h http.HandlerFunc) http.HandlerFunc {
	return s.perluAkun(func(w http.ResponseWriter, r *http.Request) {
		if a, _, _ := sesiDari(r).salin(); !a.AdalahPusat() {
			galat(w, http.StatusForbidden, "khusus_pusat")
			return
		}
		h(w, r)
	})
}

func sesiDari(r *http.Request) *sesi { return r.Context().Value(konteksAkun{}).(*sesi) }

type responSesi struct {
	Akun       *akun.Akun     `json:"akun"`
	K          int            `json:"k"`
	DaftarAkun []akun.Akun    `json:"daftar_akun"`
	Manifest   data.Manifest  `json:"manifest"`
	AI         statusAI       `json:"ai"`
	Konstanta  map[string]int `json:"konstanta"`
}

type statusAI struct {
	Tersedia   bool    `json:"tersedia"`
	Alasan     string  `json:"alasan"`
	BatasWaktu float64 `json:"batas_waktu"`
}

func aiSekarang() statusAI {
	ok, alasan := pesan.AITersedia()
	return statusAI{Tersedia: ok, Alasan: alasan, BatasWaktu: pesan.BatasWaktu()}
}

func (s *Server) tulisSesi(w http.ResponseWriter, ss *sesi) {
	a, k, _ := ss.salin()
	kirimJSON(w, responSesi{Akun: a, K: k, DaftarAkun: akun.Daftar, Manifest: s.data.Manifest, AI: aiSekarang(),
		Konstanta: map[string]int{"klaim_besar": triase.KlaimBesar, "jeda_kait": triase.JedaKait,
			"derajat": triase.Derajat}})
}

func (s *Server) lihatSesi(w http.ResponseWriter, r *http.Request) {
	s.tulisSesi(w, s.sesi.ambil(w, r))
}

func (s *Server) masuk(w http.ResponseWriter, r *http.Request) {
	var in struct {
		Akun string `json:"akun"`
	}
	if !bacaJSON(w, r, &in) {
		return
	}
	a, ok := akun.Cari(in.Akun)
	if !ok {
		galat(w, http.StatusBadRequest, "akun_tidak_dikenal")
		return
	}
	ss := s.sesi.ambil(w, r)
	ss.mu.Lock()
	ss.akun = &a
	ss.mu.Unlock()
	s.tulisSesi(w, ss)
}

func (s *Server) keluar(w http.ResponseWriter, r *http.Request) {
	ss := s.sesi.ambil(w, r)
	ss.mu.Lock()
	ss.akun = nil
	ss.mu.Unlock()
	s.tulisSesi(w, ss)
}

func (s *Server) aturKapasitas(w http.ResponseWriter, r *http.Request) {
	ss := sesiDari(r)
	if a, _, _ := ss.salin(); !a.AdalahPusat() {
		galat(w, http.StatusForbidden, "kapasitas_ditetapkan_pusat")
		return
	}
	var in struct {
		K int `json:"k"`
	}
	if !bacaJSON(w, r, &in) {
		return
	}
	if in.K < 1 || in.K > 20 {
		galat(w, http.StatusBadRequest, "k_di_luar_1_20")
		return
	}
	ss.mu.Lock()
	ss.k = in.K
	ss.mu.Unlock()
	s.tulisSesi(w, ss)
}

// lingkup: peserta yang boleh dilihat akun, wilayah efektif, daftar peringatan dini, dan tindakan utama.
