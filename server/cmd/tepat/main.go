// Perintah tepat menjalankan aplikasi TEPAT: API Go dan antarmuka web dalam satu proses.
//
// Build rilis (rilis.sh) menanam data dan antarmuka, jadi cukup jalankan berkasnya tanpa Python, Node,
// atau internet. Build biasa membaca langsung dari folder repo:
//
//	go run ./cmd/tepat -data ../app_data -bukti ../bukti/hasil -web ../web/out
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"runtime"
	"strings"
	"syscall"
	"time"
	_ "time/tzdata" // zona waktu tertanam: image tanpa tzdata dan Windows tanpa basis data zona tetap benar

	"github.com/zul-zulkar/tepat-jkn/server/internal/api"
	"github.com/zul-zulkar/tepat-jkn/server/internal/aset"
	"github.com/zul-zulkar/tepat-jkn/server/internal/data"
)

func main() {
	alamat := flag.String("addr", "", "alamat server (kosong = :$PORT bila PORT ada, selain itu 127.0.0.1:8080)")
	folderData := flag.String("data", "", "folder app_data (kosong = data tertanam, atau ../app_data)")
	folderBukti := flag.String("bukti", "", "folder bukti/hasil (kosong = tertanam, atau ../bukti/hasil)")
	folderWeb := flag.String("web", "", "folder hasil next build (kosong = tertanam, atau ../web/out)")
	buka := flag.Bool("buka", true, "buka peramban setelah server siap")
	flag.Parse()
	log.SetFlags(log.Ltime)
	*alamat = alamatServer(*alamat, os.Getenv("PORT"))

	appData, err := pilihFS(*folderData, "data", "../app_data")
	if err != nil {
		log.Fatal(err)
	}
	bukti, err := pilihFS(*folderBukti, "bukti", "../bukti/hasil")
	if err != nil {
		log.Fatal(err)
	}
	web, err := pilihFS(*folderWeb, "web", "../web/out")
	if err != nil {
		log.Printf("antarmuka web tidak ditemukan (%v); hanya API yang jalan", err)
		web = nil
	}

	mulai := time.Now()
	store, err := data.Muat(appData, bukti)
	if err != nil {
		log.Fatalf("memuat data: %v", err)
	}
	log.Printf("data dimuat: %d peserta, %s", len(store.Peserta), time.Since(mulai).Round(time.Millisecond))

	ln, err := net.Listen("tcp", *alamat)
	if err != nil {
		log.Fatalf("port sudah dipakai? %v", err)
	}
	url := "http://" + ln.Addr().String()
	app := api.Baru(store, web)
	srv := &http.Server{
		Handler:           app.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      90 * time.Second, // di atas batas waktu panggilan AI
		IdleTimeout:       120 * time.Second,
		MaxHeaderBytes:    1 << 16,
	}
	go func() {
		if err := srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
	}()
	log.Printf("TEPAT siap di %s (Ctrl+C untuk berhenti)", ln.Addr())
	if *buka && web != nil && strings.HasPrefix(ln.Addr().String(), "127.") { // peramban hanya untuk pemakaian lokal
		bukaPeramban(url)
	}

	// SIGTERM dikirim Docker, Cloud Run, dan systemd saat berhenti atau deploy ulang.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go app.Jaga(ctx)
	<-ctx.Done()
	log.Print("berhenti...")
	tutup, batal := context.WithTimeout(context.Background(), 8*time.Second)
	defer batal()
	_ = srv.Shutdown(tutup)
}

// alamatServer: flag -addr menang; lalu $PORT (platform hosting, semua antarmuka); lalu hanya lokal.
func alamatServer(flag, port string) string {
	switch {
	case flag != "":
		return flag
	case port != "":
		return ":" + port
	default:
		return "127.0.0.1:8080"
	}
}

// pilihFS: folder dari flag, lalu aset tertanam, lalu folder bawaan relatif ke direktori kerja.
func pilihFS(flagFolder, namaTertanam, bawaan string) (fs.FS, error) {
	if flagFolder != "" {
		return folder(flagFolder)
	}
	if f := aset.Sub(namaTertanam); f != nil {
		return f, nil
	}
	return folder(bawaan)
}

func folder(path string) (fs.FS, error) {
	info, err := os.Stat(path)
	if err != nil || !info.IsDir() {
		return nil, fmt.Errorf("folder %s tidak ada", path)
	}
	return os.DirFS(path), nil
}

func bukaPeramban(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	if err := cmd.Start(); err != nil {
		log.Printf("buka %s di peramban", url)
	}
}
