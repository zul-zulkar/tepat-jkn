"use client";

// Daftar kerja: dua daftar (triase pola bayar, berisiko menunggak), filter wilayah, rute, dan kapasitas k.
// Satu peserta hanya mendapat satu tindakan; tindakan utama dihitung server.

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlurPerlakuan } from "@/components/AlurPerlakuan";
import { Ikon } from "@/components/Ikon";
import { useSesi } from "@/components/Sesi";
import { LabelWarna, Progres, Tabel, type Kolom } from "@/components/Tabel";
import { Info, Kartu, Kepala, Lipat, Memuat, Pesan, Pil, PilihWilayah, Saklar, Segmen, Tombol } from "@/components/ui";
import { api, type BarisEW, type BarisTriase, type Daftar, type Keputusan } from "@/lib/api";
import { alasanRapi, angka, unduhCSV } from "@/lib/format";
import { useSimpanan } from "@/lib/simpanan";
import { DESIL, EW, PERLAKUAN, RUTE, RUTE_AKSI, SARAN, STATUS, WARNA, type KodeRute } from "@/lib/tepat";

const labelKeputusan = (k?: Keputusan) => (!k ? "" : k.keputusan === "setuju" ? "Disetujui" : "Ditolak");
const pencatat = (k?: Keputusan) => (k ? k.dicatat_oleh : "");

