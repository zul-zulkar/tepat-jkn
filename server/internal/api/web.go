package api

import (
	"errors"
	"io/fs"
	"net/http"
	"strings"
)

// berkasWeb menyajikan hasil "next build" (static export). Alamat tanpa berkas jatuh ke 404.html.
func berkasWeb(web fs.FS) http.Handler {
	files := http.FileServerFS(web)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := strings.TrimPrefix(r.URL.Path, "/")
		if p == "" {
			p = "index.html"
		} else if strings.HasSuffix(p, "/") {
			p += "index.html"
		}
		if _, err := fs.Stat(web, p); err != nil {
			if errors.Is(err, fs.ErrNotExist) {
				if _, err := fs.Stat(web, p+"/index.html"); err == nil {
					http.Redirect(w, r, r.URL.Path+"/", http.StatusMovedPermanently)
					return
				}
				if isi, err := fs.ReadFile(web, "404.html"); err == nil {
					w.Header().Set("Content-Type", "text/html; charset=utf-8")
					w.WriteHeader(http.StatusNotFound)
					_, _ = w.Write(isi)
					return
				}
			}
			http.NotFound(w, r)
			return
		}
		if strings.HasPrefix(p, "_next/static/") {
			w.Header().Set("Cache-Control", "public, max-age=31536000, immutable") // nama berkas memuat hash isi
		} else {
			w.Header().Set("Cache-Control", "no-cache") // HTML dan aset lain: periksa ulang agar rilis baru langsung terlihat
		}
		files.ServeHTTP(w, r)
	})
}
