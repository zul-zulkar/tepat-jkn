package data

import (
	"bytes"
	"cmp"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io/fs"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/parquet-go/parquet-go"
)

// Baris mentah per berkas. Tipe mengikuti skema parquet yang ditulis pandas/pyarrow (int8, int16, int32,
// timestamp mikrodetik); kolom yang tidak disebut di sini tidak dibaca.

type barisPeserta struct {
	ID               string    `parquet:"id_peserta"`
	TglDaftar        time.Time `parquet:"tgl_daftar,timestamp(microsecond)"`
	Kelas            int8      `parquet:"kelas"`
	IuranBulanan     int32     `parquet:"iuran_bulanan"`
	Usia2023         int8      `parquet:"usia_2023"`
	JenisKelamin     string    `parquet:"jenis_kelamin"`
	KodeWilayah      string    `parquet:"kode_wilayah"`
	Autodebet        bool      `parquet:"autodebet"`
	Segmen           string    `parquet:"segmen_kepesertaan"`
	PembayarIuran    string    `parquet:"pembayar_iuran"`
	IndeksKemiskinan float64   `parquet:"indeks_kemiskinan"`
	RentangDesil     string    `parquet:"rentang_desil"`
}

type barisDaftar struct {
	ID                 string   `parquet:"id_peserta"`
	Rute               string   `parquet:"rute"`
	Alasan             string   `parquet:"alasan"`
	TunggakanBulan     int8     `parquet:"tunggakan_bulan"`
	TunggakanRp        int32    `parquet:"tunggakan_rp"`
	NReaktivasi        int8     `parquet:"n_reaktivasi"`
	NReaktTerkaitKlaim int8     `parquet:"n_reakt_terkait_klaim"`
	RasioHariAktif     float64  `parquet:"rasio_hari_aktif"`
	RasioKlaimIuran    *float64 `parquet:"rasio_klaim_iuran,optional"`
	KlaimRp            float64  `parquet:"klaim_rp"`
	IuranRp            float64  `parquet:"iuran_rp"`
}

type barisStatus struct {
	ID      string    `parquet:"id_peserta"`
	Mulai   time.Time `parquet:"tgl_mulai,timestamp(microsecond)"`
	Selesai time.Time `parquet:"tgl_selesai,timestamp(microsecond)"`
	Status  string    `parquet:"status"`
}

type barisBayar struct {
	ID           string    `parquet:"id_peserta"`
	Tanggal      time.Time `parquet:"tgl_bayar,timestamp(microsecond)"`
	PeriodeAwal  string    `parquet:"periode_awal"`
	PeriodeAkhir string    `parquet:"periode_akhir"`
	JumlahBulan  int8      `parquet:"jumlah_bulan_dibayar"`
	Nominal      int32     `parquet:"nominal"`
	Kanal        string    `parquet:"kanal"`
}

type barisKlaim struct {
	ID              string    `parquet:"id_klaim"`
	Peserta         string    `parquet:"id_peserta"`
	Episode         string    `parquet:"id_episode"`
	TglMasuk        time.Time `parquet:"tgl_masuk,timestamp(microsecond)"`
	TglKeluar       time.Time `parquet:"tgl_keluar,timestamp(microsecond)"`
	JenisLayanan    string    `parquet:"jenis_layanan"`
	CaraMasuk       string    `parquet:"cara_masuk"`
	KelompokLayanan string    `parquet:"kelompok_layanan"`
	KelasRawat      int8      `parquet:"kelas_rawat"`
	BiayaKlaim      int32     `parquet:"biaya_klaim"`
	DendaPelayanan  int32     `parquet:"denda_pelayanan"`
}

type barisReakt struct {
	ID              string    `parquet:"id_peserta"`
	Tanggal         time.Time `parquet:"tgl_reakt,timestamp(microsecond)"`
	BulanTertunggak int8      `parquet:"bulan_tertunggak"`
}

