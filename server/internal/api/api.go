// Package api menyajikan data TEPAT sebagai JSON untuk antarmuka web. Akses dibatasi di server: kantor
// cabang hanya menerima peserta di wilayahnya, dan halaman Kebijakan serta Keadilan hanya untuk Pusat.
package api

import (
	"context"
	"io/fs"
	"net/http"

	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
	"github.com/zul-zulkar/tepat-jkn/server/internal/keadilan"
)

// Server menyatukan data, sesi, dan berkas antarmuka.
type Server struct {
	data     *data.Store
	keadilan keadilan.Hasil
	sesi     *penyimpanSesi
	web      fs.FS
}

// Baru membuat server. web boleh nil (hanya API).
func Baru(s *data.Store, web fs.FS) *Server {
	return &Server{data: s, keadilan: keadilan.Hitung(s), sesi: baruPenyimpan(s.Manifest.EWKPersenDaftar), web: web}
}

// Jaga menjalankan pekerjaan latar (pembersihan sesi lama) sampai ctx selesai.
func (s *Server) Jaga(ctx context.Context) { s.sesi.jagaKebersihan(ctx) }

// Handler mengembalikan semua rute.
func (s *Server) Handler() http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { // tanpa sesi: dipanggil mesin
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write([]byte("ok\n"))
	})
	m.HandleFunc("GET /api/sesi", s.lihatSesi)
	m.HandleFunc("POST /api/masuk", s.masuk)
	m.HandleFunc("POST /api/keluar", s.keluar)
	m.HandleFunc("PUT /api/kapasitas", s.perluAkun(s.aturKapasitas))
	m.HandleFunc("GET /api/daftar", s.perluAkun(s.daftar))
	m.HandleFunc("GET /api/contoh", s.perluAkun(s.contoh))
	m.HandleFunc("GET /api/peserta/{id}", s.perluAkun(s.peserta))
	m.HandleFunc("POST /api/pesan", s.perluAkun(s.pesanAI))
	m.HandleFunc("POST /api/keputusan", s.perluAkun(s.simpanKeputusan))
	m.HandleFunc("GET /api/kebijakan", s.perluPusat(s.kebijakan))
	m.HandleFunc("GET /api/keadilan", s.perluPusat(s.lihatKeadilan))
	m.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) { galat(w, http.StatusNotFound, "tidak_ada") })
	if s.web != nil {
		m.Handle("/", berkasWeb(s.web))
	}
	return amankan(kompres(m))
}
