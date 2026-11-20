// Package acaknp mereproduksi numpy.random.default_rng(seed).random() bit demi bit: SeedSequence untuk
// menurunkan state, lalu PCG64 (XSL-RR 128/64). Dipakai halaman Keadilan untuk pemecah seri yang sama dengan
// pra-registrasi bagian 3a (np.random.default_rng([7, 1])). Hanya bagian yang dipakai yang diport.
package acaknp

import "math/bits"

// Konstanta SeedSequence (numpy/random/bit_generator.pyx).
const (
	initA     = 0x43b0d7e5
	multA     = 0x931e8875
	initB     = 0x8b51f9dd
	multB     = 0x58f38ded
	mixMultL  = 0xca01f9dd
	mixMultR  = 0x4973f715
	xShift    = 16
	ukuranKol = 4
)

// Pengali PCG64 bawaan (PCG_DEFAULT_MULTIPLIER_128).
const (
	multHi = 2549297995355413924
	multLo = 4865540595714422341
)

// PCG64 adalah pembangkit dengan state 128 bit.
type PCG64 struct {
	stateHi, stateLo uint64
	incHi, incLo     uint64
}

// Baru membuat pembangkit yang sama dengan numpy.random.default_rng(entropi), entropi berupa daftar bilangan
// bulat nonnegatif yang masing-masing muat dalam 32 bit.
func Baru(entropi ...uint32) *PCG64 {
	kol := campurEntropi(entropi)
	s := hasilkanState(kol, 8) // 4 kata uint64 = 8 kata uint32, little-endian
	k := func(i int) uint64 { return uint64(s[2*i]) | uint64(s[2*i+1])<<32 }
	g := &PCG64{}
	g.setel(k(0), k(1), k(2), k(3))
	return g
}

func hashmix(nilai uint32, konst *uint32) uint32 {
	nilai ^= *konst
	*konst *= multA
	nilai *= *konst
	nilai ^= nilai >> xShift
	return nilai
}

func campur(x, y uint32) uint32 {
	h := mixMultL*x - mixMultR*y
	return h ^ (h >> xShift)
}

func campurEntropi(entropi []uint32) [ukuranKol]uint32 {
	var kol [ukuranKol]uint32
	konst := uint32(initA)
	for i := range kol {
		var e uint32
		if i < len(entropi) {
			e = entropi[i]
		}
		kol[i] = hashmix(e, &konst)
	}
	for src := range kol {
		for dst := range kol {
			if src != dst {
				kol[dst] = campur(kol[dst], hashmix(kol[src], &konst))
			}
		}
	}
	for src := ukuranKol; src < len(entropi); src++ {
		for dst := range kol {
			kol[dst] = campur(kol[dst], hashmix(entropi[src], &konst))
		}
	}
	return kol
}

func hasilkanState(kol [ukuranKol]uint32, n int) []uint32 {
	konst := uint32(initB)
	s := make([]uint32, n)
	for i := range s {
		v := kol[i%ukuranKol]
		v ^= konst
		konst *= multB
		v *= konst
		v ^= v >> xShift
		s[i] = v
	}
	return s
}

// setel = pcg64_set_seed: state = 0; inc = (initseq << 1) | 1; langkah; state += initstate; langkah.
func (g *PCG64) setel(stateHi, stateLo, incHi, incLo uint64) {
	g.incHi = incHi<<1 | incLo>>63
	g.incLo = incLo<<1 | 1
	g.stateHi, g.stateLo = 0, 0
	g.langkah()
	var c uint64
	g.stateLo, c = bits.Add64(g.stateLo, stateLo, 0)
	g.stateHi, _ = bits.Add64(g.stateHi, stateHi, c)
	g.langkah()
}

// langkah: state = state * mult + inc (mod 2^128).
func (g *PCG64) langkah() {
	hi, lo := bits.Mul64(g.stateLo, multLo)
	hi += g.stateHi*multLo + g.stateLo*multHi
	var c uint64
	lo, c = bits.Add64(lo, g.incLo, 0)
	hi, _ = bits.Add64(hi, g.incHi, c)
	g.stateHi, g.stateLo = hi, lo
}

// Uint64 mengembalikan bilangan 64 bit berikutnya.
func (g *PCG64) Uint64() uint64 {
	g.langkah()
	return bits.RotateLeft64(g.stateHi^g.stateLo, -int(g.stateHi>>58))
}

// Float64 sama dengan Generator.random(): 53 bit atas dibagi 2^53, di [0, 1).
func (g *PCG64) Float64() float64 {
	return float64(g.Uint64()>>11) * (1.0 / 9007199254740992.0)
}
