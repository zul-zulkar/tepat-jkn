"use client";

import { Ikon } from "@/components/Ikon";
import { Chip, Info } from "@/components/ui";
import { type Peserta } from "@/lib/api";
import { alasanRapi, angka, bulanTahun, persen } from "@/lib/format";
import { EW, FITUR_EW, namaTindakan, PERINGATAN_DINI, RUTE, SARAN, WARNA, warnaTindakan } from "@/lib/tepat";

export function TindakanBulanIni({ p }: { p: Peserta }) {
  if (p.utama === "tanpa_tindakan") return (
    <div className="tp-tindakan" style={{ "--c": WARNA.tinta2, "--l": WARNA.permukaan } as React.CSSProperties}>
      <div className="tp-bulat"><Ikon nama="circle-check-big" ukuran={20} warna={WARNA.tinta3} /></div>
      <div><div className="lbl">Tindakan bulan ini</div><div className="isi">Tidak ada</div></div>
    </div>
  );
  const [c, l, ik] = warnaTindakan(p.utama);
  const lain = [
    ...(p.rute !== "tanpa_tindakan" && p.rute !== p.utama ? [RUTE[p.rute].pendek] : []),
    ...(p.masuk_ew && p.utama !== PERINGATAN_DINI ? [EW.nama] : []),
  ];
  return (
    <div className="tp-tindakan" style={{ "--c": c, "--l": l } as React.CSSProperties}>
      <div className="tp-bulat" style={{ color: c }}><Ikon nama={ik} ukuran={20} warna={c} /></div>
      <div><div className="lbl">Tindakan bulan ini</div><div className="isi">{namaTindakan(p.utama)}</div></div>
      {lain.length > 0 && (
        <div className="lain" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: ".2rem" }}>
          Juga masuk: {lain.join(", ")} (tidak dijalankan)
          <Info kanan>Satu peserta hanya mendapat satu tindakan. Urutan: verifikasi, cek PBI, berisiko menunggak, lalu pengingat.</Info>
        </div>
      )}
    </div>
  );
}

export function PanelRute({ p }: { p: Peserta }) {
  const R = RUTE[p.rute];
  let arti = R.arti;
  let catatan: React.ReactNode = null;
  if (p.rute === "verifikasi_pola_reaktivasi") {
    arti += " Peserta DTSEN desil 1–5 tidak pernah masuk rute ini.";
    // aturan tetap menghitung IGD (24 Okt); petugas diberi tahu bila buktinya rawat inap darurat
    const q = p.linimasa.pasangan.filter((x) => x.terkait);
    const nIGD = q.filter((x) => x.jenis_layanan === "RITL" && x.cara_masuk === "IGD").length;
    if (nIGD) catatan = (
      <div className="tp-catatan"><Ikon nama="siren" ukuran={16} warna="#8A3B14" />
        <span>{nIGD === q.length ? "Semua bukti" : `${nIGD} dari ${q.length} bukti`} berupa rawat inap darurat lewat IGD.
          Periksa apakah peserta baru melunasi karena musibah.</span></div>
    );
  }
  const triase = (
    <section className={"tp-panel" + (p.utama === p.rute ? "" : " tp-sekunder")}
      style={{ "--c": R.warna, "--l": R.lembut } as React.CSSProperties}>
      <div className="atas">
        <div className="tp-bulat"><Ikon nama={R.ikon} ukuran={20} warna={R.warna} /></div>
        <div><p className="sumber">Rute triase</p><p className="nama">{R.nama}</p></div>
        <Info kanan label="Arti rute">{arti}</Info>
      </div>
      {p.alasan && <p className="alasan">{alasanRapi(p.alasan)}</p>}
      {p.rute !== "tanpa_tindakan" && (
        <div className="tp-angka">
          <Chip teks={`Klaim besar ≤ 90 hari setelah aktif kembali: ${p.n_reakt_terkait_klaim} kali`} ikon={R.ikon}
            warna={R.warna} latar={R.lembut} />
        </div>
      )}
      {catatan}
    </section>
  );
  if (!p.ew) return triase;
  const e = p.ew;
  const maks = Math.max(...e.kontribusi.map((k) => k.nilai), 1e-9);
  return (
    <div className="tp-dua" style={{ alignItems: "start" }}>
      {triase}
      <section className={"tp-panel" + (p.utama === PERINGATAN_DINI ? "" : " tp-sekunder")}
        style={{ "--c": EW.warna, "--l": EW.lembut } as React.CSSProperties}>
        <div className="atas">
          <div className="tp-bulat"><Ikon nama={EW.ikon} ukuran={20} warna={EW.warna} /></div>
          <div><p className="sumber">{EW.namaPanjang}</p><p className="nama">Peluang {persen(e.skor, 1)}</p></div>
          <Info kanan label="Tentang skor">
            Model peringatan dini, dihitung {bulanTahun(e.bulan)}. Peringkat {angka(e.peringkat)} dari{" "}
            {angka(e.n_dinilai)} peserta aktif.{" "}
            {p.masuk_ew ? `Masuk daftar pada kapasitas saat ini (${angka(p.n_ew_daftar)} orang).`
              : "Tidak masuk daftar pada kapasitas saat ini."} Batang di bawah menunjukkan penyumbang terbesar skor.
          </Info>
        </div>
        <p className="alasan">{alasanRapi(e.alasan)}</p>
        <div className="tp-angka">
          <Chip teks={`Saran: ${SARAN[e.saran]?.nama ?? "-"}`} ikon="bell-ring" warna={EW.warna} latar={EW.lembut} />
        </div>
        {e.kontribusi.length > 0 && (
          <div className="tp-kontrib">
            {e.kontribusi.map((k) => (
              <div key={k.fitur}><span>{FITUR_EW[k.fitur] ?? k.fitur}</span><s style={{ width: `${(100 * k.nilai / maks).toFixed(0)}%` }} /></div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
