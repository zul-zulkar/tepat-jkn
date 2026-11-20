package acaknp

import "testing"

// Nilai acuan dari numpy 2.x: np.random.default_rng(seed).random(n).
func TestSamaDenganNumpy(t *testing.T) {
	kasus := []struct {
		seed  []uint32
		harap []float64
	}{
		{[]uint32{7, 1}, []float64{0.7701409510034741, 0.1119272443176843, 0.18909773329712753, 0.15995526155905015, 0.43196882203614395}},
		{[]uint32{2026}, []float64{0.17893481367543618, 0.6399131657151546, 0.4672684011434851}},
	}
	for _, k := range kasus {
		g := Baru(k.seed...)
		for i, h := range k.harap {
			if v := g.Float64(); v != h {
				t.Fatalf("seed %v ke-%d: %v, harap %v", k.seed, i, v, h)
			}
		}
	}
}