type barisHarian struct {
	CaraMasuk  string  `parquet:"cara_masuk"`
	Hari       int8    `parquet:"hari"`
	Hitung     int16   `parquet:"hitung"`
	CF         float64 `parquet:"cf"`
	Jendela    string  `parquet:"jendela"`
	DipakaiFit bool    `parquet:"dipakai_fit"`
}

type barisRingkasan struct {
	CaraMasuk        string   `parquet:"cara_masuk"`
	NKasus           int16    `parquet:"n_kasus"`
	NHari0           int16    `parquet:"n_hari0"`
	Lebih            float64  `parquet:"lebih"`
	LebihIKBawah     float64  `parquet:"lebih_ik_bawah"`
	LebihIKAtas      float64  `parquet:"lebih_ik_atas"`
	Kurang           float64  `parquet:"kurang"`
	Lompat           float64  `parquet:"lompat"`
	LompatIKBawah    float64  `parquet:"lompat_ik_bawah"`
	LompatIKAtas     float64  `parquet:"lompat_ik_atas"`
	IKLompatMencakup bool     `parquet:"ik_lompat_mencakup_0"`
	DendaTerhindarRp *float64 `parquet:"denda_terhindar_rp,optional"`
	BatasHari        int8     `parquet:"batas_hari"`
	NBootstrap       int16    `parquet:"n_bootstrap"`
}

// prefiksKontribusi menandai kolom kontribusi ciri di ew_daftar.parquet.
const prefiksKontribusi = "kontribusi_"

// Muat membaca semua data dari appData (isi folder app_data) dan bukti (isi folder bukti/hasil).
func Muat(appData, bukti fs.FS) (*Store, error) {
	s := &Store{indeks: map[string]*Peserta{}}

	b, err := fs.ReadFile(appData, "manifest.json")
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(b, &s.Manifest); err != nil {
		return nil, fmt.Errorf("manifest.json: %w", err)
	}

	peserta, err := baca[barisPeserta](appData, "peserta.parquet")
	if err != nil {
		return nil, err
	}
	s.Peserta = make([]*Peserta, 0, len(peserta))
	for _, r := range peserta {
		p := &Peserta{ID: r.ID, TglDaftar: r.TglDaftar, Kelas: int(r.Kelas), IuranBulanan: int(r.IuranBulanan),
			Usia2023: int(r.Usia2023), JenisKelamin: r.JenisKelamin, KodeWilayah: r.KodeWilayah,
			Autodebet: r.Autodebet, Segmen: r.Segmen, PembayarIuran: r.PembayarIuran,
			IndeksKemiskinan: r.IndeksKemiskinan, RentangDesil: r.RentangDesil, StatusAkhir: "nonaktif"}
		if _, ada := s.indeks[p.ID]; ada {
			return nil, fmt.Errorf("peserta.parquet: id ganda %s", p.ID)
		}
		s.indeks[p.ID] = p
		s.Peserta = append(s.Peserta, p)
	}

	// daftar_kerja: tepat satu baris per peserta (merge validate="1:1" di tepat_ui.tabel_peserta)
	daftar, err := baca[barisDaftar](appData, "daftar_kerja.parquet")
	if err != nil {
		return nil, err
	}
	terisi := 0
	for _, r := range daftar {
		p := s.indeks[r.ID]
		if p == nil {
			return nil, fmt.Errorf("daftar_kerja.parquet: %s tidak ada di peserta.parquet", r.ID)
		}
		if p.Rute != "" {
			return nil, fmt.Errorf("daftar_kerja.parquet: id ganda %s", r.ID)
		}
		p.Rute, p.Alasan = r.Rute, r.Alasan
		p.TunggakanBulan, p.TunggakanRp = int(r.TunggakanBulan), int(r.TunggakanRp)
		p.NReaktivasi, p.NReaktTerkaitKlaim = int(r.NReaktivasi), int(r.NReaktTerkaitKlaim)
		p.RasioHariAktif, p.RasioKlaimIuran = r.RasioHariAktif, r.RasioKlaimIuran
		p.KlaimRp, p.IuranRp = r.KlaimRp, r.IuranRp
		terisi++
	}
	if terisi != len(s.Peserta) {
		return nil, fmt.Errorf("daftar_kerja.parquet: %d baris untuk %d peserta", terisi, len(s.Peserta))
	}

	if err := s.muatEW(appData); err != nil {
		return nil, err
	}
	if err := s.muatLinimasa(appData); err != nil {
		return nil, err
	}
	if err := s.muatLonjakan(appData); err != nil {
		return nil, err
	}
	if err := s.muatBukti(bukti); err != nil {
		return nil, err
	}
	return s, nil
}

