//go:build rilis

package aset

import "embed"

//go:embed all:data all:bukti all:web
var berkas embed.FS

func init() { Tertanam = berkas }
