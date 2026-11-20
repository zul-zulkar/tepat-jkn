"use client";

// Rawat inap per hari setelah peserta aktif kembali: batang kasus nyata, garis perkiraan tanpa penundaan,
// jendela uji hari 31-45 dan 46-60, dan batas denda. Port grafik Altair di halaman/kebijakan.py ke SVG.

import type { Lonjakan } from "@/lib/api";
import { angka } from "@/lib/format";
import { WARNA } from "@/lib/tepat";
import { AnimasiMasuk } from "./AnimasiMasuk";
import { useTip } from "./Tip";

const LEBAR = 600, TINGGI = 300, KIRI = 56, KANAN = 10, ATAS = 10, BAWAH = 46;

/** Kurva monoton (Fritsch-Carlson), setara interpolate="monotone". */
function pathMonoton(t: [number, number][]): string {
  const n = t.length;
  if (n < 2) return "";
  const dx = t.slice(1).map((p, i) => p[0] - t[i][0]);
  const m = t.slice(1).map((p, i) => (p[1] - t[i][1]) / dx[i]);
  const s = t.map((_, i) => (i === 0 ? m[0] : i === n - 1 ? m[n - 2]
    : m[i - 1] * m[i] <= 0 ? 0 : (3 * (dx[i - 1] + dx[i])) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i])));
  let d = `M${t[0][0]},${t[0][1]}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += `C${t[i][0] + h},${t[i][1] + h * s[i]} ${t[i + 1][0] - h},${t[i + 1][1] - h * s[i + 1]} ${t[i + 1][0]},${t[i + 1][1]}`;
  }
  return d;
}

function centangY(maks: number): number[] {
  const kasar = maks / 5;
  const pangkat = 10 ** Math.floor(Math.log10(kasar));
  const langkah = [1, 2, 5, 10].map((k) => k * pangkat).find((k) => k >= kasar) ?? pangkat * 10;
  const hasil = [];
  for (let v = 0; v <= maks; v += langkah) hasil.push(v);
  return hasil;
}

export function GrafikLonjakan({ data, cara, warna, nama, kurang, lebih, batas }: {
  data: Lonjakan["harian"]; cara: string; warna: string; nama: string;
  kurang: [number, number]; lebih: [number, number]; batas: number;
}) {
  const { wadah, tunjuk, lapisan } = useTip();
  const d = data.filter((x) => x.cara_masuk === cara && x.hari >= 1);
  const maksHari = Math.max(...data.map((x) => x.hari));
  const ymaks = Math.max(...d.map((x) => x.hitung), ...d.map((x) => x.cf)) * 1.22;
  const sx = (v: number) => KIRI + (v / (maksHari + 1)) * (LEBAR - KIRI - KANAN);
  const sy = (v: number) => TINGGI - BAWAH - (v / ymaks) * (TINGGI - ATAS - BAWAH);
  const pita: [number, number][] = [kurang, lebih];
  const diJendela = (h: number) => (h >= kurang[0] && h <= kurang[1]) || (h >= lebih[0] && h <= lebih[1]);

  return (
    <div className="tp-grafik" ref={wadah}>
      <AnimasiMasuk kunci={`${cara}-${d.length}`}>
      <svg viewBox={`0 0 ${LEBAR} ${TINGGI}`} role="img" aria-label={`${nama}: kasus per hari sejak aktif kembali`}>
        {centangY(ymaks).map((v) => (
          <g key={v}>
            <line x1={KIRI} x2={LEBAR - KANAN} y1={sy(v)} y2={sy(v)} stroke="#E6E5DE" />
            <text x={KIRI - 8} y={sy(v)} fontSize={11} fill={WARNA.tinta3} textAnchor="end" dominantBaseline="middle">{angka(v)}</text>
          </g>
        ))}
        <text transform={`translate(14 ${(ATAS + TINGGI - BAWAH) / 2}) rotate(-90)`} fontSize={11.5} fontWeight={500}
          fill={WARNA.tinta3} textAnchor="middle">Kasus per hari</text>
        {pita.map(([a, b]) => (
          <g key={a}>
            <rect x={sx(a - 0.5)} width={sx(b + 0.5) - sx(a - 0.5)} y={ATAS} height={TINGGI - ATAS - BAWAH} fill="#ECEADF" opacity={0.9} />
            <text x={sx((a + b) / 2)} y={sy(ymaks * 0.965)} fontSize={10} fontWeight={600} fill={WARNA.tinta3}
              textAnchor="middle" dominantBaseline="hanging">{a}–{b}</text>
          </g>
        ))}
        {d.map((x) => (
          <rect key={x.hari} data-anim="batang" x={sx(x.hari - 0.42)} width={sx(x.hari + 0.42) - sx(x.hari - 0.42)} y={sy(x.hitung)}
            height={sy(0) - sy(x.hitung)} rx={1.5} fill={warna} opacity={diJendela(x.hari) ? 1 : 0.45}
            {...tunjuk({ judul: nama, teks: `Hari ke-${x.hari}: ${x.hitung} kasus, perkiraan ${angka(x.cf, 1)}` })} />
        ))}
        <path data-anim="garis" d={pathMonoton(d.map((x) => [sx(x.hari), sy(x.cf)]))} fill="none" stroke={WARNA.tinta} strokeWidth={2} />
        <line x1={sx(batas + 0.5)} x2={sx(batas + 0.5)} y1={ATAS} y2={TINGGI - BAWAH} stroke={WARNA.tinta3}
          strokeWidth={1.3} strokeDasharray="4 3" />
        <text x={sx(batas - 0.6)} y={sy(ymaks * 0.8)} fontSize={10.5} fill={WARNA.tinta3} textAnchor="end">batas denda</text>
        <line x1={KIRI} x2={LEBAR - KANAN} y1={sy(0)} y2={sy(0)} stroke={WARNA.garis} />
        {[1, 15, 30, 45, 60, 90, 120].filter((v) => v <= maksHari + 1).map((v) => (
          <g key={v}>
            <line x1={sx(v)} x2={sx(v)} y1={sy(0)} y2={sy(0) + 5} stroke={WARNA.garis} />
            <text x={sx(v)} y={sy(0) + 17} fontSize={11} fill={WARNA.tinta3} textAnchor="middle">{v}</text>
          </g>
        ))}
        <text x={(KIRI + LEBAR - KANAN) / 2} y={TINGGI - 6} fontSize={11.5} fontWeight={500} fill={WARNA.tinta3}
          textAnchor="middle">Hari sejak aktif kembali sampai masuk rawat inap</text>
      </svg>
      </AnimasiMasuk>
      {lapisan}
    </div>
  );
}