// baca membaca seluruh berkas parquet ke irisan T.
func baca[T any](f fs.FS, nama string) ([]T, error) {
	b, err := fs.ReadFile(f, nama)
	if err != nil {
		return nil, err
	}
	rows, err := parquet.Read[T](bytes.NewReader(b), int64(len(b)))
	if err != nil {
		return nil, fmt.Errorf("%s: %w", nama, err)
	}
	return rows, nil
}

// muatEW membaca ew_daftar.parquet kolom per kolom, karena jumlah kolom kontribusi_* ikut model.
func (s *Store) muatEW(appData fs.FS) error {
	const nama = "ew_daftar.parquet"
	b, err := fs.ReadFile(appData, nama)
	if err != nil {
		return err
	}
	f, err := parquet.OpenFile(bytes.NewReader(b), int64(len(b)))
	if err != nil {
		return fmt.Errorf("%s: %w", nama, err)
	}
	kolom := func(k string) ([]parquet.Value, error) {
		v, err := nilaiKolom(f, k)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", nama, err)
		}
		return v, nil
	}
	id, err := kolom("id_peserta")
	if err != nil {
		return err
	}
	n := len(id)
	ambil := map[string][]parquet.Value{}
	for _, k := range []string{"peringkat", "bulan", "skor", "masuk_daftar", "alasan", "saran_intervensi"} {
		if ambil[k], err = kolom(k); err != nil {
			return err
		}
	}
	var fitur []string
	var kontrib [][]parquet.Value
	for _, c := range f.Schema().Fields() {
		if k := c.Name(); strings.HasPrefix(k, prefiksKontribusi) {
			v, err := kolom(k)
			if err != nil {
				return err
			}
			fitur, kontrib = append(fitur, strings.TrimPrefix(k, prefiksKontribusi)), append(kontrib, v)
		}
	}
	for i := range n {
		pid := id[i].String()
		p := s.indeks[pid]
		if p == nil {
			return fmt.Errorf("%s: %s tidak ada di peserta.parquet", nama, pid)
		}
		if p.EW != nil {
			return fmt.Errorf("%s: id ganda %s", nama, pid)
		}
		e := &EW{Peringkat: int(ambil["peringkat"][i].Int64()), Bulan: ambil["bulan"][i].String(),
			Skor: ambil["skor"][i].Double(), MasukDaftar: ambil["masuk_daftar"][i].Boolean(),
			Alasan: ambil["alasan"][i].String(), Saran: ambil["saran_intervensi"][i].String(),
			Kontribusi: make([]Kontribusi, len(fitur))}
		for j, ft := range fitur {
			e.Kontribusi[j] = Kontribusi{Fitur: ft, Nilai: kontrib[j][i].Double()}
		}
		p.EW = e
	}
	return nil
}

// nilaiKolom membaca semua nilai satu kolom datar (tanpa nilai kosong) di semua row group.
func nilaiKolom(f *parquet.File, nama string) ([]parquet.Value, error) {
	leaf, ok := f.Schema().Lookup(nama)
	if !ok {
		return nil, fmt.Errorf("kolom %s tidak ada", nama)
	}
	var hasil []parquet.Value
	for _, rg := range f.RowGroups() {
		pages := rg.ColumnChunks()[leaf.ColumnIndex].Pages()
		for {
			pg, err := pages.ReadPage()
			if err != nil {
				break
			}
			vals := make([]parquet.Value, pg.NumValues())
			nv, _ := pg.Values().ReadValues(vals)
			for _, v := range vals[:nv] {
				if v.IsNull() {
					_ = pages.Close()
					return nil, fmt.Errorf("kolom %s berisi nilai kosong", nama)
				}
				hasil = append(hasil, v.Clone())
			}
			parquet.Release(pg)
		}
		_ = pages.Close()
	}
	if int64(len(hasil)) != f.NumRows() {
		return nil, fmt.Errorf("kolom %s: %d nilai untuk %d baris", nama, len(hasil), f.NumRows())
	}
	return hasil, nil
}

