"use client";

// Tabel ringan dengan header tetap, kolom tersemat, dan baris virtual (hanya baris yang terlihat yang dirender),
// cukup untuk ribuan peserta tanpa pustaka tambahan. Bila onPilih diberikan, satu baris bisa dipilih.

import { useMemo, useRef, useState, type ReactNode } from "react";
import { Info } from "./ui";

export interface Kolom<T> {
  kunci: string;
  judul: string;
  lebar: number;
  isi: (b: T) => ReactNode;
  angka?: boolean;
  bantuan?: string;
  sematkan?: boolean;
}

const TINGGI_BARIS = 35;
const TINGGI_KEPALA = 38;
const CADANGAN = 12;

export function Tabel<T>({ baris, kolom, kunciBaris, dipilih, onPilih, tinggiMaks = 600, label }: {
  baris: T[]; kolom: Kolom<T>[]; kunciBaris: (b: T, i: number) => string; dipilih?: string | null;
  onPilih?: (kunci: string | null) => void; tinggiMaks?: number; label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [gulir, setGulir] = useState(0);
  const tinggi = Math.min(tinggiMaks, TINGGI_KEPALA + TINGGI_BARIS * Math.max(baris.length, 1) + 2);
  const awal = Math.max(0, Math.floor(gulir / TINGGI_BARIS) - CADANGAN);
  const akhir = Math.min(baris.length, Math.ceil((gulir + tinggi) / TINGGI_BARIS) + CADANGAN);
  const pilih = onPilih !== undefined;
  const kiri = useMemo(() => {
    // posisi kiri kolom tersemat (kolom pilih + kolom sematkan berurutan dari kiri)
    const pos: number[] = [];
    let x = pilih ? 34 : 0;
    for (const k of kolom) { pos.push(x); x += k.lebar; }
    return pos;
  }, [kolom, pilih]);

  return (
    <div ref={ref} className={"tp-tabel" + (pilih ? " pilih" : "")} style={{ maxHeight: tinggi }}
      onScroll={(e) => setGulir(e.currentTarget.scrollTop)} role="region" aria-label={label} tabIndex={0}>
      <table>
        <colgroup>
          {pilih && <col style={{ width: 34 }} />}
          {kolom.map((k) => <col key={k.kunci} style={{ width: k.lebar }} />)}
        </colgroup>
        <thead>
          <tr>
            {pilih && <th className="pilih-sel sematkan" style={{ left: 0 }} aria-label="Pilih" />}
            {kolom.map((k, i) => (
              <th key={k.kunci} className={(k.angka ? "angka " : "") + (k.sematkan ? "sematkan" : "")}
                style={k.sematkan ? { left: kiri[i] } : undefined}>
                <span className="kepala-kol">
                  {k.judul}
                  {k.bantuan && <Info label={`Tentang kolom ${k.judul}`}>{k.bantuan}</Info>}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {awal > 0 && <tr aria-hidden="true" style={{ height: awal * TINGGI_BARIS }} />}
          {baris.slice(awal, akhir).map((b, j) => {
            const kunci = kunciBaris(b, awal + j);
            const aktif = kunci === dipilih;
            return (
              <tr key={kunci} className={aktif ? "dipilih" : ""} aria-selected={pilih ? aktif : undefined}
                onClick={pilih ? () => onPilih(aktif ? null : kunci) : undefined}>
                {pilih && <td className="pilih-sel sematkan" style={{ left: 0 }}><span className="bulatan" /></td>}
                {kolom.map((k, i) => (
                  <td key={k.kunci} className={(k.angka ? "angka " : "") + (k.sematkan ? "sematkan" : "")}
                    style={k.sematkan ? { left: kiri[i] } : undefined}>
                    {k.isi(b)}
                  </td>
                ))}
              </tr>
            );
          })}
          {akhir < baris.length && <tr aria-hidden="true" style={{ height: (baris.length - akhir) * TINGGI_BARIS }} />}
        </tbody>
      </table>
    </div>
  );
}

/** Label berwarna satu nilai (rute, saran). */
export function LabelWarna({ teks, warna }: { teks: string; warna: string }) {
  return teks ? <span className="tp-label-warna" style={{ background: warna }}>{teks}</span> : null;
}

/** Batang persentase 0-100. */
export function Progres({ nilai }: { nilai: number }) {
  return (
    <span className="tp-progres">
      <span><i style={{ width: `${Math.max(0, Math.min(100, nilai))}%` }} /></span>
      <b>{nilai}%</b>
    </span>
  );
}
