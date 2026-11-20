package api

import (
	"encoding/json"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
)

func TestNormalkanID(t *testing.T) {
	for masuk, harap := range map[string]string{"2329": "P-002329", " p 2329 ": "P-002329", "P-2329": "P-002329",
		"P002329": "P-002329", "x1": "X1", "1234567": "1234567", "-12": "-12"} {
		if got := NormalkanID(masuk); got != harap {
			t.Errorf("NormalkanID(%q) = %q, harap %q", masuk, got, harap)
		}
	}
}

// Uji ujung ke ujung dengan app_data/ repo: angka kanonik proposal dan pembatasan akses.
func TestAngkaKanonikDanAkses(t *testing.T) {
	appData, bukti := "../../../app_data", "../../../bukti/hasil"
	if _, err := os.Stat(appData); err != nil {
		t.Skip("app_data tidak ada")
	}
	s, err := data.Muat(os.DirFS(appData), os.DirFS(bukti))
	if err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(Baru(s, nil).Handler())
	defer srv.Close()
	jar, _ := cookiejar.New(nil)
	c := &http.Client{Jar: jar}
	minta := func(metode, jalur, badan string, v any) int {
		req, _ := http.NewRequest(metode, srv.URL+jalur, strings.NewReader(badan))
		resp, err := c.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()
		if v != nil {
			_ = json.NewDecoder(resp.Body).Decode(v)
		}
		return resp.StatusCode
	}

	if kode := minta("GET", "/api/daftar", "", nil); kode != http.StatusUnauthorized {
		t.Errorf("tanpa akun harus 401, dapat %d", kode)
	}
	minta("POST", "/api/masuk", `{"akun":"pusat"}`, nil)
	var d struct {
		Total     int            `json:"total"`
		Jumlah    map[string]int `json:"jumlah_utama"`
		NDinilai  int            `json:"n_dinilai"`
		NEWDaftar int            `json:"n_ew_daftar"`
		Triase    []any          `json:"triase"`
		EW        []any          `json:"ew"`
	}
	minta("GET", "/api/daftar", "", &d)
	// angka proposal: triase 7.788, berisiko menunggak 650, daftar Des 2025 (k 5%) 712 dari 14.237
	if d.Total != 20000 || len(d.Triase) != 7788 || len(d.EW) != 650 || d.NEWDaftar != 712 || d.NDinilai != 14237 {
		t.Errorf("angka kanonik berubah: total %d, triase %d, berisiko %d, daftar %d/%d",
			d.Total, len(d.Triase), len(d.EW), d.NEWDaftar, d.NDinilai)
	}
	if d.Jumlah["verifikasi_pola_reaktivasi"] != 909 || d.Jumlah["rujuk_cek_kelayakan_PBI"] != 2133 {
		t.Errorf("rute berubah: %v", d.Jumlah)
	}

	minta("POST", "/api/masuk", `{"akun":"cabang_a"}`, nil)
	if kode := minta("GET", "/api/keadilan", "", nil); kode != http.StatusForbidden {
		t.Errorf("cabang membuka Keadilan: %d", kode)
	}
	if kode := minta("PUT", "/api/kapasitas", `{"k":9}`, nil); kode != http.StatusForbidden {
		t.Errorf("cabang mengubah kapasitas: %d", kode)
	}
	var luar string
	for _, p := range s.Peserta {
		if p.KodeWilayah == "W40" {
			luar = p.ID
			break
		}
	}
	if kode := minta("GET", "/api/peserta/"+luar, "", nil); kode != http.StatusForbidden {
		t.Errorf("cabang A membuka peserta W40: %d", kode)
	}
	var k struct{ Info struct{ Cocok, BarisCSV int } }
	minta("POST", "/api/masuk", `{"akun":"pusat"}`, nil)
	minta("GET", "/api/keadilan", "", &k)
	if k.Info.Cocok == 0 {
		t.Error("keadilan: cek silang beban_strata.csv gagal")
	}
}
