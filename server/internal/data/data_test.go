package data

import (
	"encoding/json"
	"os"
	"testing"
)

// Jumlah baris yang dimuat harus sama dengan yang dicatat siapkan_app.py di manifest.json.
func TestMuatSesuaiManifest(t *testing.T) {
	appData, bukti := "../../../app_data", "../../../bukti/hasil"
	b, err := os.ReadFile(appData + "/manifest.json")
	if err != nil {
		t.Skip("app_data tidak ada")
	}
	var m struct {
		File map[string]struct {
			Baris int `json:"baris"`
		} `json:"file"`
	}
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}
	s, err := Muat(os.DirFS(appData), os.DirFS(bukti))
	if err != nil {
		t.Fatal(err)
	}
	nEW, nStatus, nBayar, nKlaim, nReakt := 0, 0, 0, 0, 0
	for _, p := range s.Peserta {
		if p.Rute == "" {
			t.Fatalf("%s tanpa rute", p.ID)
		}
		if p.EW != nil {
			nEW++
		}
		nStatus += len(s.Status(p.ID))
		nBayar += len(s.Bayar(p.ID))
		nKlaim += len(s.Klaim(p.ID))
		nReakt += len(s.Reaktivasi(p.ID))
	}
	for berkas, dapat := range map[string]int{"peserta.parquet": len(s.Peserta), "ew_daftar.parquet": nEW,
		"linimasa_status.parquet": nStatus, "linimasa_bayar.parquet": nBayar, "linimasa_klaim.parquet": nKlaim,
		"linimasa_reaktivasi.parquet": nReakt, "bunching_harian.parquet": len(s.LonjakanHarian),
		"bunching_ringkasan.parquet": len(s.LonjakanRingkasan)} {
		if harap := m.File[berkas].Baris; dapat != harap {
			t.Errorf("%s: dimuat %d baris, manifest %d", berkas, dapat, harap)
		}
	}
	if nEW != s.Manifest.EWNDinilai {
		t.Errorf("peserta dinilai model: %d, manifest %d", nEW, s.Manifest.EWNDinilai)
	}
	if len(s.SkorVerifikasi) != len(s.Peserta) || len(s.BebanStrata) == 0 {
		t.Errorf("bukti: skor %d baris, beban_strata %d baris", len(s.SkorVerifikasi), len(s.BebanStrata))
	}
	for i := 1; i < len(s.SkorVerifikasi); i++ {
		if s.SkorVerifikasi[i-1].ID > s.SkorVerifikasi[i].ID {
			t.Fatal("skor_verifikasi harus urut id_peserta")
		}
	}
	for _, p := range s.Peserta {
		if p.EW != nil && len(p.EW.Kontribusi) != 13 { // 13 kolom kontribusi_* di ew_daftar.parquet
			t.Fatalf("%s: %d kolom kontribusi, harap 13", p.ID, len(p.EW.Kontribusi))
		}
	}
	if s.Cari("P-002329") == nil {
		t.Error("P-002329 harus ada")
	}
}
