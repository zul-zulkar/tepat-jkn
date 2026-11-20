package main

import "testing"

func TestAlamatServer(t *testing.T) {
	for _, c := range []struct{ flag, port, harap string }{
		{"", "", "127.0.0.1:8080"},
		{"", "8080", ":8080"},
		{"0.0.0.0:9000", "8080", "0.0.0.0:9000"},
		{"127.0.0.1:1", "", "127.0.0.1:1"},
	} {
		if got := alamatServer(c.flag, c.port); got != c.harap {
			t.Errorf("alamatServer(%q, %q) = %q, harap %q", c.flag, c.port, got, c.harap)
		}
	}
}
