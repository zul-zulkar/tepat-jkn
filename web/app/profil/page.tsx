"use client";

// Profil peserta: ringkasan, tindakan bulan ini, rute + alasan, linimasa 3 tahun, keputusan, draf pesan, riwayat.

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AlurPerlakuan } from "@/components/AlurPerlakuan";
import { Ikon, type NamaIkon } from "@/components/Ikon";
import { LegendaLinimasa, Linimasa } from "@/components/Linimasa";
import { DrafPesan } from "@/components/profil/DrafPesan";
import { KeputusanPetugas } from "@/components/profil/Keputusan";
import { Riwayat } from "@/components/profil/Riwayat";
import { PanelRute, TindakanBulanIni } from "@/components/profil/Tindakan";
import { useSesi } from "@/components/Sesi";
import { Chip, ChipData, JudulBagian, Kepala, Lipat, Memuat, Pesan } from "@/components/ui";
import { api, GalatAPI, type Peserta } from "@/lib/api";
import { angka, kecil, normalkanID, persen, rp, tgl } from "@/lib/format";
import {
  DESIL,
  EW,
  langkah,
  namaPendek,
  PERINGATAN_DINI,
  PERLAKUAN,
  RUTE,
  STATUS,
  STATUS_WARNA,
  WARNA,
  warnaTindakan,
  type KodeRute,
} from "@/lib/tepat";

export default function HalamanProfil() {
  return <Suspense fallback={<Memuat />}><Profil /></Suspense>;
}

function Profil() {
  const cari = useSearchParams();
  const router = useRouter();
  const { sesi, wilayah, pidTerakhir, setPidTerakhir } = useSesi();
  const pid = cari.get("id") ? normalkanID(cari.get("id")!) : pidTerakhir;
  const [p, setP] = useState<Peserta | null>(null);
  const [galat, setGalat] = useState<"" | "tidak_ada" | "di_luar_wilayah" | "server">("");
  const [teksCari, setTeksCari] = useState("");

  useEffect(() => {
    if (!pid) return;
    let batal = false;
    setP(null);
    setGalat("");
    api.peserta(pid, wilayah).then((x) => {
      if (batal) return;
      setP(x);
      setPidTerakhir(x.id);
    }).catch((e) => {
      if (batal) return;
      setGalat(e instanceof GalatAPI && e.status === 404 ? "tidak_ada"
        : e instanceof GalatAPI && e.status === 403 ? "di_luar_wilayah" : "server");
    });
    return () => { batal = true; };
  }, [pid, wilayah, sesi?.k, setPidTerakhir]);

  const atas = (
    <div className="tp-baris" style={{ alignItems: "flex-end", marginBottom: ".6rem" }}>
      <Link href="/daftar-kerja/" className="tp-tombol"><Ikon nama="arrow-left" ukuran={16} /><span>Daftar kerja</span></Link>
      <form className="tp-kanan" style={{ minWidth: 300, flexDirection: "column", alignItems: "stretch" }}
        onSubmit={(e) => {
          e.preventDefault();
          const v = normalkanID(teksCari);
          if (v) router.push(`/profil/?id=${encodeURIComponent(v)}`);
          setTeksCari("");
        }}>
        <label className="tp-label" htmlFor="cari-id"><Ikon nama="search" ukuran={15} /> Cari ID peserta</label>
        <input id="cari-id" className="tp-input" value={teksCari} onChange={(e) => setTeksCari(e.target.value)}
          placeholder="P-002329 atau 2329" autoComplete="off" />
      </form>
    </div>
  );

  if (!pid) return <>{atas}<Contoh /></>;
  if (galat === "tidak_ada") return (
    <>{atas}<Kepala judul="Profil peserta" penjelasan="Format ID: P- diikuti enam angka, misalnya P-002329." />
      <Pesan>ID <b>{pid}</b> tidak ada di data peserta mandiri. Periksa penulisannya.</Pesan></>
  );
  if (galat === "di_luar_wilayah") return (
    <>{atas}<Kepala judul="Profil peserta" penjelasan="Peserta di luar wilayah kantor cabang tidak dibuka." />
      <Pesan ikon="lock">Peserta ini di luar wilayah kantor cabang Anda.</Pesan></>
  );
  if (galat) return <>{atas}<Pesan>Profil tidak bisa dimuat dari server.</Pesan></>;
  if (!p) return <>{atas}<Memuat /></>;
  return <>{atas}<IsiProfil p={p} setP={setP} /></>;
}

