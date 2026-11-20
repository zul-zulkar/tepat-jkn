"use client";

import { Ikon } from "@/components/Ikon";
import { Tabel } from "@/components/Tabel";
import { JudulBagian, Tab } from "@/components/ui";
import { type Peserta } from "@/lib/api";
import { angka, bulanTahun, rp, tgl } from "@/lib/format";
import { KANAL, STATUS } from "@/lib/tepat";

const kapital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

export function Riwayat({ p }: { p: Peserta }) {
  const { bayar, klaim, status } = p.linimasa;
  return (
    <>
      <JudulBagian teks="Riwayat" ikon="history" penjelasan="Angka di setiap tab adalah jumlah baris: berapa kali membayar, berapa klaim, dan berapa kali status berganti sejak Januari 2023." />
      <Tab tab={[
        { kunci: "bayar", isi: <><Ikon nama="wallet" ukuran={16} />Pembayaran ({angka(bayar.length)})</> },
        { kunci: "klaim", isi: <><Ikon nama="stethoscope" ukuran={16} />Klaim ({angka(klaim.length)})</> },
        { kunci: "status", isi: <><Ikon nama="arrow-left-right" ukuran={16} />Perubahan status ({angka(status.length)})</> },
      ]}>
        {(aktif) => aktif === "bayar" ? (
          bayar.length ? <Tabel label="Riwayat pembayaran" tinggiMaks={420} baris={[...bayar].reverse()} kunciBaris={(_, i) => String(i)}
            kolom={[
              { kunci: "tgl", judul: "Tanggal bayar", lebar: 130, isi: (b) => tgl(b.tgl) },
              { kunci: "periode", judul: "Periode", lebar: 200, isi: (b) => `${bulanTahun(b.periode_awal)} sampai ${bulanTahun(b.periode_akhir)}` },
              { kunci: "bulan", judul: "Bulan dibayar", lebar: 120, angka: true, isi: (b) => b.jumlah_bulan },
              { kunci: "nominal", judul: "Nominal", lebar: 130, angka: true, isi: (b) => rp(b.nominal) },
              { kunci: "kanal", judul: "Kanal", lebar: 130, isi: (b) => KANAL[b.kanal] ?? b.kanal },
            ]} /> : <p>Belum ada pembayaran tercatat.</p>
        ) : aktif === "klaim" ? (
          klaim.length ? <Tabel label="Riwayat klaim" tinggiMaks={420} baris={[...klaim].reverse()} kunciBaris={(_, i) => String(i)}
            kolom={[
              { kunci: "tgl", judul: "Tanggal masuk", lebar: 130, isi: (k) => tgl(k.tgl_masuk) },
              { kunci: "layanan", judul: "Layanan", lebar: 120, isi: (k) => ({ RITL: "Rawat inap", RJTL: "Rawat jalan" } as Record<string, string>)[k.jenis_layanan] ?? k.jenis_layanan },
              { kunci: "cara", judul: "Cara masuk", lebar: 110, isi: (k) => ({ poli: "Poli", IGD: "IGD", terjadwal: "Terjadwal" } as Record<string, string>)[k.cara_masuk] ?? k.cara_masuk },
              { kunci: "kelompok", judul: "Kelompok", lebar: 200, isi: (k) => kapital(k.kelompok_layanan.replaceAll("_", " ")) },
              { kunci: "biaya", judul: "Biaya", lebar: 130, angka: true, isi: (k) => rp(k.biaya) },
              { kunci: "denda", judul: "Denda pelayanan", lebar: 150, angka: true, isi: (k) => (k.denda ? rp(k.denda) : "") },
            ]} /> : <p>Belum ada klaim tercatat.</p>
        ) : (
          <Tabel label="Riwayat status" tinggiMaks={420} baris={[...status].reverse()} kunciBaris={(_, i) => String(i)}
            kolom={[
              { kunci: "mulai", judul: "Mulai", lebar: 130, isi: (s) => tgl(s.mulai) },
              { kunci: "selesai", judul: "Selesai", lebar: 130, isi: (s) => tgl(s.selesai) },
              { kunci: "status", judul: "Status", lebar: 130, isi: (s) => STATUS[s.status] ?? s.status },
            ]} />
        )}
      </Tab>
    </>
  );
}
