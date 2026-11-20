// Format angka gaya Indonesia. Pembulatan meniru Python (setengah ke genap pada nilai biner persis) supaya
// angka di layar sama dengan aplikasi Streamlit dan proposal.

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
export const BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
  "September", "Oktober", "November", "Desember"];

/** round() Python: setengah ke genap. */
export function bulatGenap(x: number): number {
  const f = Math.floor(x);
  const sisa = x - f;
  if (sisa < 0.5) return f;
  if (sisa > 0.5) return f + 1;
  return f % 2 === 0 ? f : f + 1;
}

/** f"{x:.{d}f}" Python: dibulatkan benar pada nilai desimal persis, seri ke genap. */
export function tetap(x: number, d: number): string {
  if (!Number.isFinite(x)) return String(x);
  const negatif = x < 0 || Object.is(x, -0);
  const [bulat, pecahan = ""] = Math.abs(x).toFixed(100).split(".");
  let n = BigInt(bulat + pecahan.slice(0, d));
  const sisa = pecahan.slice(d).replace(/0+$/, "");
  if (sisa > "5" || (sisa.startsWith("5") && sisa.length > 1) || (sisa === "5" && n % 2n === 1n)) n += 1n;
  let s = n.toString().padStart(d + 1, "0");
  if (d > 0) s = s.slice(0, -d) + "." + s.slice(-d);
  return (negatif ? "-" : "") + s;
}

/** Angka dengan titik ribuan dan koma desimal: 1.234,5 */
export function angka(x: number, desimal = 0): string {
  const s = tetap(x, desimal);
  const [kiri, kanan] = s.split(".");
  const neg = kiri.startsWith("-");
  const digit = neg ? kiri.slice(1) : kiri;
  const ribuan = digit.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return (neg ? "-" : "") + ribuan + (kanan !== undefined ? "," + kanan : "");
}

export const rp = (x: number) => "Rp" + angka(bulatGenap(x));
export const persen = (x: number, desimal = 1) => angka(100 * x, desimal) + "%";

/** "2025-12-31" -> "31 Des 2025" */
export function tgl(iso: string): string {
  const [th, bl, hr] = iso.slice(0, 10).split("-").map(Number);
  return `${hr} ${BULAN[bl - 1]} ${th}`;
}

/** "2025-12" -> "Des 2025" */
export function bulanTahun(periode: string): string {
  const [th, bl] = periode.split("-");
  return `${BULAN[Number(bl) - 1]} ${th}`;
}

/** Hanya tampilan: "<=" jadi "≤", "1.48x" jadi "1,48×", "bln" jadi "bulan". Data tidak diubah. */
export function alasanRapi(s: string | null | undefined): string {
  if (!s) return "";
  const t = s.replaceAll("<=", "≤").replaceAll(">=", "≥")
    .replace(/(\d+)\.(\d+)x\b/g, "$1,$2×")
    .replace(/\bbln\b/g, "bulan");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** Huruf pertama kecil saja, supaya singkatan seperti H-5 dan PBI tetap utuh. */
export const kecil = (s: string) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s);

/** Angka dengan tanda minus tipografis (halaman Kebijakan). */
export const bil = (x: number, desimal = 0) => angka(x, desimal).replace("-", "−");

/** Rasio "1,23×", atau "—" bila tidak terhingga. */
export const kali = (v: number | null | undefined) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—" : `${angka(v, 2)}×`;

export function normalkanID(s: string): string {
  const t = (s || "").trim().toUpperCase().replaceAll(" ", "");
  const m = /^(?:P-?)?(\d{1,6})$/.exec(t);
  return m ? `P-${m[1].padStart(6, "0").slice(-6)}` : t;
}

/** Unduh teks sebagai CSV (BOM UTF-8 supaya Excel membaca huruf Indonesia dengan benar). */
export function unduhCSV(namaBerkas: string, baris: Record<string, unknown>[], bom = true): void {
  if (baris.length === 0) return;
  const kolom = Object.keys(baris[0]);
  const sel = (v: unknown) => {
    const s = v === null || v === undefined ? "" : typeof v === "boolean" ? (v ? "True" : "False") : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const isi = [kolom.join(","), ...baris.map((b) => kolom.map((k) => sel(b[k])).join(","))].join("\n") + "\n";
  const blob = new Blob([(bom ? "﻿" : "") + isi], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = namaBerkas;
  a.click();
  URL.revokeObjectURL(a.href);
}