func (s *Store) muatLinimasa(appData fs.FS) error {
	st, err := baca[barisStatus](appData, "linimasa_status.parquet")
	if err != nil {
		return err
	}
	s.status = map[string][]Status{}
	for _, r := range st {
		s.status[r.ID] = append(s.status[r.ID], Status{Mulai: r.Mulai, Selesai: r.Selesai, Status: r.Status})
	}
	for id, xs := range s.status {
		slices.SortStableFunc(xs, func(a, b Status) int { return a.Mulai.Compare(b.Mulai) })
		if p := s.indeks[id]; p != nil {
			p.StatusAkhir = xs[len(xs)-1].Status // groupby().tail(1) setelah urut (id, tgl_mulai)
		}
	}

	by, err := baca[barisBayar](appData, "linimasa_bayar.parquet")
	if err != nil {
		return err
	}
	s.bayar = map[string][]Bayar{}
	kanal := map[string]string{} // satu salinan per nilai kanal
	for _, r := range by {
		k, ada := kanal[r.Kanal]
		if !ada {
			k = strings.Clone(r.Kanal)
			kanal[k] = k
		}
		s.bayar[r.ID] = append(s.bayar[r.ID], Bayar{Tanggal: r.Tanggal, PeriodeAwal: r.PeriodeAwal,
			PeriodeAkhir: r.PeriodeAkhir, JumlahBulan: int(r.JumlahBulan), Nominal: int(r.Nominal), Kanal: k})
	}
	for _, xs := range s.bayar {
		slices.SortStableFunc(xs, func(a, b Bayar) int { return a.Tanggal.Compare(b.Tanggal) })
	}

	kl, err := baca[barisKlaim](appData, "linimasa_klaim.parquet")
	if err != nil {
		return err
	}
	s.klaim = map[string][]Klaim{}
	for _, r := range kl {
		s.klaim[r.Peserta] = append(s.klaim[r.Peserta], Klaim{ID: r.ID, Episode: r.Episode, TglMasuk: r.TglMasuk,
			TglKeluar: r.TglKeluar, JenisLayanan: r.JenisLayanan, CaraMasuk: r.CaraMasuk,
			KelompokLayanan: r.KelompokLayanan, KelasRawat: int(r.KelasRawat), BiayaKlaim: int(r.BiayaKlaim),
			DendaPelayanan: int(r.DendaPelayanan)})
	}
	for _, xs := range s.klaim {
		slices.SortStableFunc(xs, func(a, b Klaim) int { return a.TglMasuk.Compare(b.TglMasuk) })
	}

	re, err := baca[barisReakt](appData, "linimasa_reaktivasi.parquet")
	if err != nil {
		return err
	}
	s.reakt = map[string][]Reaktivasi{}
	for _, r := range re {
		s.reakt[r.ID] = append(s.reakt[r.ID], Reaktivasi{Tanggal: r.Tanggal, BulanTertunggak: int(r.BulanTertunggak)})
	}
	for _, xs := range s.reakt {
		slices.SortStableFunc(xs, func(a, b Reaktivasi) int { return a.Tanggal.Compare(b.Tanggal) })
	}
	return nil
}

