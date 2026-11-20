"use client";

// Kebijakan: uji lonjakan hari ke-45, rawat inap terjadwal dibanding plasebo IGD (untuk unit kebijakan).
// Ukuran ujinya LOMPATAN (kekurangan hari 31-45 + kelebihan hari 46-60), bukan kelebihan saja. Lompatan bukan
// jumlah rawat inap yang ditunda; perkiraan yang ditunda adalah KELEBIHAN di hari 46-60.

import { useEffect, useState } from "react";
import { GrafikLonjakan } from "@/components/GrafikLonjakan";
import { Ikon, type NamaIkon } from "@/components/Ikon";
import { Chip, JudulBagian, Kartu, Kepala, Lipat, Memuat, Pesan } from "@/components/ui";
import { api, type Lonjakan } from "@/lib/api";
import { angka, bil, bulatGenap } from "@/lib/format";
import { WARNA } from "@/lib/tepat";

const PANEL = {
  terjadwal: { nama: "Rawat inap terjadwal", sumber: "Bisa ditunda", warna: "#9A5F0E", lembut: "#F5E6C8", ikon: "calendar" as NamaIkon },
  IGD: { nama: "Rawat inap darurat lewat IGD", sumber: "Pembanding: tidak bisa ditunda", warna: "#B24A2B", lembut: "#F6E4D6", ikon: "siren" as NamaIkon },
};
type Cara = keyof typeof PANEL;

const rentang = (lo: number, hi: number) => (bulatGenap(lo) < 0 ? `${bil(lo)} s.d. ${bil(hi)}` : `${bil(lo)}–${bil(hi)}`);
const hariTeks = ([a, b]: [number, number]) => `${a}–${b}`;

