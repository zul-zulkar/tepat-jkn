// Klien API server Go. Semua permintaan memakai kuki sesi (akun, kapasitas, keputusan).

import type { KodeRute, Tindakan } from "./tepat";

export interface Akun { kunci: string; nama: string; peran: "pusat" | "cabang"; wilayah: string[] }

export interface Sesi {
  akun: Akun | null;
  k: number;
  daftar_akun: Akun[];
  manifest: { triase_per_tanggal: string; ew_bulan_operasional: string; ew_k_persen_daftar: number;
    ew_k_orang_daftar: number; ew_n_dinilai: number };
  ai: { tersedia: boolean; alasan: string; batas_waktu: number };
  konstanta: { klaim_besar: number; jeda_kait: number; derajat: number };
}

export interface Keputusan {
  id_peserta: string; sasaran: string; kode: Tindakan; keputusan: "setuju" | "tolak"; alasan: string;
  catatan: string; waktu: string; dicatat_oleh: string;
}

export interface BarisTriase {
  id: string; rute: KodeRute; alasan: string; status_akhir: string; tunggakan_bulan: number; tunggakan_rp: number;
  kode_wilayah: string; rentang_desil: string; juga_ew: boolean;
}

export interface BarisEW {
  urut: number; peringkat: number; id: string; skor: number; alasan: string; saran: string; kode_wilayah: string;
  rute: KodeRute;
}

export interface Daftar {
  k: number; total: number; jumlah_utama: Partial<Record<Tindakan, number>>; pindah: number; n_dinilai: number;
  n_ew_daftar: number; triase: BarisTriase[]; ew: BarisEW[]; keputusan: Record<string, Keputusan>;
  wilayah_tersedia: string[]; wilayah_efektif: string[];
}

export interface Draf { sumber: string; jenis: "pesan_peserta" | "catatan_petugas"; judul: string; isi: string }

export interface Pasangan {
  tgl_reakt: string; tgl_masuk: string | null; jenis_layanan: string; cara_masuk: string; hari: number | null;
  terkait: boolean;
}

export interface Peserta {
  id: string; tgl_daftar: string; kelas: number; segmen: string; kode_wilayah: string; iuran_bulanan: number;
  autodebet: boolean; rentang_desil: string; status_akhir: string; status_sejak: string | null; rute: KodeRute;
  alasan: string; tunggakan_bulan: number; tunggakan_rp: number; n_reaktivasi: number;
  n_reakt_terkait_klaim: number; rasio_hari_aktif: number; rasio_klaim_iuran: number | null; klaim_rp: number;
  iuran_rp: number; utama: Tindakan; masuk_ew: boolean; n_ew_daftar: number; juga: Tindakan[];
  ew: null | { skor: number; peringkat: number; n_dinilai: number; bulan: string; alasan: string; saran: string;
    kontribusi: { fitur: string; nilai: number }[] };
  linimasa: {
    status: { mulai: string; selesai: string; status: string }[];
    bayar: { tgl: string; periode_awal: string; periode_akhir: string; jumlah_bulan: number; nominal: number;
      kanal: string }[];
    klaim: { tgl_masuk: string; jenis_layanan: string; cara_masuk: string; kelompok_layanan: string; biaya: number;
      denda: number }[];
    reaktivasi: { tgl: string; bulan_tertunggak: number }[];
    pasangan: Pasangan[];
  };
  draf: Draf[];
  keputusan: Keputusan | null;
}

export interface HasilAI {
  hasil: { jalur: Tindakan; draf: Draf[]; status: "ai" | "template"; cadangan: string; rinci: string;
    ringkasan_petugas: string; model: string; penyedia: string; dirapikan: number };
  keterangan: string;
}

export interface Lonjakan {
  harian: { cara_masuk: string; hari: number; hitung: number; cf: number; jendela: string }[];
  ringkasan: Record<"terjadwal" | "IGD", {
    n_kasus: number; n_hari0: number; lebih: number; lebih_ik_bawah: number; lebih_ik_atas: number; kurang: number;
    lompat: number; lompat_ik_bawah: number; lompat_ik_atas: number; ik_lompat_mencakup_0: boolean;
    denda_terhindar_rp: number | null; batas_hari: number; n_bootstrap: number }>;
  derajat: number;
}

export interface BarisKeadilan {
  dimensi: string; kelompok: string; n: number; n_jalur: number; n_periksa: number; porsi_jalur: number;
  porsi_periksa: number; rasio_jalur: number; rasio_periksa: number; status_jalur: StatusKeadilan;
  status_periksa: StatusKeadilan; jarang_jalur: boolean; jarang_periksa: boolean; porsi_pop: number;
  bagian_jalur: number; bagian_periksa: number; batas_atas: number; luar_jalur: number | null;
  luar_periksa: number | null;
}
export type StatusKeadilan = "wajar" | "perhatian" | "di_atas";
export interface Keadilan {
  tabel: BarisKeadilan[];
  info: { n: number; isi: number; k: number; m: number; baris_csv: number; cocok: number; rata_j: number;
    rata_p: number; n_wilayah: number; wil_min: number; wil_maks: number };
}

export class GalatAPI extends Error {
  constructor(public status: number, public kode: string) {
    super(kode);
  }
}

async function minta<T>(metode: string, jalur: string, badan?: unknown): Promise<T> {
  const r = await fetch(jalur, {
    method: metode, credentials: "same-origin", cache: "no-store",
    headers: badan === undefined ? undefined : { "content-type": "application/json" },
    body: badan === undefined ? undefined : JSON.stringify(badan),
  });
  if (!r.ok) {
    const isi = await r.json().catch(() => ({ galat: r.statusText }));
    throw new GalatAPI(r.status, isi.galat ?? r.statusText);
  }
  return r.json();
}

const q = (wilayah: string[]) => (wilayah.length ? `?wilayah=${encodeURIComponent(wilayah.join(","))}` : "");

export const api = {
  sesi: () => minta<Sesi>("GET", "/api/sesi"),
  masuk: (akun: string) => minta<Sesi>("POST", "/api/masuk", { akun }),
  keluar: () => minta<Sesi>("POST", "/api/keluar"),
  kapasitas: (k: number) => minta<Sesi>("PUT", "/api/kapasitas", { k }),
  daftar: (wilayah: string[]) => minta<Daftar>("GET", "/api/daftar" + q(wilayah)),
  contoh: () => minta<{ id: string; tindakan: Tindakan }[]>("GET", "/api/contoh"),
  peserta: (id: string, wilayah: string[]) => minta<Peserta>("GET", `/api/peserta/${encodeURIComponent(id)}` + q(wilayah)),
  pesan: (id: string, wilayah: string[], pakaiAI: boolean) =>
    minta<HasilAI>("POST", "/api/pesan" + q(wilayah), { id, pakai_ai: pakaiAI }),
  keputusan: (id: string, wilayah: string[], keputusan: string, alasan: string, catatan: string) =>
    minta<Keputusan>("POST", "/api/keputusan" + q(wilayah), { id, keputusan, alasan, catatan }),
  kebijakan: () => minta<Lonjakan>("GET", "/api/kebijakan"),
  keadilan: () => minta<Keadilan>("GET", "/api/keadilan"),
};
