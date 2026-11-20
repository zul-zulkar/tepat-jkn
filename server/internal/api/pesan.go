package api

import (
	"log"
	"net/http"
	"slices"
	"strings"
	"time"

	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
	"github.com/zul-zulkar/tepat-jkn/server/internal/pesan"
	"github.com/zul-zulkar/tepat-jkn/server/internal/triase"
)

func untukPesan(p *data.Peserta) pesan.Peserta {
	q := pesan.Peserta{ID: p.ID, Rute: p.Rute, Alasan: p.Alasan, AlasanRapi: pesan.AlasanRapi(p.Alasan),
		TunggakanBulan: p.TunggakanBulan, TunggakanRp: float64(p.TunggakanRp),
		IuranBulanan: float64(p.IuranBulanan), Autodebet: p.Autodebet}
	if p.EW != nil {
		skor := p.EW.Skor
		q.EWSkor, q.EWAlasan, q.EWSaran = &skor, p.EW.Alasan, p.EW.Saran
	}
	return q
}

func (s *Server) pesanAI(w http.ResponseWriter, r *http.Request) {
	var in struct {
		ID      string `json:"id"`
		PakaiAI bool   `json:"pakai_ai"`
	}
	if !bacaJSON(w, r, &in) {
		return
	}
	p := s.data.Cari(NormalkanID(in.ID))
	l := s.lingkup(r)
	if p == nil || !l.akun.Boleh(p.KodeWilayah) {
		galat(w, http.StatusNotFound, "tidak_ada")
		return
	}
	h := pesan.Susun(r.Context(), untukPesan(p), l.utama(p), pesan.Opsi{PakaiAI: in.PakaiAI})
	if h.Status == "ai" || h.Cadangan != "" {
		log.Printf("draf %s: %s %s %s", p.ID, h.Status, h.Cadangan, h.Rinci)
	}
	kirimJSON(w, map[string]any{"hasil": h, "keterangan": h.Keterangan()})
}

// AlasanTolak adalah pilihan alasan menolak, sama dengan halaman profil.
var AlasanTolak = []string{"Data tidak sesuai kondisi di lapangan", "Peserta sudah melunasi atau sudah ditangani",
	"Peserta tidak mampu, lebih tepat dirujuk cek PBI",
	"Ada penjelasan lain yang wajar, misalnya sakit atau kerja musiman", "Lainnya"}

func (s *Server) simpanKeputusan(w http.ResponseWriter, r *http.Request) {
	var in struct {
		ID        string `json:"id"`
		Keputusan string `json:"keputusan"`
		Alasan    string `json:"alasan"`
		Catatan   string `json:"catatan"`
	}
	if !bacaJSON(w, r, &in) {
		return
	}
	l := s.lingkup(r)
	if l.akun.AdalahPusat() {
		galat(w, http.StatusForbidden, "keputusan_dicatat_cabang")
		return
	}
	p := s.data.Cari(NormalkanID(in.ID))
	if p == nil || !l.akun.Boleh(p.KodeWilayah) {
		galat(w, http.StatusNotFound, "tidak_ada")
		return
	}
	in.Catatan = strings.TrimSpace(in.Catatan)
	switch {
	case in.Keputusan != "setuju" && in.Keputusan != "tolak":
		galat(w, http.StatusBadRequest, "keputusan_tidak_valid")
		return
	case in.Keputusan == "tolak" && !slices.Contains(AlasanTolak, in.Alasan):
		galat(w, http.StatusBadRequest, "pilih_alasan_menolak")
		return
	case in.Alasan == "Lainnya" && in.Catatan == "":
		galat(w, http.StatusBadRequest, "catatan_wajib_untuk_lainnya")
		return
	}
	if in.Keputusan == "setuju" {
		in.Alasan = ""
	}
	utama := l.utama(p)
	sasaran := "Rute triase"
	switch {
	case utama == triase.PeringatanDini:
		sasaran = "Pencegahan, berisiko menunggak"
	case !slices.Contains(triase.RuteAksi, utama):
		galat(w, http.StatusBadRequest, "tidak_ada_yang_diputuskan")
		return
	}
	k := Keputusan{IDPeserta: p.ID, Sasaran: sasaran, Kode: utama, Keputusan: in.Keputusan, Alasan: in.Alasan,
		Catatan: in.Catatan, Waktu: time.Now().Format("2006-01-02 15:04"), DicatatOleh: l.akun.Nama}
	ss := sesiDari(r)
	ss.mu.Lock()
	ss.keputusan[p.ID] = k
	ss.mu.Unlock()
	kirimJSON(w, k)
}