func (s *Store) muatLonjakan(appData fs.FS) error {
	h, err := baca[barisHarian](appData, "bunching_harian.parquet")
	if err != nil {
		return err
	}
	s.LonjakanHarian = make([]LonjakanHarian, len(h))
	for i, r := range h {
		s.LonjakanHarian[i] = LonjakanHarian{CaraMasuk: r.CaraMasuk, Hari: int(r.Hari), Hitung: int(r.Hitung),
			CF: r.CF, Jendela: r.Jendela, DipakaiFit: r.DipakaiFit}
	}
	rg, err := baca[barisRingkasan](appData, "bunching_ringkasan.parquet")
	if err != nil {
		return err
	}
	s.LonjakanRingkasan = map[string]LonjakanRingkasan{}
	for _, r := range rg {
		s.LonjakanRingkasan[r.CaraMasuk] = LonjakanRingkasan{NKasus: int(r.NKasus), NHari0: int(r.NHari0),
			Lebih: r.Lebih, LebihIKBawah: r.LebihIKBawah, LebihIKAtas: r.LebihIKAtas, Kurang: r.Kurang,
			Lompat: r.Lompat, LompatIKBawah: r.LompatIKBawah, LompatIKAtas: r.LompatIKAtas,
			IKLompatMencakup: r.IKLompatMencakup, DendaTerhindarRp: r.DendaTerhindarRp,
			BatasHari: int(r.BatasHari), NBootstrap: int(r.NBootstrap)}
	}
	return nil
}

// muatBukti membaca skor_verifikasi.csv (lalu diurutkan menurut id_peserta, seperti halaman/keadilan.py)
// dan beban_strata.csv (urutan berkas).
func (s *Store) muatBukti(bukti fs.FS) error {
	sk, err := bacaCSV(bukti, "skor_verifikasi.csv", "id_peserta", "skor", "rute")
	if err != nil {
		return err
	}
	s.SkorVerifikasi = make([]SkorVerifikasi, 0, len(sk))
	for _, r := range sk {
		skor, err := strconv.ParseFloat(r[1], 64)
		if err != nil {
			return fmt.Errorf("skor_verifikasi.csv: skor %q: %w", r[1], err)
		}
		s.SkorVerifikasi = append(s.SkorVerifikasi, SkorVerifikasi{ID: r[0], Skor: skor, Rute: r[2]})
	}
	slices.SortStableFunc(s.SkorVerifikasi, func(a, b SkorVerifikasi) int { return cmp.Compare(a.ID, b.ID) })

	bs, err := bacaCSV(bukti, "beban_strata.csv", "strata", "kelompok", "n_peserta", "n_jalur", "porsi_jalur",
		"rasio_ke_rata2")
	if err != nil {
		return err
	}
	s.BebanStrata = make([]BebanStrata, 0, len(bs))
	for _, r := range bs {
		var b BebanStrata
		b.Dimensi, b.Kelompok = r[0], r[1]
		if b.NPeserta, err = strconv.Atoi(r[2]); err == nil {
			if b.NJalur, err = strconv.Atoi(r[3]); err == nil {
				if b.PorsiJalur, err = strconv.ParseFloat(r[4], 64); err == nil {
					b.RasioKeRata2, err = strconv.ParseFloat(r[5], 64)
				}
			}
		}
		if err != nil {
			return fmt.Errorf("beban_strata.csv: %w", err)
		}
		s.BebanStrata = append(s.BebanStrata, b)
	}
	return nil
}

// bacaCSV mengembalikan kolom yang diminta (menurut nama di baris judul) untuk setiap baris data.
func bacaCSV(f fs.FS, nama string, kolom ...string) ([][]string, error) {
	b, err := fs.ReadFile(f, nama)
	if err != nil {
		return nil, err
	}
	semua, err := csv.NewReader(bytes.NewReader(bytes.TrimPrefix(b, []byte{0xEF, 0xBB, 0xBF}))).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("%s: %w", nama, err)
	}
	if len(semua) == 0 {
		return nil, fmt.Errorf("%s: kosong", nama)
	}
	posisi := make([]int, len(kolom))
	for i, k := range kolom {
		if posisi[i] = slices.Index(semua[0], k); posisi[i] < 0 {
			return nil, fmt.Errorf("%s: kolom %s tidak ada", nama, k)
		}
	}
	hasil := make([][]string, 0, len(semua)-1)
	for _, baris := range semua[1:] {
		r := make([]string, len(kolom))
		for i, p := range posisi {
			r[i] = baris[p]
		}
		hasil = append(hasil, r)
	}
	return hasil, nil
}
