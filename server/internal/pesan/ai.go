package pesan

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"os"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Lapisan AI untuk draf pesan. AI hanya menulis ulang kata-kata template; petugas yang memutuskan.
// Cadangan: kunci kosong, API mati, timeout, JSON rusak, pelanggaran aturan, atau TEPAT_AI=off => template.
// Susun tidak pernah gagal.
//
// Pengaturan lewat variabel lingkungan (sama dengan llm.py):
//
//	GEMINI_API_KEY / GOOGLE_API_KEY   kunci Gemini
//	ANTHROPIC_API_KEY                 kunci Anthropic
//	TEPAT_LLM_PROVIDER                anthropic | gemini; kosong = Anthropic bila kuncinya ada, selain itu Gemini
//	TEPAT_AI=off                      saklar mati (juga 0, false, mati, no)
//	TEPAT_LLM_MODEL                   bawaan ModelAnthropic atau ModelGemini
//	ANTHROPIC_BASE_URL / GEMINI_BASE_URL
//	TEPAT_AI_TIMEOUT                  detik per panggilan (1-120), bawaan 45
//	TEPAT_AI_BATAS_HARIAN             panggilan per hari per proses, bawaan 300

// Model dan alamat bawaan.
const (
	ModelAnthropic = "claude-haiku-5-5"
	URLAnthropic   = "https://api.anthropic.com"
	ModelGemini    = "gemini-3.1-flash-lite" // uji nyata 29 Okt: tercepat dan stabil di tier gratis
	URLGemini      = "https://generativelanguage.googleapis.com"

	batasWaktuBawaan  = 45.0 // panggilan pertama model bisa ±31 dtk (terukur)
	cobaUlang         = 1    // hanya untuk galat sementara di sisi server (503/529)
	jedaUlang         = 1200 * time.Millisecond
	batasHarianBawaan = 300
)

var penyedia = []string{"anthropic", "gemini"} // urutan = prioritas pemilihan otomatis

//go:embed sistem.txt
var sistemTemplat string

// Gagal adalah alasan AI tidak dipakai. Kode adalah kunci PesanCadangan; Rinci tanpa data peserta.
type Gagal struct{ Kode, Rinci string }

func (g *Gagal) Error() string { return g.Kode + ": " + g.Rinci }

func gagal(kode, rinci string) error { return &Gagal{kode, rinci} }

// PesanCadangan menjelaskan kode cadangan untuk petugas.
var PesanCadangan = map[string]string{
	"dimatikan":             "AI dimatikan",
	"tanpa_kunci":           "kunci API belum diisi",
	"penyedia_salah":        "pengaturan penyedia AI tidak dikenal",
	"batas_harian":          "batas panggilan harian tercapai",
	"kuota":                 "kuota API terlampaui, coba lagi sebentar",
	"api_error":             "API tidak bisa dihubungi",
	"timeout":               "API terlalu lama menjawab",
	"respons_kosong":        "AI tidak memberi jawaban",
	"json_rusak":            "jawaban AI bukan JSON yang valid",
	"jalur_berubah":         "jawaban AI mengubah jalur",
	"melanggar_aturan":      "jawaban AI melanggar aturan pesan",
	"kesalahan_tak_terduga": "galat tak terduga",
	"tanpa_pesan":           "tidak ada pesan bulan ini",
	"tanpa_pesan_peserta":   "rute ini tidak mengirim pesan ke peserta",
}

// Hasil adalah draf beserta keterangan asalnya.
type Hasil struct {
	Jalur            string `json:"jalur"`  // selalu sama dengan tindakan masukan
	Draf             []Draf `json:"draf"`   // bentuk sama dengan Template
	Status           string `json:"status"` // "ai" | "template"
	Cadangan         string `json:"cadangan"`
	Rinci            string `json:"rinci"`
	RingkasanPetugas string `json:"ringkasan_petugas"`
	Model            string `json:"model"`
	Penyedia         string `json:"penyedia"`
	Dirapikan        int    `json:"dirapikan"`
}