export default function DaftarKerja() {
  const { sesi, wilayah, setWilayah, aturK } = useSesi();
  const router = useRouter();
  const akun = sesi!.akun!;
  const cabang = akun.peran === "cabang";
  const [d, setD] = useState<Daftar | null>(null);
  const [galat, setGalat] = useState("");
  const [tampil, setTampil] = useSimpanan<"triase" | "ew">("tepat_f_daftar", "triase");
  const [rute, setRute] = useSimpanan<KodeRute[]>("tepat_f_rute", RUTE_AKSI);
  const [nonaktif, setNonaktif] = useSimpanan("tepat_f_nonaktif", false);
  const [k, setK] = useState(sesi!.k);
  const [dipilih, setDipilih] = useState<string | null>(null);
  const tundaK = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setK(sesi!.k), [sesi]);
  useEffect(() => {
    let batal = false;
    api.daftar(wilayah).then((x) => { if (!batal) { setD(x); setGalat(""); } })
      .catch(() => { if (!batal) setGalat("Daftar kerja tidak bisa dimuat dari server."); });
    return () => { batal = true; };
  }, [wilayah, sesi?.k, sesi?.akun?.kunci]);
  useEffect(() => setDipilih(null), [wilayah, tampil, rute, nonaktif, sesi?.k]);

  const ubahK = (v: number) => {
    setK(v);
    if (tundaK.current) clearTimeout(tundaK.current);
    tundaK.current = setTimeout(() => void aturK(v), 250);
  };

  const ruteTriase = useMemo(() => {
    if (!d) return [];
    return d.triase.filter((b) => rute.includes(b.rute) && (!nonaktif || b.status_akhir === "nonaktif"));
  }, [d, rute, nonaktif]);

  if (galat) return <Pesan>{galat}</Pesan>;
  if (!d) return <><KepalaDaftar /><Memuat /></>;

  const adaKeputusan = Object.keys(d.keputusan).length > 0;
  const terpilihW = d.wilayah_efektif.length > 0 && !(cabang && d.wilayah_efektif.length === akun.wilayah.length);
  const hitungRute = (r: KodeRute) => d.triase.filter((b) => b.rute === r).length;
  const keKolomKeputusan = <T extends { id: string }>(kolom: Kolom<T>[]): Kolom<T>[] => {
    if (!adaKeputusan) return kolom;
    const i = kolom.findIndex((x) => x.kunci === "id") + 1;
    const kep: Kolom<T> = { kunci: "keputusan", judul: "Keputusan", lebar: 92, bantuan: "Keputusan petugas di sesi ini",
      isi: (b) => labelKeputusan(d.keputusan[b.id]) };
    const hasil = [...kolom.slice(0, i), kep, ...kolom.slice(i)];
    if (!cabang) hasil.push({ kunci: "dicatat", judul: "Dicatat oleh", lebar: 150,
      bantuan: "Akun kantor cabang yang mencatat", isi: (b) => pencatat(d.keputusan[b.id]).replace(" (contoh)", "") });
    return hasil;
  };

  const barisAksi = (jumlah: number, unduh: () => void) => (
    <div className="tp-tabel-aksi">
      <span className="jumlah"><b>{angka(jumlah)}</b> peserta{dipilih && <>, terpilih <b>{dipilih}</b></>}</span>
      <Tombol utama ikon="external-link" disabled={!dipilih} title={dipilih ? undefined : "Pilih satu baris dulu"}
        onClick={() => dipilih && router.push(`/profil/?id=${dipilih}`)}>Buka profil</Tombol>
      <Tombol ikon="download" onClick={unduh} title="Unduh daftar ini">CSV</Tombol>
    </div>
  );

  return (
    <>
      <KepalaDaftar />
      <div className="tp-baris" style={{ alignItems: "flex-end", marginBottom: "1rem" }}>
        <PilihWilayah tersedia={d.wilayah_tersedia} nilai={wilayah} onUbah={setWilayah}
          placeholder={cabang ? "Semua wilayah cabang ini" : "Semua wilayah"} />
        <Segmen label="Daftar" nilai={tampil} onUbah={setTampil} pilihan={[
          { nilai: "triase", isi: <><Ikon nama="route" ukuran={16} />Triase pola bayar <span className="n">{angka(d.triase.length)}</span></> },
          { nilai: "ew", isi: <><Ikon nama={EW.ikon} ukuran={16} />{EW.nama} <span className="n">{angka(d.ew.length)}</span></> },
        ]} />
      </div>

      <Lipat judul="Alur perlakuan: dari peserta ke satu tindakan" ikon="workflow">
        <AlurPerlakuan jumlah={d.jumlah_utama} total={d.total}
          labelMulai={"Peserta PBPU/BP mandiri" + (terpilihW ? " di wilayah terpilih" : cabang ? " di wilayah cabang ini" : "")} />
        <p className="tp-kecil">
          Pertanyaan diperiksa dari atas; jawaban ya pertama menentukan tindakan, jadi satu peserta hanya mendapat satu
          tindakan. Jumlah mengikuti filter wilayah dan kapasitas {d.k}% di daftar {EW.nama}. Kanal tiap perlakuan
          adalah usulan tim setelah coaching dan perlu dikonfirmasi BPJS.
        </p>
      </Lipat>

      {tampil === "triase" ? (
        <>
          <Kartu item={RUTE_AKSI.map((r) => ({ ikon: RUTE[r].ikon, c: RUTE[r].warna, l: RUTE[r].lembut,
            n: angka(hitungRute(r)), label: RUTE[r].nama, mati: !rute.includes(r) }))} />
          <div className="tp-baris" style={{ marginBottom: ".3rem" }}>
            <Pil label="Rute" nilai={rute} onUbah={setRute} pilihan={RUTE_AKSI.map((r) => ({
              nilai: r, warna: RUTE[r].warna,
              isi: <><Ikon nama={RUTE[r].ikon} ukuran={15} />{RUTE[r].pendek}</> }))} />
            <span className="tp-kanan" style={{ gap: ".8rem" }}>
              <Saklar label="Hanya yang nonaktif" nilai={nonaktif} onUbah={setNonaktif} title="Status per 31 Desember 2025" />
              <Info kanan>
                Rute dihitung aturan dari riwayat bayar, status, dan klaim sejak Januari 2023, posisi 31 Desember 2025.{" "}
                {angka(d.pindah)} peserta rute pengingat yang juga berisiko menunggak ditangani di daftar {EW.nama}.
                Keputusan tetap di petugas.
              </Info>
            </span>
          </div>
          {rute.length === 0 ? <p>Pilih minimal satu rute.</p> : (
            <>
              {barisAksi(ruteTriase.length, () => unduhCSV("tepat_triase.csv", ruteTriase.map((b) => ({
                id_peserta: b.id, rute: b.rute, alasan: b.alasan, status_akhir: b.status_akhir,
                tunggakan_bulan: b.tunggakan_bulan, tunggakan_rp: b.tunggakan_rp, kode_wilayah: b.kode_wilayah,
                rentang_desil: b.rentang_desil, juga_berisiko_menunggak: b.juga_ew, tindakan_utama: b.rute,
                perlakuan: PERLAKUAN[b.rute].pendek, keputusan: labelKeputusan(d.keputusan[b.id]),
                dicatat_oleh: pencatat(d.keputusan[b.id]) }))))}
              <Tabel<BarisTriase> label="Daftar triase" baris={ruteTriase} kunciBaris={(b) => b.id}
                dipilih={dipilih} onPilih={setDipilih} kolom={keKolomKeputusan<BarisTriase>([
                  { kunci: "id", judul: "ID peserta", lebar: 96, sematkan: true, isi: (b) => b.id },
                  { kunci: "rute", judul: "Rute", lebar: 124,
                    bantuan: RUTE_AKSI.map((r) => `${RUTE[r].pendek}: ${RUTE[r].nama}`).join(" | "),
                    isi: (b) => <LabelWarna teks={RUTE[b.rute].pendek} warna={RUTE[b.rute].warna} /> },
                  { kunci: "perlakuan", judul: "Perlakuan", lebar: 240,
                    bantuan: "Yang dikerjakan petugas, lewat kanal yang sudah ada. Usulan tim, perlu dikonfirmasi BPJS. Alurnya ada di bagian Alur perlakuan.",
                    isi: (b) => PERLAKUAN[b.rute].pendek },
                  { kunci: "alasan", judul: "Alasan", lebar: 420, isi: (b) => <span title={alasanRapi(b.alasan)}>{alasanRapi(b.alasan)}</span> },
                  { kunci: "status", judul: "Status", lebar: 84, isi: (b) => STATUS[b.status_akhir] ?? b.status_akhir },
                  { kunci: "tunggakan", judul: "Tunggakan", lebar: 100, angka: true,
                    bantuan: "Bulan iuran tertunggak per 31 Des 2025", isi: (b) => `${b.tunggakan_bulan} bulan` },
                  { kunci: "wilayah", judul: "Wilayah", lebar: 76, isi: (b) => b.kode_wilayah },
                  { kunci: "dtsen", judul: "DTSEN", lebar: 100, isi: (b) => DESIL[b.rentang_desil] ?? b.rentang_desil },
                  { kunci: "juga", judul: "Juga di", lebar: 150, bantuan: "Juga memenuhi daftar lain, tetapi ditangani lewat rute ini",
                    isi: (b) => (b.juga_ew ? EW.nama : "") },
                ])} />
            </>
          )}
        </>
      ) : (
        <BerisikoMenunggak d={d} k={k} ubahK={ubahK} cabang={cabang} terpilihW={terpilihW}
          barisAksi={barisAksi} dipilih={dipilih} setDipilih={setDipilih} keKolomKeputusan={keKolomKeputusan} />
      )}
    </>
  );
}

