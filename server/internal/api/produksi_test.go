package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"testing/fstest"
	"time"
)

func TestSesiKedaluwarsaDanBatas(t *testing.T) {
	p := baruPenyimpan(5)
	ambil := func() *http.Cookie {
		w := httptest.NewRecorder()
		p.ambil(w, httptest.NewRequest("GET", "/", nil))
		return w.Result().Cookies()[0]
	}
	ambil()
	ambil()
	if len(p.isi) != 2 {
		t.Fatalf("harap 2 sesi, dapat %d", len(p.isi))
	}
	p.bersihkan(time.Now().Add(umurSesi + time.Minute))
	if len(p.isi) != 0 {
		t.Errorf("sesi lewat umur harus dibuang, sisa %d", len(p.isi))
	}
	for range maksSesi + 10 {
		ambil()
	}
	if len(p.isi) > maksSesi {
		t.Errorf("jumlah sesi melewati batas: %d > %d", len(p.isi), maksSesi)
	}
}

func TestKukiSecureDiBelakangHTTPS(t *testing.T) {
	p := baruPenyimpan(5)
	for header, harap := range map[string]bool{"": false, "https": true} {
		r := httptest.NewRequest("GET", "/", nil)
		if header != "" {
			r.Header.Set("X-Forwarded-Proto", header)
		}
		w := httptest.NewRecorder()
		p.ambil(w, r)
		if c := w.Result().Cookies()[0]; c.Secure != harap || !c.HttpOnly {
			t.Errorf("X-Forwarded-Proto=%q: Secure=%v HttpOnly=%v", header, c.Secure, c.HttpOnly)
		}
	}
}

func TestHealthzHeaderDanCache(t *testing.T) {
	web := fstest.MapFS{
		"index.html":            {Data: []byte("<html>")},
		"_next/static/a-123.js": {Data: []byte("x")},
	}
	h := (&Server{sesi: baruPenyimpan(5), web: web}).Handler()
	do := func(jalur string) *httptest.ResponseRecorder {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest("GET", jalur, nil))
		return w
	}
	if w := do("/healthz"); w.Code != 200 || len(w.Result().Cookies()) != 0 {
		t.Errorf("/healthz: kode %d, kuki %d (tidak boleh membuat sesi)", w.Code, len(w.Result().Cookies()))
	}
	w := do("/")
	for k, v := range map[string]string{"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
		"Cache-Control": "no-cache"} {
		if w.Header().Get(k) != v {
			t.Errorf("/ %s = %q, harap %q", k, w.Header().Get(k), v)
		}
	}
	if w.Header().Get("Content-Security-Policy") == "" {
		t.Error("CSP kosong")
	}
	if got := do("/_next/static/a-123.js").Header().Get("Cache-Control"); got != "public, max-age=31536000, immutable" {
		t.Errorf("aset ber-hash: Cache-Control = %q", got)
	}
}