// Keterangan adalah satu kalimat untuk petugas tentang asal draf.
func (h Hasil) Keterangan() string {
	if h.Status == "ai" {
		nama, rapi := "", ""
		if h.Model != "" {
			nama = " (" + h.Model + ")"
		}
		if h.Dirapikan > 0 {
			rapi = fmt.Sprintf(" Spasi dirapikan otomatis di %d tempat.", h.Dirapikan)
		}
		return "Disusun AI" + nama + " dari template. Rute tidak berubah; sunting sebelum dikirim." + rapi
	}
	alasan, ok := PesanCadangan[h.Cadangan]
	if !ok {
		alasan = h.Cadangan
	}
	if alasan == "" {
		return "Memakai template."
	}
	return "Memakai template (" + alasan + ")."
}

// Klien mengirim (instruksi sistem, masukan pengguna) dan mengembalikan teks mentah dari model.
type Klien func(ctx context.Context, sistem, masukan string) (string, error)

// ---------------------------------------------------------------- pengaturan

func ambil(nama string) string { return strings.TrimSpace(os.Getenv(nama)) }

// AIDimatikan melaporkan saklar TEPAT_AI.
func AIDimatikan() bool {
	return slices.Contains([]string{"off", "0", "false", "mati", "no"}, strings.ToLower(ambil("TEPAT_AI")))
}

var namaKunci = map[string][]string{"anthropic": {"ANTHROPIC_API_KEY"}, "gemini": {"GEMINI_API_KEY", "GOOGLE_API_KEY"}}

func kunciPenyedia(nama string) string {
	for _, v := range namaKunci[nama] {
		if k := ambil(v); k != "" {
			return k
		}
	}
	return ""
}

func pilihPenyedia() (string, string, error) {
	if AIDimatikan() {
		return "", "", gagal("dimatikan", "")
	}
	if pilihan := strings.ToLower(ambil("TEPAT_LLM_PROVIDER")); pilihan != "" {
		if !slices.Contains(penyedia, pilihan) {
			return "", "", gagal("penyedia_salah", potong(pilihan, 20))
		}
		k := kunciPenyedia(pilihan)
		if k == "" {
			return "", "", gagal("tanpa_kunci", pilihan)
		}
		return pilihan, k, nil
	}
	for _, nama := range penyedia {
		if k := kunciPenyedia(nama); k != "" {
			return nama, k, nil
		}
	}
	return "", "", gagal("tanpa_kunci", "")
}

// AITersedia melaporkan apakah AI bisa dipakai, dan kode alasannya bila tidak. Tanpa panggilan jaringan.
func AITersedia() (bool, string) {
	if _, _, err := pilihPenyedia(); err != nil {
		return false, err.(*Gagal).Kode
	}
	return true, ""
}

// BatasWaktu dalam detik (1-120).
func BatasWaktu() float64 {
	v, err := strconv.ParseFloat(ambil("TEPAT_AI_TIMEOUT"), 64)
	if err != nil {
		v = batasWaktuBawaan
	}
	return math.Min(math.Max(v, 1), 120)
}

var jatah = struct {
	sync.Mutex
	tgl string
	n   int
}{}

func ambilJatah() error {
	jatah.Lock()
	defer jatah.Unlock()
	if hari := time.Now().Format(time.DateOnly); jatah.tgl != hari {
		jatah.tgl, jatah.n = hari, 0
	}
	batas, err := strconv.Atoi(ambil("TEPAT_AI_BATAS_HARIAN"))
	if err != nil {
		batas = batasHarianBawaan
	}
	if jatah.n >= batas {
		return gagal("batas_harian", fmt.Sprintf("%d panggilan", batas))
	}
	jatah.n++
	return nil
}

// ---------------------------------------------------------------- klien HTTP

