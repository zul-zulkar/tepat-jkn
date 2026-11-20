"use client";

// Panel keadilan dan bukti: seberapa sering tiap kelompok peserta masuk jalur verifikasi, dibanding rata-rata
// semua peserta. Dihitung server tanpa label. Ambang 2x dikunci di pra-registrasi (T4); "perlu perhatian" dan
// "jarang diperiksa" ditambahkan sesudah hasil dilihat.

import { useEffect, useState } from "react";
import { AnimasiMasuk } from "@/components/AnimasiMasuk";
import { Ikon, type NamaIkon } from "@/components/Ikon";
import { Tabel } from "@/components/Tabel";
import { Chip, JudulBagian, Kartu, Kepala, Lipat, Memuat, Pesan, Tombol } from "@/components/ui";
import { api, type BarisKeadilan, type Keadilan as DataKeadilan, type StatusKeadilan } from "@/lib/api";
import { angka, kali, persen, unduhCSV } from "@/lib/format";
import { WARNA } from "@/lib/tepat";

const K_PORSI = 0.01, AMBANG_PRA = 2.0, AMBANG_PERHATIAN = 1.25, AMBANG_JARANG = 1 / AMBANG_PERHATIAN;

const DIMENSI: [string, string, string, NamaIkon, Record<string, string>][] = [
  ["kelas", "Kelas", "Kelas rawat peserta", "layers", { kelas_1: "Kelas 1", kelas_2: "Kelas 2", kelas_3: "Kelas 3" }],
  ["kemiskinan", "Wilayah", "Tingkat kemiskinan wilayah, tiga kelompok", "map-pin",
    { rendah: "Kemiskinan wilayah rendah", sedang: "Kemiskinan wilayah sedang", tinggi: "Kemiskinan wilayah tinggi" }],
  ["usia", "Usia", "Usia peserta", "calendar", { "<=35": "≤ 35 tahun", "36-55": "36–55 tahun", ">55": "> 55 tahun" }],
  ["jk", "Jenis kelamin", "Jenis kelamin peserta", "users", { L: "Laki-laki", P: "Perempuan" }],
];
const LABEL = Object.fromEntries(DIMENSI.map(([k, , , , l]) => [k, l]));

const STATUS: Record<StatusKeadilan | "jarang", { nama: string; warna: string; lembut: string; ikon: NamaIkon }> = {
  wajar: { nama: "Wajar", warna: "#17704D", lembut: "#E1EEE6", ikon: "circle-check-big" },
  perhatian: { nama: "Perlu perhatian", warna: "#9A5F0E", lembut: "#F5E6C8", ikon: "trending-up" },
  di_atas: { nama: "Di atas ambang 2×", warna: "#9A3F12", lembut: "#F6E4D6", ikon: "circle-x" },
  jarang: { nama: "Jarang diperiksa", warna: "#1F5F8B", lembut: "#DDE9F3", ikon: "trending-down" },
};
const URUT: StatusKeadilan[] = ["wajar", "perhatian", "di_atas"];
const terburuk = (s: StatusKeadilan[]) => s.reduce((a, b) => (URUT.indexOf(b) > URUT.indexOf(a) ? b : a), "wajar");
const namaPenuh = (dim: string, kel: string) => (dim === "usia" ? "Usia " : "") + LABEL[dim][kel];
const uraian = (xs: BarisKeadilan[]) => xs.map((r) =>
  `${namaPenuh(r.dimensi, r.kelompok)} (${kali(r.rasio_jalur)} di seluruh jalur, ${kali(r.rasio_periksa)} di yang diperiksa)`).join("; ");

