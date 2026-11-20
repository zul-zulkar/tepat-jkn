package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"sync"
	"time"

	"github.com/zul-zulkar/tepat-jkn/server/internal/akun"
)

const (
	namaKuki = "tepat_sesi"
	// Sesi tersimpan di memori. Tanpa batas, setiap pengunjung tanpa kuki (termasuk bot) menambah satu entri.
	umurSesi   = 12 * time.Hour
	maksSesi   = 5000
	jedaBersih = 10 * time.Minute
)

// Keputusan petugas atas satu peserta. Hanya untuk sesi ini; penyimpanan permanen menyusul.
type Keputusan struct {
	IDPeserta   string `json:"id_peserta"`
	Sasaran     string `json:"sasaran"`
	Kode        string `json:"kode"`
	Keputusan   string `json:"keputusan"` // setuju | tolak
	Alasan      string `json:"alasan"`
	Catatan     string `json:"catatan"`
	Waktu       string `json:"waktu"` // YYYY-MM-DD HH:MM, waktu lokal server
	DicatatOleh string `json:"dicatat_oleh"`
}

// sesi menyimpan akun yang masuk, kapasitas k, dan keputusan. Keputusan dan k tidak hilang saat ganti akun
// (sama dengan aplikasi Streamlit), supaya Pusat bisa melihat keputusan yang dicatat cabang.
type sesi struct {
	mu        sync.Mutex
	terakhir  time.Time
	akun      *akun.Akun
	k         int
	keputusan map[string]Keputusan
}

func (s *sesi) salin() (a *akun.Akun, k int, kep map[string]Keputusan) {
	s.mu.Lock()
	defer s.mu.Unlock()
	kep = make(map[string]Keputusan, len(s.keputusan))
	for id, v := range s.keputusan {
		kep[id] = v
	}
	if s.akun != nil {
		x := *s.akun
		a = &x
	}
	return a, s.k, kep
}

type penyimpanSesi struct {
	mu      sync.Mutex
	isi     map[string]*sesi
	kBawaan int
}

func baruPenyimpan(kBawaan int) *penyimpanSesi {
	return &penyimpanSesi{isi: map[string]*sesi{}, kBawaan: kBawaan}
}

// bersihkan membuang sesi yang tidak dipakai lebih dari umurSesi.
func (p *penyimpanSesi) bersihkan(sekarang time.Time) {
	p.mu.Lock()
	defer p.mu.Unlock()
	for id, s := range p.isi {
		s.mu.Lock()
		basi := sekarang.Sub(s.terakhir) > umurSesi
		s.mu.Unlock()
		if basi {
			delete(p.isi, id)
		}
	}
}

// jagaKebersihan membersihkan sesi berkala sampai ctx selesai.
func (p *penyimpanSesi) jagaKebersihan(ctx context.Context) {
	t := time.NewTicker(jedaBersih)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case now := <-t.C:
			p.bersihkan(now)
		}
	}
}

// amanHTTPS: sambungan asli atau penerus (Cloud Run, Render, Caddy) memakai HTTPS.
func amanHTTPS(r *http.Request) bool {
	return r.TLS != nil || r.Header.Get("X-Forwarded-Proto") == "https"
}

// ambil mengembalikan sesi dari kuki, atau membuat sesi baru dan memasang kukinya.
func (p *penyimpanSesi) ambil(w http.ResponseWriter, r *http.Request) *sesi {
	p.mu.Lock()
	defer p.mu.Unlock()
	now := time.Now()
	if c, err := r.Cookie(namaKuki); err == nil {
		if s, ok := p.isi[c.Value]; ok {
			s.mu.Lock()
			s.terakhir = now
			s.mu.Unlock()
			return s
		}
	}
	if len(p.isi) >= maksSesi {
		p.buangTertua()
	}
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	id := hex.EncodeToString(b)
	s := &sesi{terakhir: now, k: p.kBawaan, keputusan: map[string]Keputusan{}}
	p.isi[id] = s
	http.SetCookie(w, &http.Cookie{Name: namaKuki, Value: id, Path: "/", HttpOnly: true,
		Secure: amanHTTPS(r), SameSite: http.SameSiteLaxMode, MaxAge: int(umurSesi.Seconds())})
	return s
}

// buangTertua membuang sesi yang paling lama tidak dipakai. Pemanggil memegang p.mu.
func (p *penyimpanSesi) buangTertua() {
	var tertua string
	var waktu time.Time
	for id, s := range p.isi {
		s.mu.Lock()
		t := s.terakhir
		s.mu.Unlock()
		if tertua == "" || t.Before(waktu) {
			tertua, waktu = id, t
		}
	}
	delete(p.isi, tertua)
}
