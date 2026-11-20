package api

import (
	"encoding/json"
	"log"
	"net/http"
)

func kirimJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		log.Printf("tulis JSON: %v", err)
	}
}

func galat(w http.ResponseWriter, kode int, alasan string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(kode)
	_ = json.NewEncoder(w).Encode(map[string]string{"galat": alasan})
}

func bacaJSON(w http.ResponseWriter, r *http.Request, v any) bool {
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<16))
	if err := dec.Decode(v); err != nil {
		galat(w, http.StatusBadRequest, "json_tidak_valid")
		return false
	}
	return true
}