export default function Keadilan() {
  const [d, setD] = useState<DataKeadilan | null>(null);
  const [galat, setGalat] = useState(false);
  useEffect(() => { api.keadilan().then(setD).catch(() => setGalat(true)); }, []);
  if (galat) return <Pesan>Panel keadilan tidak bisa dimuat dari server.</Pesan>;
  if (!d) return <Memuat teks="Menghitung beban per kelompok…" />;

  const { tabel, info } = d;
  const N = info.n, ISI = info.isi, M = info.m;
  const XMAKS = Math.max(2.2, Math.max(...tabel.flatMap((r) => [r.rasio_jalur, r.rasio_periksa])) * 1.08);
  const pos = (v: number) => `${(Math.min(v / XMAKS, 1) * 100).toFixed(2)}%`;

  const lain = tabel.filter((r) => r.status_jalur !== "wajar" || r.status_periksa !== "wajar");
  const diAtas = lain.filter((r) => r.status_jalur === "di_atas" || r.status_periksa === "di_atas");
  const perhatian = lain.filter((r) => !diAtas.includes(r));
  const rendah = tabel.filter((r) => r.jarang_jalur || r.jarang_periksa);
  const mustahil = tabel.filter((r) => r.batas_atas <= AMBANG_PRA);

  let kunciV: keyof typeof STATUS, vonis: string, rinci: string;
  if (diAtas.length) {
    kunciV = "di_atas"; vonis = `${diAtas.length} kelompok di atas ambang 2×`;
    rinci = uraian(diAtas) + ". Lebih sering masuk jalur belum berarti diperlakukan tidak adil, tetapi harus bisa dijelaskan sebelum aturan dipakai.";
  } else if (perhatian.length) {
    kunciV = "perhatian"; vonis = `Tidak ada kelompok di atas ambang 2×, tetapi ${perhatian.length} kelompok perlu perhatian`;
    rinci = uraian(perhatian) + ". Selisihnya bukan kebetulan (selang 95% di atas rata-rata), tetapi panel ini belum menjelaskan penyebabnya.";
  } else if (rendah.length) {
    kunciV = "jarang"; vonis = `Tidak ada kelompok yang terlalu sering diperiksa, tetapi ${rendah.length} kelompok jarang diperiksa`;
    rinci = uraian(rendah) + ". Selisihnya bukan kebetulan (selang 95% di bawah rata-rata), tetapi panel ini belum menjelaskan penyebabnya.";
  } else {
    kunciV = "wajar"; vonis = "Tidak ada kelompok yang menonjol";
    rinci = "Semua kelompok di bawah ambang 2× dan tidak ada yang di atas 1,25× dengan selang 95% di atas rata-rata. Itu bukan bukti tidak ada ketimpangan di dimensi lain.";
  }
  const S = STATUS[kunciV];
  const tambahan: string[] = [];
  if (rendah.length && kunciV !== "jarang")
    tambahan.push(`Jarang diperiksa (≤ 0,8×, selang 95% di bawah rata-rata; tanda tambahan): ${uraian(rendah)}.`);
  if (mustahil.length)
    tambahan.push("Ambang 2× tidak mungkin tercapai oleh kelompok yang lebih dari separuh peserta (" + mustahil.map((r) =>
      `${namaPenuh(r.dimensi, r.kelompok)} ${persen(r.porsi_pop)} dari peserta → ${persen(r.bagian_periksa)} dari yang diperiksa`).join("; ") +
      "). Untuk mereka, bandingkan kedua porsi itu, bukan rasionya.");
  const nDiAtas = tabel.filter((r) => r.status_jalur === "di_atas" || r.status_periksa === "di_atas").length;

  const baris = (r: BarisKeadilan) => {
    const sj = STATUS[r.status_jalur], sp = STATUS[r.status_periksa];
    const jarang = r.jarang_jalur || r.jarang_periksa;
    const batas = r.batas_atas <= AMBANG_PRA;
    const sAll = terburuk([r.status_jalur, r.status_periksa]);
    const wj = r.status_jalur !== "wajar" ? sj.warna : r.jarang_jalur ? STATUS.jarang.warna : "inherit";
    const wp = r.status_periksa !== "wajar" ? sp.warna : r.jarang_periksa ? STATUS.jarang.warna : "inherit";
    const nama = LABEL[r.dimensi][r.kelompok];
    const ringkas = `${nama}: seluruh jalur ${kali(r.rasio_jalur)} rata-rata (${angka(r.n_jalur)} dari ${angka(r.n)} peserta, ` +
      `${persen(r.porsi_jalur)}); diperiksa ${kali(r.rasio_periksa)} (${angka(r.n_periksa)} dari ${angka(r.n)}, ${persen(r.porsi_periksa, 2)}). ` +
      `Porsi dari semua peserta ${persen(r.porsi_pop)}, dari isi jalur ${persen(r.bagian_jalur)}, dari yang diperiksa ${persen(r.bagian_periksa)}` +
      (batas ? `; rasio tertinggi yang mungkin ${kali(r.batas_atas)}` : "");
    return (
      <div key={r.kelompok} className="tp-beban-r" role="listitem" aria-label={ringkas} title={ringkas}>
        <div className="nm">{nama}<small>{angka(r.n)} peserta</small>
          {sAll !== "wajar" && <Chip teks={STATUS[sAll].nama} ikon={STATUS[sAll].ikon} warna={STATUS[sAll].warna} latar={STATUS[sAll].lembut} />}
          {jarang && <Chip teks={STATUS.jarang.nama} ikon={STATUS.jarang.ikon} warna={STATUS.jarang.warna} latar={STATUS.jarang.lembut} />}
        </div>
        <div className="tp-trek" style={{ "--wj": sj.warna, "--wp": sp.warna } as React.CSSProperties}>
          <i className="g" style={{ left: pos(1) }} /><i className="g g2" style={{ left: pos(AMBANG_PRA) }} />
          <b className="br" data-anim="lebar" style={{ width: pos(r.rasio_jalur) }} />
          <span className="dm" style={{ left: pos(r.rasio_periksa) }} />
        </div>
        <div className="ang">
          <span style={{ color: wj }}><small>jalur</small> <b>{kali(r.rasio_jalur)}</b></span>
          <span style={{ color: wp }}><small>diperiksa</small> <b>{kali(r.rasio_periksa)}</b></span>
        </div>
        <div className="bagi">Porsi: <b>{persen(r.porsi_pop)}</b> dari semua peserta → <b>{persen(r.bagian_jalur)}</b> dari isi
          jalur → <b>{persen(r.bagian_periksa)}</b> dari yang diperiksa
          {batas && <>. <em>Rasio tertinggi yang mungkin {kali(r.batas_atas)}: ambang 2× tidak bisa tercapai.</em></>}</div>
      </div>
    );
  };

  const tampil = [...tabel].sort((a, b) => {
    const da = DIMENSI.findIndex((x) => x[0] === a.dimensi), db = DIMENSI.findIndex((x) => x[0] === b.dimensi);
    return da !== db ? da - db : Object.keys(LABEL[a.dimensi]).indexOf(a.kelompok) - Object.keys(LABEL[b.dimensi]).indexOf(b.kelompok);
  });
  const r4 = (v: number) => Math.round(v * 1e4) / 1e4, r2 = (v: number | null) => (v === null ? "" : Math.round(v * 100) / 100);
  const kotak = (c: string) => <i style={{ width: 16, height: 9, borderRadius: 2, background: c }} />;
  const nmin = Math.min(...tabel.map((r) => r.n_periksa)), nmaks = Math.max(...tabel.map((r) => r.n_periksa));

  return (
    <>
      <Kepala judul="Panel keadilan dan bukti" penjelasan="Kelompok peserta mana yang paling sering masuk jalur verifikasi, dibanding rata-rata semua peserta. Dihitung tanpa label, jadi mencakup semua peserta di jalur, bukan hanya yang jujur. Angkanya bisa dihitung ulang dari skor_verifikasi.csv dan beban_strata.csv." />
      <div className="tp-tindakan" style={{ "--c": S.warna, "--l": S.lembut } as React.CSSProperties}>
        <div className="tp-bulat"><Ikon nama="scale" ukuran={20} warna={S.warna} /></div>
        <div style={{ flex: "1 1 320px" }}>
          <div className="lbl">Hasil pemeriksaan keadilan</div>
          <div className="isi">{vonis}</div>
          <div className="lain" style={{ marginTop: ".2rem" }}>{rinci}</div>
          {tambahan.map((t) => <div key={t} className="lain" style={{ marginTop: ".35rem" }}>{t}</div>)}
          <div className="lain" style={{ marginTop: ".35rem", display: "flex", gap: ".35rem", alignItems: "flex-start" }}>
            <Ikon nama="flask-conical" ukuran={14} warna={WARNA.tinta2} />
            <span>Data sintetis: pola ini berasal dari data buatan. Panel ini menunjukkan alat ukurnya bekerja, bukan bahwa peserta BPJS asli diperlakukan seperti ini.</span>
          </div>
        </div>
      </div>
      <Kartu item={[
        { ikon: "users", c: WARNA.utama, l: WARNA.utamaLembut, n: angka(ISI), label: `Peserta di jalur verifikasi (${persen(ISI / N)} dari ${angka(N)})` },
        { ikon: "search-check", c: "#9A3F12", l: "#F6E4D6", n: angka(M), label: `Diperiksa sesuai kapasitas (${persen(K_PORSI, 0)} peserta)` },
        { ikon: "circle-x", c: STATUS.di_atas.warna, l: STATUS.di_atas.lembut, n: `${nDiAtas} dari ${tabel.length}`, label: "Kelompok di atas ambang 2×", mati: nDiAtas === 0 },
        { ikon: "trending-up", c: STATUS.perhatian.warna, l: STATUS.perhatian.lembut, n: `${perhatian.length} dari ${tabel.length}`, label: "Kelompok perlu perhatian (≥ 1,25×)", mati: perhatian.length === 0 },
        { ikon: "trending-down", c: STATUS.jarang.warna, l: STATUS.jarang.lembut, n: `${rendah.length} dari ${tabel.length}`, label: "Kelompok jarang diperiksa (≤ 0,8×)", mati: rendah.length === 0 },
      ]} />

      <JudulBagian teks="Beban per kelompok" ikon="layers" penjelasan={`Rasio 1× = sama dengan rata-rata semua peserta. Seluruh jalur: rata-rata ${persen(info.rata_j)} (${angka(ISI)} dari ${angka(N)}). Diperiksa: rata-rata ${persen(info.rata_p)} (${angka(M)} dari ${angka(N)}), bila petugas memeriksa menurut urutan skor (pra-registrasi bagian 3a).`} />
      <div className="tp-legenda-lini" style={{ marginBottom: ".7rem" }}>
        <span>{kotak(STATUS.wajar.warna)}Seluruh jalur verifikasi</span>
        <span><i style={{ width: 10, height: 10, transform: "rotate(45deg)", border: `2px solid ${WARNA.tinta}`, boxSizing: "border-box", background: STATUS.wajar.warna }} />Yang diperiksa ({angka(M)} skor tertinggi)</span>
        <span><i style={{ width: 0, height: 12, borderLeft: "1.5px solid #8F9993" }} />Rata-rata (1×)</span>
        <span><i style={{ width: 0, height: 12, borderLeft: `1.5px dashed ${STATUS.di_atas.warna}` }} />Ambang 2× (pra-registrasi)</span>
        <span style={{ color: STATUS.perhatian.warna }}>Oranye = perlu perhatian</span>
        <span style={{ color: STATUS.jarang.warna }}>Biru = jarang diperiksa</span>
      </div>
      <AnimasiMasuk kunci={tabel.length}>
      <div className="tp-dua">
        {DIMENSI.map(([kunci, judul, sumber, ikon, label]) => {
          const t = tabel.filter((r) => r.dimensi === kunci).sort((a, b) => Object.keys(label).indexOf(a.kelompok) - Object.keys(label).indexOf(b.kelompok));
          const sP = STATUS[terburuk(t.flatMap((r) => [r.status_jalur, r.status_periksa]))];
          return (
            <div key={kunci} className="tp-panel-kotak">
              <div className="tp-grafik-kepala" style={{ "--c": WARNA.utama, "--l": WARNA.utamaLembut } as React.CSSProperties}>
                <div className="tp-bulat"><Ikon nama={ikon} ukuran={20} warna={WARNA.utama} /></div>
                <div><p className="sumber">{sumber}</p><p className="nama">{judul}</p></div>
                <span className="vonis">
                  <Chip teks={sP.nama} ikon={sP.ikon} warna={sP.warna} latar={sP.lembut} />
                  {t.some((r) => r.jarang_jalur || r.jarang_periksa) && <Chip teks={STATUS.jarang.nama} ikon={STATUS.jarang.ikon} warna={STATUS.jarang.warna} latar={STATUS.jarang.lembut} />}
                </span>
              </div>
              <div className="tp-beban" role="list">{t.map(baris)}</div>
              <div className="tp-beban-ax"><span /><div className="tp-trek-ax">
                <i style={{ left: pos(0) }}>0</i><i style={{ left: pos(1) }}>1×</i><i style={{ left: pos(AMBANG_PRA) }}>2×</i>
              </div><span /></div>
            </div>
          );
        })}
      </div>
      </AnimasiMasuk>

      <div style={{ height: "1rem" }} />
      <Lipat judul="Angka lengkap dan cek silang" ikon="table">
        <Tabel<BarisKeadilan> label="Angka lengkap keadilan" baris={tampil} kunciBaris={(r) => r.dimensi + r.kelompok} kolom={[
          { kunci: "dim", judul: "Dimensi", lebar: 120, isi: (r) => DIMENSI.find((x) => x[0] === r.dimensi)![1] },
          { kunci: "kel", judul: "Kelompok", lebar: 200, isi: (r) => LABEL[r.dimensi][r.kelompok] },
          { kunci: "n", judul: "Peserta", lebar: 90, angka: true, isi: (r) => angka(r.n) },
          { kunci: "pp", judul: "Porsi peserta", lebar: 110, angka: true, isi: (r) => persen(r.porsi_pop) },
          { kunci: "ba", judul: "Rasio tertinggi mungkin", lebar: 170, angka: true, isi: (r) => kali(r.batas_atas) },
          { kunci: "nj", judul: "Di jalur", lebar: 90, angka: true, isi: (r) => angka(r.n_jalur) },
          { kunci: "pj", judul: "Porsi jalur", lebar: 100, angka: true, isi: (r) => persen(r.porsi_jalur) },
          { kunci: "bj", judul: "Bagian dari isi jalur", lebar: 160, angka: true, isi: (r) => persen(r.bagian_jalur) },
          { kunci: "rj", judul: "Rasio jalur", lebar: 100, angka: true, isi: (r) => kali(r.rasio_jalur) },
          { kunci: "sj", judul: "Status jalur", lebar: 140, isi: (r) => STATUS[r.status_jalur].nama },
          { kunci: "jj", judul: "Jalur: jarang", lebar: 130, isi: (r) => (r.jarang_jalur ? STATUS.jarang.nama : "") },
          { kunci: "lj", judul: "Jalur vs di luar kelompok", lebar: 190, angka: true, isi: (r) => kali(r.luar_jalur) },
          { kunci: "np", judul: "Diperiksa", lebar: 90, angka: true, isi: (r) => angka(r.n_periksa) },
          { kunci: "ppr", judul: "Porsi diperiksa", lebar: 120, angka: true, isi: (r) => persen(r.porsi_periksa, 2) },
          { kunci: "bp", judul: "Bagian dari yang diperiksa", lebar: 190, angka: true, isi: (r) => persen(r.bagian_periksa) },
          { kunci: "rp", judul: "Rasio diperiksa", lebar: 120, angka: true, isi: (r) => kali(r.rasio_periksa) },
          { kunci: "sp", judul: "Status diperiksa", lebar: 140, isi: (r) => STATUS[r.status_periksa].nama },
          { kunci: "jp", judul: "Diperiksa: jarang", lebar: 140, isi: (r) => (r.jarang_periksa ? STATUS.jarang.nama : "") },
          { kunci: "lp", judul: "Diperiksa vs di luar kelompok", lebar: 210, angka: true, isi: (r) => kali(r.luar_periksa) },
        ]} />
        <div style={{ margin: ".7rem 0 0" }}>
          <Tombol ikon="download" onClick={() => unduhCSV("beban_per_kelompok.csv", tampil.map((r) => ({
            dimensi: r.dimensi, kelompok: r.kelompok, n_peserta: r.n, porsi_peserta: r4(r.porsi_pop),
            rasio_tertinggi_mungkin: r2(r.batas_atas), n_jalur: r.n_jalur, porsi_jalur: r4(r.porsi_jalur),
            bagian_dari_isi_jalur: r4(r.bagian_jalur), rasio_jalur: r2(r.rasio_jalur), status_jalur: r.status_jalur,
            jarang_jalur: r.jarang_jalur, rasio_vs_luar_kelompok_jalur: r2(r.luar_jalur), n_diperiksa: r.n_periksa,
            porsi_diperiksa: r4(r.porsi_periksa), bagian_dari_yang_diperiksa: r4(r.bagian_periksa),
            rasio_diperiksa: r2(r.rasio_periksa), status_diperiksa: r.status_periksa, jarang_diperiksa: r.jarang_periksa,
            rasio_vs_luar_kelompok_diperiksa: r2(r.luar_periksa) })), false)}>Unduh angka (CSV)</Tombol>
        </div>
        {info.cocok === info.baris_csv && info.baris_csv === tabel.length ? (
          <p className="tp-catatan-kecil"><Ikon nama="circle-check-big" ukuran={14} warna={WARNA.utama} /> Cek silang: dihitung ulang
            dari skor_verifikasi.csv dan atribut peserta, {info.cocok} dari {info.baris_csv} baris cocok dengan beban_strata.csv
            (jumlah peserta dan jumlah di jalur).</p>
        ) : (
          <div className="tp-pesan galat">Cek silang gagal: hanya {info.cocok} dari {info.baris_csv} baris beban_strata.csv cocok
            dengan hitungan ulang. Jangan pakai angka di halaman ini sebelum diperiksa.</div>
        )}
      </Lipat>

      <JudulBagian teks="Cara membaca" ikon="gavel" />
      <ol className="tp-baca">
        <li><b>Seluruh jalur</b> adalah {angka(ISI)} peserta yang ditandai aturan triase untuk diperiksa petugas. <b>Diperiksa</b> adalah{" "}
          {angka(M)} di antaranya dengan skor tertinggi, bila petugas memeriksa menurut urutan skor dengan kapasitas {persen(K_PORSI, 0)} peserta
          (pra-registrasi bagian 3a).</li>
        <li>Ambang <b>2× rata-rata</b> dikunci di pra-registrasi (uji T4) sebelum hasil dilihat. <b>Perlu perhatian</b> (≥{" "}
          {angka(AMBANG_PERHATIAN, 2)}× dan selang 95% di atas rata-rata) dan <b>jarang diperiksa</b> (≤ {angka(AMBANG_JARANG, 2)}× dan
          selang 95% di bawah rata-rata) ditambahkan sesudah hasil dilihat, jadi bukan bagian pra-registrasi.</li>
        <li><b>Porsi</b> di bawah tiap batang: berapa persen peserta, isi jalur, dan yang diperiksa berasal dari kelompok itu. Bila porsi
          diperiksa jauh di atas porsi peserta, kelompok itu terlalu sering diperiksa, walau rasionya belum melewati 2×. Rasio ke
          rata-rata tidak bisa melebihi 1 ÷ porsi peserta, jadi ambang 2× tidak bisa mendeteksi kelompok yang lebih dari separuh
          peserta; untuk itu baca porsinya.</li>
        <li>Lebih sering masuk jalur bukan bukti perlakuan tidak adil, dan tidak ada selisih bukan bukti sebaliknya. Panel ini
          menunjukkan di mana selisih ada. Sebabnya perlu diselidiki terpisah.</li>
        <li>Peserta yang masuk jalur diperiksa petugas lebih dulu sebelum ada tindakan. Jalur ini bukan tuduhan dan tidak mencabut
          jaminan.</li>
      </ol>
      <div style={{ height: "1rem" }} />
      <Lipat judul="Batas panel ini" ikon="ruler">
        <ul className="tp-baca">
          <li><b>Data sintetis.</b> Pola di sini berasal dari data buatan. Di data asli, hasilnya bisa lain.</li>
          <li><b>Semua peserta di jalur, bukan hanya yang jujur.</b> Label tidak dibaca di halaman ini. Uji berlabel yang memisahkan
            peserta jujur (T4) dilaporkan terpisah dan hanya dinilai bila ada cukup peserta jujur di jalur (syarat pra-registrasi:
            minimal 30).</li>
          <li><b>Yang diperiksa hanya {angka(M)} orang.</b> Per kelompok hanya {angka(nmin)}–{angka(nmaks)} orang, jadi rasionya lebih
            goyah daripada rasio seluruh jalur. Tanda perhatian memakai selang 95% tetapi tidak dikoreksi untuk {tabel.length * 2}{" "}
            perbandingan sekaligus.</li>
          <li><b>Satu dimensi sekali jalan.</b> Kelompok antardimensi saling tumpang tindih (misalnya usia dan kelas), jadi selisih di
            satu dimensi bisa berasal dari dimensi lain.</li>
          <li><b>Wilayah</b> berarti tiga kelompok tingkat kemiskinan wilayah (sepertiga bawah, tengah, atas dari {info.n_wilayah}{" "}
            wilayah), seperti di pra-registrasi. Per kode wilayah tidak ditampilkan: hanya {info.wil_min}–{info.wil_maks} peserta di
            jalur per wilayah, terlalu sedikit untuk dibandingkan.</li>
          <li><b>Pembandingnya rata-rata semua peserta</b>, bukan kelompok lain. Dua kelompok bisa sama-sama dekat rata-rata namun
            selisih antar keduanya tetap besar. Tabel lengkap memuat rasio terhadap peserta di luar kelompok, yang tidak punya batas
            1 ÷ porsi; angka itu informasi tanpa ambang.</li>
          <li><b>Skor ikut menentukan siapa yang diperiksa.</b> Rumus skor (pra-registrasi bagian 3) membagi klaim dengan iuran,
            sehingga peserta berkelas murah mendapat skor lebih tinggi untuk klaim yang sama dan kelas murah cenderung lebih banyak
            di antara yang diperiksa. Besarnya pengaruh ini diukur terpisah di bukti/hasil/sensitivitas_keadilan.txt (bagian C),
            bersama uji usia netral dan rentang antar seed (skrip: bukti/sensitivitas_keadilan.py).</li>
        </ul>
      </Lipat>
    </>
  );
}
