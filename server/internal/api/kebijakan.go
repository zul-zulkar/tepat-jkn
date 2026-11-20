package api

import (
	"net/http"

	"github.com/zul-zulkar/tepat-jkn/server/internal/triase"
)

func (s *Server) kebijakan(w http.ResponseWriter, r *http.Request) {
	kirimJSON(w, map[string]any{"harian": s.data.LonjakanHarian, "ringkasan": s.data.LonjakanRingkasan,
		"derajat": triase.Derajat})
}

func (s *Server) lihatKeadilan(w http.ResponseWriter, r *http.Request) { kirimJSON(w, s.keadilan) }
