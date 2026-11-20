// Package aset menyediakan data dan antarmuka yang ditanam ke dalam berkas program pada build rilis
// (tag "rilis"; lihat rilis.sh). Build biasa tidak menanam apa pun dan membaca dari folder repo.
package aset

import "io/fs"

// Tertanam berisi data/ (app_data), bukti/ (bukti/hasil), dan web/ (hasil next build), atau nil.
var Tertanam fs.FS

// Sub mengembalikan subfolder aset tertanam, atau nil bila tidak ada yang ditanam.
func Sub(nama string) fs.FS {
	if Tertanam == nil {
		return nil
	}
	f, err := fs.Sub(Tertanam, nama)
	if err != nil {
		return nil
	}
	return f
}