// kirim: satu tempat untuk HTTP dan pemetaan galat. Pesan galat tidak pernah memuat alamat, header, atau
// kunci. 503/529 dicoba ulang sekali setelah jeda; 429 dan galat klien tidak.
func kirim(ctx context.Context, alamat string, header map[string]string, badan []byte, batas float64) (map[string]any, error) {
	ctx, batal := context.WithTimeout(ctx, time.Duration(batas*float64(time.Second)))
	defer batal()
	waktuHabis := func() error { return gagal("timeout", strconv.FormatFloat(batas, 'g', -1, 64)+" dtk") }
	for percobaan := 0; ; percobaan++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, alamat, bytes.NewReader(badan))
		if err != nil {
			return nil, gagal("api_error", "tidak terhubung")
		}
		for k, v := range header {
			req.Header.Set(k, v)
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			var ne net.Error
			if errors.Is(err, context.DeadlineExceeded) || (errors.As(err, &ne) && ne.Timeout()) {
				return nil, waktuHabis()
			}
			return nil, gagal("api_error", "tidak terhubung")
		}
		isi, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			if errors.Is(err, context.DeadlineExceeded) {
				return nil, waktuHabis()
			}
			return nil, gagal("api_error", "respons tidak terbaca")
		}
		if resp.StatusCode >= 400 {
			if (resp.StatusCode == 503 || resp.StatusCode == 529) && percobaan < cobaUlang {
				select {
				case <-time.After(jedaUlang):
					continue
				case <-ctx.Done():
					return nil, waktuHabis()
				}
			}
			rinci := fmt.Sprintf("HTTP %d", resp.StatusCode)
			if percobaan > 0 {
				rinci += " (sudah dicoba ulang)"
			}
			if resp.StatusCode == 429 {
				return nil, gagal("kuota", rinci)
			}
			return nil, gagal("api_error", rinci)
		}
		var data map[string]any
		if err := json.Unmarshal(isi, &data); err != nil || data == nil {
			return nil, gagal("api_error", "respons tidak terbaca")
		}
		return data, nil
	}
}

// KlienAnthropic adalah klien tipis ke Messages API.
func KlienAnthropic(kunci, model, url string, batas float64) Klien {
	alamat := strings.TrimRight(url, "/") + "/v1/messages"
	return func(ctx context.Context, sistem, masukan string) (string, error) {
		if err := ambilJatah(); err != nil {
			return "", err
		}
		badan, _ := json.Marshal(map[string]any{"model": model, "max_tokens": 900, "system": sistem,
			"messages": []map[string]string{{"role": "user", "content": masukan}}})
		data, err := kirim(ctx, alamat, map[string]string{"content-type": "application/json", "x-api-key": kunci,
			"anthropic-version": "2023-06-01"}, badan, batas)
		if err != nil {
			return "", err
		}
		var teks strings.Builder
		for _, b := range daftar(data["content"]) {
			if m, ok := b.(map[string]any); ok && m["type"] == "text" {
				s, _ := m["text"].(string)
				teks.WriteString(s)
			}
		}
		if trimPy(teks.String()) == "" {
			sebab, _ := data["stop_reason"].(string)
			return "", gagal("respons_kosong", potong(sebab, 40))
		}
		return teks.String(), nil
	}
}

var polaNamaModel = regexp.MustCompile(`^[\w.\-]+$`)