export default function Kebijakan() {
  const [d, setD] = useState<Lonjakan | null>(null);
  const [galat, setGalat] = useState(false);
  useEffect(() => { api.kebijakan().then(setD).catch(() => setGalat(true)); }, []);
  if (galat) return <Pesan>Data uji lonjakan tidak bisa dimuat dari server.</Pesan>;
  if (!d) return <Memuat />;

  const jendela = (nama: string): [number, number] => {
    const h = d.harian.filter((x) => x.jendela === nama).map((x) => x.hari);
    return [Math.min(...h), Math.max(...h)];
  };
  const KURANG = jendela("kurang_31_45"), LEBIH = jendela("lebih_46_60");
  const rt = d.ringkasan.terjadwal, ri = d.ringkasan.IGD;
  const BATAS = rt.batas_hari;
  const MAKS = Math.max(...d.harian.map((x) => x.hari));
  const ada = (c: Cara) => !d.ringkasan[c].ik_lompat_mencakup_0 && d.ringkasan[c].lompat > 0;
  const tAda = ada("terjadwal"), iAda = ada("IGD");

  let vonis: string, cV: string, lV: string, ikV: NamaIkon, rinci: string;
  if (tAda && !iAda) {
    [vonis, cV, lV, ikV] = ["Lonjakan hanya muncul pada rawat inap yang bisa ditunda", "#9A5F0E", "#F5E6C8", "trending-up"];
    rinci = `Rawat inap terjadwal menumpuk tepat setelah hari ke-${BATAS}; rawat inap darurat tidak. Pola ini cocok dengan peserta yang menunda rawat inap sampai denda pelayanan tidak berlaku lagi.`;
  } else if (tAda && iAda) {
    [vonis, cV, lV, ikV] = ["Pembanding IGD ikut melonjak", "#9A3F12", "#F6E4D6", "circle-x"];
    rinci = "Lonjakan rawat inap terjadwal belum bisa dibaca sebagai penundaan. Periksa kurva perkiraan dan rawat inap terencana yang masuk lewat IGD.";
  } else {
    [vonis, cV, lV, ikV] = [`Tidak ada lonjakan yang terdeteksi setelah hari ke-${BATAS}`, WARNA.tinta2, WARNA.permukaan, "circle-check-big"];
    rinci = "Bukan bukti tidak ada penundaan: penundaan kecil bisa lolos dari uji ini.";
  }

  const kartu = [
    { ikon: "calendar" as NamaIkon, c: PANEL.terjadwal.warna, l: PANEL.terjadwal.lembut, n: bil(rt.lompat),
      label: "Lompatan rawat inap terjadwal",
      ket: `Rentang 95%: ${rentang(rt.lompat_ik_bawah, rt.lompat_ik_atas)}` + (tAda ? ", di atas nol" : ", mencakup nol") },
    { ikon: "siren" as NamaIkon, c: PANEL.IGD.warna, l: PANEL.IGD.lembut, n: bil(ri.lompat), label: "Lompatan IGD (pembanding)",
      ket: `Rentang 95%: ${rentang(ri.lompat_ik_bawah, ri.lompat_ik_atas)}` + (iAda ? ", di atas nol" : ", mencakup nol") },
    { ikon: "trending-up" as NamaIkon, c: WARNA.utama, l: WARNA.utamaLembut, n: bil(rt.lebih),
      label: `Perkiraan rawat inap yang ditunda ke hari ${hariTeks(LEBIH)}`,
      ket: `Rentang 95%: ${rentang(rt.lebih_ik_bawah, rt.lebih_ik_atas)}` },
    ...(rt.denda_terhindar_rp !== null ? [{ ikon: "receipt" as NamaIkon, c: WARNA.tinta2, l: WARNA.permukaan,
      n: `Rp${angka(bulatGenap(rt.denda_terhindar_rp / 1e6))} juta`, label: "Perkiraan denda pelayanan yang lolos",
      ket: "Biaya klaim sintetis; satu rawat inap per aktif kembali, denda paling tinggi Rp20 juta" }] : []),
  ];

  const ringkasJendela = (cara: Cara) => {
    const r = d.ringkasan[cara];
    return (
      <div className="tp-jendela">
        {([[KURANG, "sebelum batas", -r.kurang], [LEBIH, "sesudah batas", r.lebih]] as [[number, number], string, number][]).map(([[a, b], nama, selisih]) => {
          const w = d.harian.filter((x) => x.cara_masuk === cara && x.hari >= a && x.hari <= b);
          const turun = bulatGenap(selisih) < 0;
          return (
            <div key={nama}>
              Hari {a}–{b}, {nama}<b>{angka(w.reduce((s, x) => s + x.hitung, 0))} kasus</b>
              perkiraan {angka(bulatGenap(w.reduce((s, x) => s + x.cf, 0)))} →{" "}
              <span className={turun ? "turun" : "naik"}>{turun ? "kurang" : "lebih"} {angka(Math.abs(bulatGenap(selisih)))}</span>
            </div>
          );
        })}
      </div>
    );
  };

  const kotak = (c: string) => <i style={{ width: 12, height: 9, borderRadius: 2, background: c }} />;
  return (
    <>
      <Kepala judul="Uji lonjakan hari ke-45" penjelasan={`Apakah peserta menunda rawat inap terjadwal sampai denda pelayanan ${BATAS} hari setelah aktif kembali lewat? Rawat inap darurat lewat IGD menjadi pembanding karena tidak bisa ditunda. Untuk unit kebijakan BPJS Kesehatan, dilaporkan per kuartal.`} />
      <div className="tp-tindakan" style={{ "--c": cV, "--l": lV } as React.CSSProperties}>
        <div className="tp-bulat"><Ikon nama={ikV} ukuran={20} warna={cV} /></div>
        <div style={{ flex: "1 1 320px" }}>
          <div className="lbl">Hasil uji</div>
          <div className="isi">{vonis}</div>
          <div className="lain" style={{ marginTop: ".2rem" }}>{rinci}</div>
          <div className="lain" style={{ marginTop: ".35rem", display: "flex", gap: ".35rem", alignItems: "flex-start" }}>
            <Ikon nama="flask-conical" ukuran={14} warna={WARNA.tinta2} />
            <span>Data sintetis: penundaan sengaja dibuat di data buatan untuk menguji alat ini. Halaman ini menunjukkan ujinya bisa menemukan pola itu, bukan bahwa peserta asli menunda.</span>
          </div>
        </div>
      </div>
      <Kartu item={kartu} />

      <JudulBagian teks="Rawat inap per hari setelah peserta aktif kembali" ikon="activity"
        penjelasan={`Batang: kasus nyata per hari. Garis: perkiraan jumlah kasus kalau tidak ada yang menunda, dari kurva yang dipasang ke hari 1–${KURANG[0] - 1} dan ${LEBIH[1] + 1}–${MAKS}. Hari 0 tidak digambar. Sumbu tegak tiap grafik berbeda karena jumlah kasusnya berbeda.`} />
      <div className="tp-legenda-lini" style={{ marginBottom: ".7rem" }}>
        <span>{kotak(PANEL.terjadwal.warna)}{kotak(PANEL.IGD.warna)}Kasus nyata per hari</span>
        <span><i style={{ width: 18, height: 2, background: WARNA.tinta }} />Perkiraan tanpa penundaan</span>
        <span>{kotak("#DDD9CC")}Jendela uji: hari {hariTeks(KURANG)} dan {hariTeks(LEBIH)}</span>
        <span><i style={{ width: 0, height: 12, borderLeft: `1.5px dashed ${WARNA.tinta3}` }} />Batas denda hari ke-{BATAS}</span>
      </div>
      <div className="tp-dua">
        {(["terjadwal", "IGD"] as Cara[]).map((cara) => {
          const P = PANEL[cara], r = d.ringkasan[cara];
          return (
            <div key={cara} className="tp-panel-kotak">
              <div className="tp-grafik-kepala" style={{ "--c": P.warna, "--l": P.lembut } as React.CSSProperties}>
                <div className="tp-bulat"><Ikon nama={P.ikon} ukuran={20} warna={P.warna} /></div>
                <div><p className="sumber">{P.sumber}</p><p className="nama">{P.nama}</p></div>
                <span className="vonis">{ada(cara)
                  ? <Chip teks="Ada lonjakan" ikon="trending-up" warna="#9A3F12" latar="#F6E4D6" />
                  : <Chip teks="Tidak ada lonjakan" ikon="circle-check-big" warna={WARNA.utama} latar={WARNA.utamaLembut} />}</span>
              </div>
              <GrafikLonjakan data={d.harian} cara={cara} warna={P.warna} nama={P.nama} kurang={KURANG} lebih={LEBIH} batas={BATAS} />
              {ringkasJendela(cara)}
              <p className="tp-catatan-kecil">Lompatan = kekurangan sebelum batas + kelebihan sesudah batas ={" "}
                {bil(r.kurang, 1)} + {bil(r.lebih, 1)} = <b style={{ color: WARNA.tinta }}>{bil(r.lompat, 1)}</b>, dibulatkan{" "}
                {bil(r.lompat)}. Total kasus hari 1–{MAKS}: {angka(r.n_kasus - r.n_hari0)}.</p>
            </div>
          );
        })}
      </div>

      <JudulBagian teks="Cara membaca untuk pembuat aturan" ikon="gavel" />
      <ol className="tp-baca">
        <li>Denda pelayanan berlaku untuk rawat inap dalam {BATAS} hari pertama setelah peserta aktif kembali. Kalau peserta
          menunda, kasus berkurang di hari {hariTeks(KURANG)} dan menumpuk di hari {hariTeks(LEBIH)}. Lompatan menjumlahkan
          kedua perubahan itu.</li>
        <li>Keadaan darurat tidak bisa ditunda. Kalau IGD ikut melonjak, yang salah alat ukurnya, bukan perilaku peserta.
          Karena itu lonjakan rawat inap terjadwal hanya dibaca bila IGD tidak melonjak.</li>
        <li>Perkiraan rawat inap yang ditunda adalah kelebihan di hari {hariTeks(LEBIH)} (<b>{bil(rt.lebih)}</b>), bukan
          lompatan (<b>{bil(rt.lompat)}</b>). Lompatan menghitung kasus yang pindah dua kali: sekali saat hilang, sekali saat
          muncul.</li>
        <li>Penundaan berarti dua hal: denda tidak tertagih, dan perawatan yang sudah direncanakan bergeser lebih lambat.
          Hasil ini bahan evaluasi aturan denda. Keputusannya tetap di pembuat kebijakan.</li>
      </ol>
      <div style={{ height: "1rem" }} />
      <Lipat judul="Batas uji ini" ikon="ruler">
        <ul className="tp-baca">
          <li><b>Data sintetis.</b> Penundaan sengaja dibuat di data buatan. Di data asli, hasilnya bisa nol.</li>
          <li><b>Kurva perkiraan bisa terlalu rendah</b> di hari {KURANG[0]}–{LEBIH[1]}. Di IGD, kelebihan hari {hariTeks(LEBIH)} saja
            sudah {bil(ri.lebih)} kasus (rentang 95%: {rentang(ri.lebih_ik_bawah, ri.lebih_ik_atas)}), padahal tidak ada yang
            menunda. Karena itu ukurannya lompatan, bukan kelebihan saja.</li>
          <li><b>Penundaan kecil bisa lolos.</b> Hasil &quot;tidak ada lonjakan&quot; bukan bukti tidak ada penundaan. Data nasional jauh
            lebih besar, jadi ujinya lebih peka.</li>
          <li><b>IGD di data asli</b> bisa memuat sebagian rawat inap terencana. Pembanding bisa ikut naik sedikit.</li>
          <li><b>Hari 0</b> (melunasi tunggakan di hari masuk rumah sakit) tidak dihitung dalam kurva: {angka(rt.n_hari0)} rawat inap
            terjadwal dan {angka(ri.n_hari0)} IGD. Itu pola lain, dipantau lewat triase.</li>
          <li><b>Metode.</b> Kurva polinomial derajat {d.derajat} dan {angka(rt.n_bootstrap)} sampel bootstrap. Untuk data asli, pakai
            metode dengan batasan integrasi (Chetty dkk. 2011; Kleven 2016).</li>
        </ul>
      </Lipat>
    </>
  );
}