function KepalaDaftar() {
  return (
    <Kepala judul="Daftar kerja" penjelasan="Siapa yang ditangani bulan ini, lewat jalur apa, dan kenapa. Satu peserta hanya mendapat satu tindakan. Pilih satu baris di tabel untuk membuka profilnya." />
  );
}

function BerisikoMenunggak({ d, k, ubahK, cabang, terpilihW, barisAksi, dipilih, setDipilih, keKolomKeputusan }: {
  d: Daftar; k: number; ubahK: (v: number) => void; cabang: boolean; terpilihW: boolean;
  barisAksi: (n: number, unduh: () => void) => React.ReactNode; dipilih: string | null;
  setDipilih: (v: string | null) => void; keKolomKeputusan: (k: Kolom<BarisEW>[]) => Kolom<BarisEW>[];
}) {
  const keRute = d.n_ew_daftar - d.ew.length;
  const jumlahSaran = (s: string) => d.ew.filter((b) => b.saran === s).length;
  return (
    <>
      <Kartu item={[
        { ikon: EW.ikon, c: EW.warna, l: EW.lembut, n: angka(d.ew.length), label: `dari ${angka(d.n_ew_daftar)} teratas` },
        ...Object.entries(SARAN).map(([s, v]) => ({ ikon: v.ikon, c: WARNA.tinta2, l: WARNA.permukaan,
          n: angka(jumlahSaran(s)), label: v.pendek })),
      ]} />
      <div className="tp-baris" style={{ marginBottom: ".3rem", alignItems: "center" }}>
        <div className="tp-geser">
          <label className="tp-label" htmlFor="kapasitas"><Ikon nama="users" ukuran={15} /> Kapasitas petugas bulan ini</label>
          <input id="kapasitas" type="range" min={1} max={20} step={1} value={k} disabled={cabang}
            onChange={(e) => ubahK(Number(e.target.value))} aria-valuetext={`${k}% peserta aktif`} />
          <span className="nilai">{k}% peserta aktif</span>
          {cabang && <span className="tp-kecil" style={{ margin: 0 }}>Kapasitas ditetapkan Kantor Pusat: {k}%</span>}
        </div>
        <Info>
          Peserta aktif yang berisiko menunggak dalam 3 bulan ke depan menurut model peringatan dini, diurutkan dari
          peluang tertinggi. Kapasitas dihitung dari {angka(d.n_dinilai)} peserta aktif
          {terpilihW ? " di wilayah terpilih" : cabang ? " di wilayah cabang ini" : ""}; angka proposal adalah 5%, yaitu
          712 orang. {angka(keRute)} peserta juga ada di rute verifikasi, jadi ditangani lewat verifikasi.
        </Info>
      </div>
      {barisAksi(d.ew.length, () => unduhCSV("tepat_berisiko_menunggak.csv", d.ew.map((b) => ({
        ew_peringkat: b.peringkat, id_peserta: b.id, ew_skor: b.skor, ew_alasan: b.alasan, ew_saran: b.saran,
        kode_wilayah: b.kode_wilayah, rute: b.rute, peringkat_di_daftar: b.urut,
        keputusan: labelKeputusan(d.keputusan[b.id]), dicatat_oleh: pencatat(d.keputusan[b.id]) }))))}
      <Tabel<BarisEW> label="Daftar berisiko menunggak" baris={d.ew} kunciBaris={(b) => b.id} dipilih={dipilih}
        onPilih={setDipilih} kolom={keKolomKeputusan([
          { kunci: "peringkat", judul: "Peringkat", lebar: 92, angka: true, sematkan: true,
            bantuan: "Peringkat risiko di daftar kapasitas. Nomor yang tidak muncul ditangani lewat rute verifikasi.",
            isi: (b) => b.urut },
          { kunci: "id", judul: "ID peserta", lebar: 96, sematkan: true, isi: (b) => b.id },
          // dibulatkan ke bawah: skor 0,9975 tampil 99%, bukan 100% yang terkesan pasti
          { kunci: "peluang", judul: "Peluang menunggak", lebar: 170,
            bantuan: "Peluang menunggak dalam 3 bulan menurut model (data sintetis)",
            isi: (b) => <Progres nilai={Math.floor(100 * b.skor)} /> },
          { kunci: "alasan", judul: "Alasan", lebar: 360, isi: (b) => <span title={alasanRapi(b.alasan)}>{alasanRapi(b.alasan)}</span> },
          { kunci: "saran", judul: "Saran", lebar: 220, bantuan: "Perlakuan yang disarankan model",
            isi: (b) => <LabelWarna teks={SARAN[b.saran]?.pendek ?? b.saran} warna={SARAN[b.saran]?.warna ?? WARNA.tinta3} /> },
          { kunci: "wilayah", judul: "Wilayah", lebar: 76, isi: (b) => b.kode_wilayah },
          { kunci: "juga", judul: "Juga di", lebar: 110, bantuan: "Juga memenuhi rute triase ini, tetapi ditangani lewat daftar ini",
            isi: (b) => RUTE[b.rute].pendek },
        ])} />
    </>
  );
}