// KlienGemini adalah klien tipis ke Gemini generateContent (v1beta). Kunci lewat header, bukan alamat.
// JSON dijaga prompt, lalu urai dan validator; maxOutputTokens longgar karena model bisa "berpikir" dulu.
func KlienGemini(kunci, model, url string, batas float64) (Klien, error) {
	if !polaNamaModel.MatchString(model) {
		return nil, gagal("penyedia_salah", "nama model tidak valid")
	}
	alamat := fmt.Sprintf("%s/v1beta/models/%s:generateContent", strings.TrimRight(url, "/"), model)
	return func(ctx context.Context, sistem, masukan string) (string, error) {
		if err := ambilJatah(); err != nil {
			return "", err
		}
		badan, _ := json.Marshal(map[string]any{
			"system_instruction": map[string]any{"parts": []map[string]string{{"text": sistem}}},
			"contents":           []map[string]any{{"role": "user", "parts": []map[string]string{{"text": masukan}}}},
			"generationConfig":   map[string]int{"maxOutputTokens": 2048}})
		data, err := kirim(ctx, alamat, map[string]string{"content-type": "application/json", "x-goog-api-key": kunci},
			badan, batas)
		if err != nil {
			return "", err
		}
		var kandidat []map[string]any
		for _, c := range daftar(data["candidates"]) {
			if m, ok := c.(map[string]any); ok {
				kandidat = append(kandidat, m)
			}
		}
		var teks strings.Builder
		if len(kandidat) > 0 {
			konten, _ := kandidat[0]["content"].(map[string]any)
			for _, b := range daftar(konten["parts"]) {
				if m, ok := b.(map[string]any); ok && m["thought"] != true {
					s, _ := m["text"].(string)
					teks.WriteString(s)
				}
			}
		}
		if trimPy(teks.String()) == "" {
			sebab := ""
			if umpan, ok := data["promptFeedback"].(map[string]any); ok {
				sebab, _ = umpan["blockReason"].(string)
			}
			if sebab == "" && len(kandidat) > 0 {
				sebab, _ = kandidat[0]["finishReason"].(string)
			}
			return "", gagal("respons_kosong", potong(sebab, 40))
		}
		return teks.String(), nil
	}, nil
}

// KlienDariLingkungan memilih penyedia, model, dan klien dari variabel lingkungan.
func KlienDariLingkungan() (Klien, string, string, error) {
	nama, kunci, err := pilihPenyedia()
	if err != nil {
		return nil, "", "", err
	}
	batas := BatasWaktu()
	if nama == "gemini" {
		model := cmpOr(ambil("TEPAT_LLM_MODEL"), ModelGemini)
		k, err := KlienGemini(kunci, model, cmpOr(ambil("GEMINI_BASE_URL"), URLGemini), batas)
		return k, nama, model, err
	}
	model := cmpOr(ambil("TEPAT_LLM_MODEL"), ModelAnthropic)
	return KlienAnthropic(kunci, model, cmpOr(ambil("ANTHROPIC_BASE_URL"), URLAnthropic), batas), nama, model, nil
}

// ---------------------------------------------------------------- prompt dan masukan

func kodeAturan(tindakan, saran string) string {
	if tindakan == tdkPD {
		return "peringatan_dini:" + saran
	}
	return tindakan
}

// Sistem adalah instruksi sistem untuk satu kode aturan.
func Sistem(kode string) string {
	grup, ok := WajibSebut[kode]
	if !ok {
		grup = [][]string{istilahBoleh}
	}
	var bagian []string
	for _, g := range grup {
		var q []string
		for _, k := range g {
			q = append(q, `"`+k+`"`)
		}
		bagian = append(bagian, strings.Join(q, " atau "))
	}
	dilarang, ringkasan := "", ""
	if tanpaOpsiBayar[kode] {
		dilarang = catatanTanpaOpsiBayar
	}
	if _, ok := ringkasanWajib[kode]; ok {
		ringkasan = catatanRingkasanPBI
	}
	return strings.NewReplacer("{wajib}", strings.Join(bagian, " / "), "{dilarang}", dilarang,
		"{ringkasan}", ringkasan).Replace(sistemTemplat)
}

