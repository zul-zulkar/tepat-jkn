"use client";

// Linimasa tiga tahun satu peserta (2023-2025): status, pembayaran iuran, klaim, aktif kembali, dan pasangan
// "aktif kembali lalu klaim besar <= 90 hari". Port grafik Altair di halaman/profil_peserta.py ke SVG.

import { Fragment } from "react";
import type { Peserta } from "@/lib/api";
import { kecil, rp, tgl } from "@/lib/format";
import { KANAL, STATUS, WARNA } from "@/lib/tepat";
import { AnimasiMasuk } from "./AnimasiMasuk";
import { useTip } from "./Tip";

export const KAT: Record<string, string> = {
  Aktif: "#CBE5D7", Nonaktif: "#F1D3C4", "Masa tunggu": "#F3E3BF",
  "Iuran 1 bulan": "#8F9993", "Melunasi beberapa bulan": WARNA.utama,
  "Rawat jalan": "#C5CCC8", "Rawat jalan ≥ Rp1 juta": "#5E6B66",
  "Rawat inap terjadwal": "#9A5F0E", "Rawat inap lewat IGD": "#B24A2B",
};

const LEBAR = 1000, TINGGI = 236, KIRI = 112, KANAN = 12, ATAS = 8, BAWAH = 30;
const BARIS = ["Status", "Iuran dibayar", "Klaim"];
const AWAL = Date.UTC(2023, 0, 1), AKHIR = Date.UTC(2026, 0, 1);
const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const waktu = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const x = (ms: number) => KIRI + ((ms - AWAL) / (AKHIR - AWAL)) * (LEBAR - KIRI - KANAN);
// skala pita: paddingInner 0,3, paddingOuter 0,15 (sama dengan grafik Altair)
const tinggiPlot = TINGGI - ATAS - BAWAH;
const langkah = tinggiPlot / (BARIS.length - 0.3 + 0.3);
const pita = langkah * 0.7;
const yBaris = (i: number) => ATAS + langkah * 0.15 + i * langkah;
const tengah = (i: number) => yBaris(i) + pita / 2;

function kategoriKlaim(k: Peserta["linimasa"]["klaim"][number], klaimBesar: number): string {
  if (k.jenis_layanan === "RITL" && k.cara_masuk === "terjadwal") return "Rawat inap terjadwal";
  if (k.jenis_layanan === "RITL" && k.cara_masuk === "IGD") return "Rawat inap lewat IGD";
  if (k.jenis_layanan === "RJTL" && k.biaya >= klaimBesar) return "Rawat jalan ≥ Rp1 juta";
  return "Rawat jalan";
}

