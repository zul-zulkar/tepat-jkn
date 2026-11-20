// Label, warna, dan alur keputusan TEPAT (sama dengan tepat_ui.py). Aturan rute sendiri ada di pipeline
// Python; urutan prioritas dijaga server (internal/triase).

import type { NamaIkon } from "@/components/Ikon";

export const WARNA = {
  tinta: "#12302A", tinta2: "#3D4B46", tinta3: "#5E6B66", garis: "#DCDFD7", permukaan: "#ECEBE4",
  kartu: "#FCFCF9", utama: "#17704D", utamaLembut: "#E1EEE6", mint: "#9FD8BC",
} as const;

export type KodeRute = "verifikasi_pola_reaktivasi" | "rujuk_cek_kelayakan_PBI" | "pengingat_autodebet_REHAB"
  | "nonaktif_lama_tanpa_sinyal" | "tanpa_tindakan";
export const PERINGATAN_DINI = "peringatan_dini";
export type Tindakan = KodeRute | typeof PERINGATAN_DINI;

interface InfoRute { nama: string; pendek: string; warna: string; lembut: string; ikon: NamaIkon; arti: string }

export const RUTE: Record<KodeRute, InfoRute> = {
  verifikasi_pola_reaktivasi: {
    nama: "Verifikasi pola reaktivasi", pendek: "Verifikasi", warna: "#9A3F12", lembut: "#F6E4D6",
    ikon: "search-check",
    arti: "Aktif kembali tak lama sebelum klaim besar, berulang. Petugas memeriksa riwayatnya sebelum " +
      "menindaklanjuti. Rute ini bukan tuduhan.",
  },
  rujuk_cek_kelayakan_PBI: {
    nama: "Rujuk cek kelayakan PBI", pendek: "Cek PBI", warna: "#2F5D8C", lembut: "#DCE6F1", ikon: "hand-heart",
    arti: "Menunggak dan tercatat di DTSEN desil 1–5. Peserta dirujuk untuk dicek kelayakannya sebagai " +
      "penerima bantuan iuran.",
  },
  pengingat_autodebet_REHAB: {
    nama: "Pengingat, autodebet, REHAB", pendek: "Pengingat", warna: "#17704D", lembut: "#E1EEE6",
    ikon: "bell-ring",
    arti: "Sering nonaktif lalu melunasi sendiri, dan jarang terkait klaim. Cukup pengingat, tawaran " +
      "autodebet, atau cicilan REHAB.",
  },
  nonaktif_lama_tanpa_sinyal: {
    nama: "Nonaktif lama", pendek: "Nonaktif lama", warna: "#5E6B66", lembut: "#E6E4DC", ikon: "hourglass",
    arti: "Menunggak lama tanpa pernah aktif kembali dan tanpa sinyal lain. Kemampuan bayarnya perlu diverifikasi.",
  },
  tanpa_tindakan: {
    nama: "Tanpa tindakan", pendek: "", warna: "#8F9993", lembut: "#ECEBE4", ikon: "circle-check-big",
    arti: "Tidak ada pola pembayaran yang memerlukan tindakan.",
  },
};
export const RUTE_AKSI: KodeRute[] = ["verifikasi_pola_reaktivasi", "rujuk_cek_kelayakan_PBI",
  "pengingat_autodebet_REHAB", "nonaktif_lama_tanpa_sinyal"];

// Istilah untuk pengguna internal BPJS (24 Okt): tidak dipakai di pesan ke peserta.
export const EW = { nama: "Berisiko menunggak", namaPanjang: "Berisiko menunggak 3 bulan ke depan",
  warna: "#9A5F0E", lembut: "#F5E6C8", ikon: "trending-up" as NamaIkon };

export const namaTindakan = (t: Tindakan) =>
  t === PERINGATAN_DINI ? "Pencegahan untuk peserta berisiko menunggak" : RUTE[t].nama;
export const namaPendek = (t: Tindakan) => (t === PERINGATAN_DINI ? EW.nama : RUTE[t].pendek || RUTE[t].nama);
export const warnaTindakan = (t: Tindakan): [string, string, NamaIkon] =>
  t === PERINGATAN_DINI ? [EW.warna, EW.lembut, EW.ikon] : [RUTE[t].warna, RUTE[t].lembut, RUTE[t].ikon];

// Perlakuan per tindakan lewat kanal yang sudah ada di BPJS (usulan tim setelah coaching 11 Nov).
export const PERLAKUAN: Record<Tindakan, { pendek: string; panjang: string }> = {
  verifikasi_pola_reaktivasi: { pendek: "Periksa riwayat, tawarkan autodebet",
    panjang: "Petugas memeriksa riwayatnya, lalu menawarkan autodebet dan edukasi manfaat lewat telekolekting " +
      "atau Kader JKN. Aktif kembali itu sah, jadi tanpa sanksi." },
  rujuk_cek_kelayakan_PBI: { pendek: "Rujuk cek PBI, tawarkan REHAB",
    panjang: "Dirujuk ke pengecekan kelayakan PBI. Sambil menunggu, tunggakannya bisa dicicil lewat REHAB." },
  nonaktif_lama_tanpa_sinyal: { pendek: "Kader JKN cek kemampuan bayar",
    panjang: "Kader JKN memastikan kondisi dan kemampuan bayarnya sebelum ditagih." },
  peringatan_dini: { pendek: "Pengingat sebelum jatuh tempo",
    panjang: "Diingatkan sebelum jatuh tempo tanggal 10 lewat WA blast, dengan tawaran autodebet atau pengingat " +
      "saldo autodebet." },
  pengingat_autodebet_REHAB: { pendek: "WA blast, tawarkan autodebet",
    panjang: "Cukup diingatkan lewat WA blast dan ditawari autodebet. Bila tunggakan menumpuk, cicilan REHAB." },
  tanpa_tindakan: { pendek: "Tidak dihubungi", panjang: "Tidak dihubungi bulan ini." },
};

