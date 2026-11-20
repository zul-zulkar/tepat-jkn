package api

import (
	"compress/gzip"
	"net/http"
	"strings"
)

type gzipWriter struct {
	http.ResponseWriter
	gz *gzip.Writer
}

func (g gzipWriter) Write(b []byte) (int, error) { return g.gz.Write(b) }

// kompres memampatkan jawaban API dengan gzip bila peramban menerimanya.
func kompres(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/api/") && strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
			w.Header().Set("Content-Encoding", "gzip")
			w.Header().Add("Vary", "Accept-Encoding")
			gz := gzip.NewWriter(w)
			defer gz.Close()
			w = gzipWriter{w, gz}
		}
		h.ServeHTTP(w, r)
	})
}

// Next static export menyisipkan skrip inline untuk hidrasi, jadi script-src memerlukan 'unsafe-inline'.
// Selebihnya ketat: tanpa sumber luar, tanpa bingkai, tanpa pengiriman formulir ke luar.
const kebijakanKonten = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
	"img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; " +
	"base-uri 'self'; form-action 'self'; frame-ancestors 'none'"

// amankan memasang header keamanan dan mencegah penyimpanan jawaban API oleh perantara.
func amankan(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hd := w.Header()
		hd.Set("X-Content-Type-Options", "nosniff")
		hd.Set("X-Frame-Options", "DENY")
		hd.Set("Referrer-Policy", "no-referrer")
		hd.Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		hd.Set("Content-Security-Policy", kebijakanKonten)
		if amanHTTPS(r) {
			hd.Set("Strict-Transport-Security", "max-age=31536000")
		}
		h.ServeHTTP(w, r)
	})
}