export function Linimasa({ p, klaimBesar }: { p: Peserta; klaimBesar: number }) {
  const { wadah, tunjuk, lapisan } = useTip();
  const { status, bayar, klaim, reaktivasi, pasangan } = p.linimasa;
  const terkait = pasangan.filter((q) => q.terkait && q.tgl_masuk);
  const centang: number[] = [];
  for (let th = 2023; th <= 2025; th++) for (let bl = 0; bl < 12; bl += 3) centang.push(Date.UTC(th, bl, 1));
  centang.push(AKHIR);

  return (
    <div className="tp-grafik" ref={wadah}>
      <AnimasiMasuk kunci={p.id}>
      <svg viewBox={`0 0 ${LEBAR} ${TINGGI}`} role="img" aria-label={`Linimasa 2023 sampai 2025 peserta ${p.id}`}>
        {centang.map((t) => (
          <Fragment key={t}>
            <line x1={x(t)} x2={x(t)} y1={ATAS} y2={TINGGI - BAWAH} stroke="#E6E5DE" />
            <text x={x(t)} y={TINGGI - BAWAH + 18} fontSize={11} fill={WARNA.tinta3} textAnchor="middle">
              {BULAN[new Date(t).getUTCMonth()] + (new Date(t).getUTCMonth() === 0 ? " " + new Date(t).getUTCFullYear() : "")}
            </text>
          </Fragment>
        ))}
        {BARIS.map((b, i) => (
          <text key={b} x={KIRI - 10} y={tengah(i)} fontSize={12} fontWeight={600} fill={WARNA.tinta2}
            textAnchor="end" dominantBaseline="middle">{b}</text>
        ))}

        {status.map((s, i) => {
          const kat = STATUS[s.status] ?? s.status;
          const x1 = x(waktu(s.mulai)), x2 = x(waktu(s.selesai) + 86400000);
          return <rect key={i} data-anim="pita" x={x1} y={yBaris(0)} width={Math.max(x2 - x1, 0.5)} height={pita} rx={3} fill={KAT[kat]}
            {...tunjuk({ judul: "Status", teks: `${kat}, ${tgl(s.mulai)} sampai ${tgl(s.selesai)}` })} />;
        })}

        {reaktivasi.map((r, i) => (
          <g key={i} {...tunjuk({ judul: "Reaktivasi", teks: `Aktif kembali ${tgl(r.tgl)}, melunasi ${r.bulan_tertunggak} bulan tertunggak` })}>
            <line x1={x(waktu(r.tgl))} x2={x(waktu(r.tgl))} y1={ATAS} y2={TINGGI - BAWAH} stroke="#1E8A5F"
              strokeWidth={1.2} strokeDasharray="3 3" opacity={0.7} />
            <line x1={x(waktu(r.tgl))} x2={x(waktu(r.tgl))} y1={ATAS} y2={TINGGI - BAWAH} stroke="transparent" strokeWidth={8} />
          </g>
        ))}

        {bayar.map((b, i) => {
          const banyak = b.jumlah_bulan > 1;
          const h = banyak ? 26 : 14;
          const bx = x(waktu(b.tgl));
          return (
            <g key={i} {...tunjuk({ judul: "Pembayaran", teks: `${tgl(b.tgl)}: ${b.jumlah_bulan} bulan, ${rp(b.nominal)} lewat ${KANAL[b.kanal] ?? b.kanal}` })}>
              <line x1={bx} x2={bx} y1={tengah(1) - h / 2} y2={tengah(1) + h / 2}
                stroke={banyak ? KAT["Melunasi beberapa bulan"] : KAT["Iuran 1 bulan"]} strokeWidth={banyak ? 3 : 1.4} />
              <line x1={bx} x2={bx} y1={tengah(1) - 14} y2={tengah(1) + 14} stroke="transparent" strokeWidth={6} />
            </g>
          );
        })}

        {terkait.map((q, i) => {
          const x1 = x(waktu(q.tgl_reakt)), x2 = x(waktu(q.tgl_masuk!));
          return (
            <g key={i} {...tunjuk({ judul: "Pola", teks: `Aktif kembali ${tgl(q.tgl_reakt)}, klaim besar ${q.hari} hari kemudian (${tgl(q.tgl_masuk!)})` })}>
              <line x1={x1} x2={x2} y1={tengah(2)} y2={tengah(2)} stroke="#9A5F0E" strokeWidth={3} opacity={0.5} />
              <text x={(x1 + x2) / 2} y={tengah(2) + (i % 2 === 0 ? -14 : 16)} fontSize={11} fontWeight={700}
                fill="#7A4A0B" textAnchor="middle" dominantBaseline="middle">{q.hari} hari</text>
            </g>
          );
        })}

        {klaim.map((k, i) => {
          const kat = kategoriKlaim(k, klaimBesar);
          const luas = 18 + (420 - 18) * Math.sqrt(Math.max(k.biaya, 0) / 25_000_000);
          const teks = `${tgl(k.tgl_masuk)}: ${kecil(kat)}, ${k.kelompok_layanan.replaceAll("_", " ")}, ${rp(k.biaya)}` +
            (k.denda ? `, denda pelayanan ${rp(k.denda)}` : "");
          return <circle key={i} cx={x(waktu(k.tgl_masuk))} cy={tengah(2)} r={Math.sqrt(luas / Math.PI)} fill={KAT[kat]}
            opacity={0.92} stroke="#FFFFFF" strokeWidth={0.8} {...tunjuk({ judul: "Klaim", teks })} />;
        })}
      </svg>
      </AnimasiMasuk>
      {lapisan}
    </div>
  );
}

export function LegendaLinimasa() {
  const kotak = (c: string) => <i style={{ width: 12, height: 9, borderRadius: 2, background: c }} />;
  const garis = (c: string, w: number, h: number) => <i style={{ width: w, height: h, background: c }} />;
  const bulat = (c: string, d: number) => <i style={{ width: d, height: d, borderRadius: "50%", background: c }} />;
  const item: [React.ReactNode, string][] = [
    [kotak(KAT.Aktif), "Aktif"], [kotak(KAT.Nonaktif), "Nonaktif"], [kotak(KAT["Masa tunggu"]), "Masa tunggu"],
    [garis(KAT["Iuran 1 bulan"], 2, 12), "Iuran 1 bulan"], [garis(WARNA.utama, 3, 16), "Melunasi beberapa bulan"],
    [bulat(KAT["Rawat jalan"], 8), "Rawat jalan"], [bulat(KAT["Rawat jalan ≥ Rp1 juta"], 9), "Rawat jalan ≥ Rp1 juta"],
    [bulat(KAT["Rawat inap terjadwal"], 10), "Rawat inap terjadwal"], [bulat(KAT["Rawat inap lewat IGD"], 10), "Rawat inap IGD"],
    [<i key="r" style={{ width: 0, height: 14, borderLeft: "1.5px dashed #1E8A5F" }} />, "Aktif kembali"],
    [garis("#D9B88C", 18, 3), "Klaim besar ≤ 90 hari"],
  ];
  return (
    <div className="tp-legenda-lini">
      {item.map(([b, t]) => <span key={t}>{b}{t}</span>)}
    </div>
  );
}