/** Alur keputusan satu peserta; urutan sama dengan prioritas server. Jawaban "ya" pertama menang. */
export function langkah(jedaKait: number): { tindakan: Tindakan; tanya: string; syarat: string }[] {
  return [
    { tindakan: "verifikasi_pola_reaktivasi", tanya: "Aktif kembali menjelang klaim besar?",
      syarat: `Separuh atau lebih reaktivasi diikuti klaim besar ≤ ${jedaKait} hari dan aktif kurang dari separuh ` +
        "waktu, atau peserta baru langsung klaim besar lalu menunggak ≥ 6 bulan. DTSEN desil 1–5 tidak pernah masuk." },
    { tindakan: "rujuk_cek_kelayakan_PBI", tanya: "Menunggak dan tampak tidak mampu?",
      syarat: "Menunggak ≥ 3 bulan, dan DTSEN desil 1–5 atau dulu rutin bayar lalu berhenti." },
    { tindakan: "nonaktif_lama_tanpa_sinyal", tanya: "Menunggak lama tanpa pernah aktif kembali?",
      syarat: "Menunggak ≥ 12 bulan tanpa satu pun reaktivasi." },
    { tindakan: PERINGATAN_DINI, tanya: "Masih aktif, tetapi berisiko menunggak?",
      syarat: "Masuk daftar teratas model peringatan dini, sebanyak kapasitas petugas bulan ini." },
    { tindakan: "pengingat_autodebet_REHAB", tanya: "Sering nonaktif lalu melunasi sendiri?",
      syarat: "Aktif kembali ≥ 3 kali, dan tidak memenuhi pertanyaan di atas." },
  ];
}

export const SARAN: Record<string, { nama: string; pendek: string; ikon: NamaIkon; warna: string }> = {
  "pengingat_H-5_dan_tawaran_autodebet": { nama: "Pengingat H-5 dan tawaran autodebet",
    pendek: "Pengingat H-5 + autodebet", ikon: "bell-ring", warna: EW.warna },
  cek_kelayakan_PBI: { nama: "Cek kelayakan PBI", pendek: "Cek kelayakan PBI", ikon: "hand-heart",
    warna: RUTE.rujuk_cek_kelayakan_PBI.warna },
  pengingat_saldo_autodebet: { nama: "Pengingat saldo autodebet", pendek: "Pengingat saldo autodebet",
    ikon: "wallet", warna: RUTE.pengingat_autodebet_REHAB.warna },
};

export const STATUS: Record<string, string> = { aktif: "Aktif", nonaktif: "Nonaktif", masa_tunggu: "Masa tunggu" };
export const STATUS_WARNA: Record<string, [string, string]> = {
  aktif: ["#17704D", "#E1EEE6"], nonaktif: ["#9A3F12", "#F6E4D6"], masa_tunggu: ["#9A5F0E", "#F5E6C8"],
};
export const DESIL: Record<string, string> = { "1-5": "Desil 1–5", "6-10": "Desil 6–10", tidak_padan: "Tidak padan" };
export const KANAL: Record<string, string> = { autodebet: "Autodebet", va_bank: "VA bank", minimarket: "Minimarket",
  mobile_jkn: "Mobile JKN" };

export const FITUR_EW: Record<string, string> = {
  bulan_nonaktif_12: "Bulan nonaktif dalam 12 bulan terakhir",
  n_reaktivasi_12: "Aktif kembali dalam 12 bulan terakhir",
  bulan_telat_dibayar_12: "Iuran telat yang dilunasi, 12 bulan terakhir",
  log_rasio_klaim_iuran_12: "Rasio klaim terhadap iuran, 12 bulan terakhir",
  log_masa_kepesertaan: "Masa kepesertaan",
  pernah_nonaktif: "Pernah nonaktif",
  aktif_kembali_3bln: "Baru aktif kembali dalam 3 bulan",
  klaim_besar_bulan_lalu: "Klaim besar bulan lalu",
  klaim_besar_2_3bln: "Klaim besar 2–3 bulan lalu",
  klaim_besar_4_12bln: "Klaim besar 4–12 bulan lalu",
  autodebet: "Memakai autodebet",
  kelas_1: "Kelas 1",
  kelas_2: "Kelas 2",
};

export const ALASAN_TOLAK = ["Data tidak sesuai kondisi di lapangan", "Peserta sudah melunasi atau sudah ditangani",
  "Peserta tidak mampu, lebih tepat dirujuk cek PBI",
  "Ada penjelasan lain yang wajar, misalnya sakit atau kerja musiman", "Lainnya"];