function Contoh() {
  const router = useRouter();
  const [contoh, setContoh] = useState<{ id: string; tindakan: string }[] | null>(null);
  useEffect(() => { api.contoh().then(setContoh).catch(() => setContoh([])); }, []);
  return (
    <>
      <Kepala judul="Profil peserta" penjelasan="Riwayat tiga tahun, rute, alasan, dan keputusan petugas untuk satu peserta. Pilih dari daftar kerja, ketik ID, atau buka salah satu contoh." />
      <JudulBagian teks="Contoh" ikon="layers" />
      {!contoh ? <Memuat /> : (
        <div className="tp-kartu-grid">
          {contoh.map((c) => {
            const t = c.tindakan as KodeRute | typeof PERINGATAN_DINI;
            const [w, l, ik] = warnaTindakan(t);
            const label = t === PERINGATAN_DINI ? `${EW.nama}, peringkat 1` : RUTE[t].nama;
            return (
              <button key={c.id} type="button" className="tp-kartu" style={{ "--c": w, "--l": l, cursor: "pointer", textAlign: "left" } as React.CSSProperties}
                onClick={() => router.push(`/profil/?id=${c.id}`)}>
                <div className="tp-bulat"><Ikon nama={ik} ukuran={20} warna={w} /></div>
                <div><div className="n" style={{ fontSize: "1.1rem" }}>{c.id}</div><div className="l">{label}</div></div>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}

function IsiProfil({ p, setP }: { p: Peserta; setP: (p: Peserta) => void }) {
  const { sesi } = useSesi();
  const klaimBesar = sesi?.konstanta.klaim_besar ?? 1_000_000;
  const [sw, sl] = STATUS_WARNA[p.status_akhir] ?? [WARNA.tinta2, WARNA.permukaan];
  const statusTeks = (STATUS[p.status_akhir] ?? p.status_akhir) + (p.status_sejak ? ` sejak ${tgl(p.status_sejak)}` : "");
  const fakta: [NamaIkon, string, string, string][] = [
    ["wallet", "Tunggakan", `${p.tunggakan_bulan} bulan`, rp(p.tunggakan_rp)],
    ["receipt", "Iuran", rp(p.iuran_bulanan), "per bulan"],
    ["repeat", "Autodebet", p.autodebet ? "Ya" : "Tidak", ""],
    ["users", "DTSEN", DESIL[p.rentang_desil] ?? "-", ""],
    ["scale", "Klaim : iuran", p.iuran_rp && p.rasio_klaim_iuran !== null ? `${angka(p.rasio_klaim_iuran, 2)}×` : "-",
      `${rp(p.klaim_rp)} klaim`],
    ["history", "Aktif kembali", `${p.n_reaktivasi} kali`, `aktif ${persen(p.rasio_hari_aktif, 0)} waktu`],
  ];
  const LANGKAH = langkah(sesi?.konstanta.jeda_kait ?? 90);
  const noLangkah = LANGKAH.findIndex((x) => x.tindakan === p.utama) + 1;
  const ringkas = noLangkah ? `berhenti di pertanyaan ${noLangkah}, ${kecil(namaPendek(p.utama))}` : "tanpa tindakan bulan ini";

  return (
    <>
      <div className="tp-id">
        <h1>{p.id}</h1>
        <Chip teks={statusTeks} ikon="activity" warna={sw} latar={sl} />
        <Chip teks={`${p.segmen} mandiri, kelas ${p.kelas}`} />
        <Chip teks={p.kode_wilayah} ikon="map-pin" />
        <Chip teks={`Terdaftar ${tgl(p.tgl_daftar)}`} ikon="calendar" />
        <ChipData />
      </div>
      <div className="tp-fakta">
        {fakta.map(([ik, k, v, s]) => (
          <div key={k}>
            <div className="dt"><Ikon nama={ik} ukuran={14} warna={WARNA.tinta3} />{k}</div>
            <div className="dd">{v}{s && <small>{s}</small>}</div>
          </div>
        ))}
      </div>
      <TindakanBulanIni p={p} />
      <PanelRute p={p} />
      <Lipat judul={`Alur perlakuan peserta ini: ${ringkas}`} ikon="workflow">
        <AlurPerlakuan utama={p.utama} juga={p.juga} labelMulai={p.id} />
        <p className="tp-kecil">Perlakuan: {PERLAKUAN[p.utama].panjang} Kanal tiap perlakuan adalah usulan tim setelah
          coaching dan perlu dikonfirmasi BPJS. Keputusan tetap di petugas.</p>
      </Lipat>

      <JudulBagian teks="Linimasa 2023 sampai 2025" ikon="activity" penjelasan="Garis putus-putus hijau: aktif kembali. Garis oranye: klaim besar paling lama 90 hari setelah aktif kembali, angkanya jarak dalam hari. Arahkan kursor ke tanda untuk rinciannya." />
      <Linimasa p={p} klaimBesar={klaimBesar} />
      <LegendaLinimasa />

      <div className="tp-dua-tiga">
        <KeputusanPetugas p={p} setP={setP} />
        <DrafPesan p={p} />
      </div>
      <Riwayat p={p} />
    </>
  );
}