// Masukan adalah satu-satunya data peserta yang meninggalkan sistem: tanpa nomor peserta. Ditulis sebagai
// JSON dengan pemisah ", " dan ": " seperti json.dumps(..., ensure_ascii=False).
func Masukan(p Peserta, tindakan, drafTemplat string) string {
	ew := tindakan == tdkPD
	var b strings.Builder
	b.WriteString(`{"jalur": ` + jsonPy(tindakan) + `, "skor": `)
	if ew && p.EWSkor != nil && !math.IsNaN(*p.EWSkor) {
		b.WriteString(floatPy(bulat(*p.EWSkor, 3)))
	} else {
		b.WriteString("null")
	}
	alasan := cmpOr(p.AlasanRapi, p.Alasan)
	if ew {
		alasan = p.EWAlasan
	}
	b.WriteString(`, "alasan": ` + jsonPy(alasan))
	b.WriteString(`, "fakta": {"tunggakan_bulan": ` + strconv.Itoa(p.TunggakanBulan) +
		`, "tunggakan_rp": ` + jsonPy(Rp(p.TunggakanRp)) + `, "iuran_bulanan": ` + jsonPy(Rp(p.IuranBulanan)) +
		`, "sudah_autodebet": ` + strconv.FormatBool(p.Autodebet) + `}`)
	b.WriteString(`, "draf_template": ` + jsonPy(strings.ReplaceAll(drafTemplat, p.ID, "{ID}")))
	if ew {
		b.WriteString(`, "saran": ` + jsonPy(p.EWSaran))
	}
	b.WriteString("}")
	return b.String()
}

// bulat = round(x, n) Python: dibulatkan benar pada nilai desimal persis.
func bulat(x float64, n int) float64 {
	v, _ := strconv.ParseFloat(strconv.FormatFloat(x, 'f', n, 64), 64)
	return v
}

// floatPy = repr(float) Python untuk nilai biasa (tanpa notasi eksponen).
func floatPy(x float64) string {
	s := strconv.FormatFloat(x, 'f', -1, 64)
	if !strings.ContainsAny(s, ".eEn") {
		s += ".0"
	}
	return s
}

// jsonPy = json.dumps(string, ensure_ascii=False).
func jsonPy(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(&b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

// urai mengambil objek JSON {jalur, pesan_peserta, ringkasan_petugas} dari jawaban mentah model.
func urai(mentah string) (map[string]string, error) {
	t := trimPy(mentah)
	if l := strings.ToLower(t); strings.HasPrefix(l, "```") {
		t = t[3:]
		if strings.HasPrefix(strings.ToLower(t), "json") {
			t = t[4:]
		}
		t = strings.TrimLeftFunc(t, spasiPy)
	}
	if strings.HasSuffix(t, "```") {
		t = strings.TrimRightFunc(t[:len(t)-3], spasiPy)
	}
	a, b := strings.Index(t, "{"), strings.LastIndex(t, "}")
	if a < 0 || b <= a {
		return nil, gagal("json_rusak", "tanpa objek JSON")
	}
	var d map[string]any
	if err := json.Unmarshal([]byte(t[a:b+1]), &d); err != nil {
		return nil, gagal("json_rusak", "JSON tidak valid")
	}
	hasil := map[string]string{}
	for _, k := range []string{"jalur", "pesan_peserta", "ringkasan_petugas"} {
		s, ok := d[k].(string)
		if !ok {
			return nil, gagal("json_rusak", "kunci jalur/pesan_peserta/ringkasan_petugas tidak lengkap")
		}
		hasil[k] = s
	}
	return hasil, nil
}

// ---------------------------------------------------------------- titik masuk

// Opsi Susun.
type Opsi struct {
	PakaiAI bool
	Klien   Klien // untuk uji; nil = klien dari variabel lingkungan
}

// Susun menyusun draf untuk tindakan utama peserta. Selalu mengembalikan draf dari template bila AI tidak
// bisa dipakai atau jawabannya ditolak. Tidak pernah gagal dan tidak mengubah p.
func Susun(ctx context.Context, p Peserta, tindakan string, o Opsi) (h Hasil) {
	templat := Template(p, tindakan)
	h = Hasil{Jalur: tindakan, Draf: templat, Status: "template"}
	switch {
	case len(templat) == 0:
		h.Cadangan = "tanpa_pesan"
		return h
	case templat[0].Jenis != PesanPeserta:
		h.Cadangan = "tanpa_pesan_peserta"
		return h
	case !o.PakaiAI:
		h.Cadangan = "dimatikan"
		return h
	}
	defer func() { // jaring terakhir: halaman petugas tidak boleh gagal karena AI
		if r := recover(); r != nil {
			h = Hasil{Jalur: tindakan, Draf: templat, Status: "template", Cadangan: "kesalahan_tak_terduga",
				Rinci: fmt.Sprintf("%T", r)}
		}
	}()
	if err := susunAI(ctx, p, tindakan, templat, o, &h); err != nil {
		h.Draf, h.Status, h.RingkasanPetugas, h.Model, h.Penyedia, h.Dirapikan = templat, "template", "", "", "", 0
		var g *Gagal
		if errors.As(err, &g) {
			h.Cadangan, h.Rinci = g.Kode, g.Rinci
		} else {
			h.Cadangan, h.Rinci = "kesalahan_tak_terduga", fmt.Sprintf("%T", err)
		}
	}
	return h
}

func susunAI(ctx context.Context, p Peserta, tindakan string, templat []Draf, o Opsi, h *Hasil) error {
	klien, nama, model := o.Klien, "", ""
	if klien == nil {
		var err error
		if klien, nama, model, err = KlienDariLingkungan(); err != nil {
			return err
		}
	} else if AIDimatikan() {
		return gagal("dimatikan", "")
	}
	saran := ""
	if tindakan == tdkPD {
		saran = p.EWSaran
	}
	kode := kodeAturan(tindakan, saran)
	mentah, err := klien(ctx, Sistem(kode), Masukan(p, tindakan, templat[0].Isi))
	if err != nil {
		return err
	}
	d, err := urai(mentah)
	if err != nil {
		return err
	}
	if trimPy(d["jalur"]) != tindakan {
		return gagal("jalur_berubah", reprPendek(d["jalur"], 40))
	}
	pesan, rapiPesan := RapikanSpasi(BersihkanKarakter(d["pesan_peserta"]))
	// ringkasan petugas juga dirapikan (uji 30 Okt: "diarahkanuntuk", "inicek") dan dinilai setelah dirapikan
	ringkasan, rapiRingkasan := RapikanSpasi(BersihkanKarakter(d["ringkasan_petugas"]))
	ringkasan = trimPy(ringkasan)
	nominal := []int{int(math.RoundToEven(p.TunggakanRp)), int(math.RoundToEven(p.IuranBulanan))}
	pelanggaran := PeriksaPesanPeserta(pesan, kode, p.TunggakanBulan, nominal, OpsiDalam(templat[0].Isi))
	for _, x := range PeriksaRingkasan(ringkasan) {
		pelanggaran = append(pelanggaran, x+"@ringkasan")
	}
	if len(pelanggaran) > 0 {
		return gagal("melanggar_aturan", strings.Join(pelanggaran, ","))
	}
	d0 := templat[0]
	d0.Isi = strings.ReplaceAll(trimPy(pesan), "{ID}", p.ID)
	d0.Judul = "Pesan ke peserta (draf AI)"
	h.Draf, h.Status, h.Model, h.Penyedia = []Draf{d0}, "ai", model, nama
	h.Dirapikan = rapiPesan + rapiRingkasan
	if pola, ok := ringkasanWajib[kode]; ok && !pola.MatchString(proyeksi(ringkasan, true)) {
		ringkasan, h.Rinci = "", "ringkasan_dibuang:tanpa_kelayakan_PBI"
	}
	h.RingkasanPetugas = ringkasan
	return nil
}

// reprPendek meniru f"{s[:n]!r}" Python untuk kasus umum (kutip tunggal).
func reprPendek(s string, n int) string {
	s = potong(s, n)
	if strings.Contains(s, "'") && !strings.Contains(s, `"`) {
		return `"` + s + `"`
	}
	return "'" + strings.ReplaceAll(strings.ReplaceAll(s, `\`, `\\`), "'", `\'`) + "'"
}

func potong(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

func daftar(v any) []any {
	xs, _ := v.([]any)
	return xs
}

func cmpOr(a, b string) string {
	if a != "" {
		return a
	}
	return b
}
