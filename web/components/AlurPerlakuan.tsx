"use client";

// Flowchart dari peserta ke satu tindakan dan perlakuannya (tepat_ui.alur_perlakuan).
// Mode jumlah (Daftar kerja): jumlah per tindakan. Mode satu peserta (Profil): jalurnya disorot, langkah
// sesudahnya diredupkan, dan tindakan lain yang juga dipenuhi ditandai.

import { Fragment } from "react";
import { angka } from "@/lib/format";
import { langkah, namaTindakan, PERLAKUAN, RUTE, warnaTindakan, WARNA, type Tindakan } from "@/lib/tepat";
import { Ikon } from "./Ikon";
import { Chip } from "./ui";
import { useSesi } from "./Sesi";

export function AlurPerlakuan({ jumlah, total, utama, juga = [], labelMulai = "Peserta PBPU/BP mandiri" }: {
  jumlah?: Partial<Record<Tindakan, number>>; total?: number; utama?: Tindakan; juga?: Tindakan[];
  labelMulai?: string;
}) {
  const { sesi } = useSesi();
  const LANGKAH = langkah(sesi?.konstanta.jeda_kait ?? 90);
  const jalur = utama !== undefined;
  const iUtama = LANGKAH.findIndex((x) => x.tindakan === utama);
  const henti = iUtama < 0 ? LANGKAH.length : iUtama;
  let sisa = total;

  return (
    <div className={"tp-alur" + (jalur ? " tp-alur-jalur" : "")}>
      <div className="tp-alur-ujung mulai">
        <Ikon nama="user-round" ukuran={18} warna="#F2F0E5" />
        <span>{labelMulai}</span>
        {total !== undefined && <span className="n">{angka(total)}</span>}
      </div>
      {LANGKAH.map((x, i) => {
        const t = x.tindakan;
        const [c, l, ik] = warnaTindakan(t);
        const keadaan = !jalur ? "" : i < henti ? "lewat" : i === henti ? "kena" : "sesudah";
        const teksTurun = i === 0 ? "" : "Tidak" + (sisa !== undefined ? `, ${angka(sisa)} peserta lanjut` : "");
        const n = jumlah?.[t] ?? 0;
        const baris = (
          <Fragment key={t}>
            <div className={"tp-alur-turun" + (jalur && i <= henti ? " aktif" : "") + (i === 0 ? " pendek" : "")}>
              <div><span>{teksTurun}</span></div>
            </div>
            <div className={"tp-alur-baris " + keadaan} style={{ "--c": c, "--l": l } as React.CSSProperties}>
              <div className="tp-alur-tanya">
                <div className="kepala">
                  <span className="no">{i + 1}</span>
                  <span className="q">{x.tanya}</span>
                  {jalur && i <= henti && (
                    <Chip teks={i === henti ? "Ya" : "Tidak"} warna={i === henti ? "#FCFCF9" : WARNA.tinta2}
                      latar={i === henti ? WARNA.utama : "#E6E4DC"} />
                  )}
                </div>
                <div className="s">{x.syarat}</div>
              </div>
              <div className="tp-alur-ya"><span>Ya</span></div>
              <div className="tp-alur-hasil">
                <div className="tp-bulat"><Ikon nama={ik} ukuran={18} warna={c} /></div>
                <div className="isi">
                  <div className="nm">{t === "peringatan_dini" ? namaTindakan(t) : RUTE[t].nama}</div>
                  <div className="pl">{PERLAKUAN[t].pendek}</div>
                  {jalur && i === henti && <span className="tanda">Tindakan peserta ini</span>}
                  {jalur && i !== henti && juga.includes(t) && (
                    <span className="tanda redup">Juga dipenuhi, tidak dijalankan</span>
                  )}
                </div>
                {jumlah && <span className="n">{angka(n)}<small> peserta</small></span>}
              </div>
            </div>
          </Fragment>
        );
        if (sisa !== undefined && jumlah) sisa -= n;
        return baris;
      })}
      <div className={"tp-alur-turun" + (jalur && henti === LANGKAH.length ? " aktif" : "")}>
        <div><span>{"Tidak" + (sisa !== undefined ? `, ${angka(sisa)} peserta` : "")}</span></div>
      </div>
      <div className={"tp-alur-ujung akhir" + (jalur && henti === LANGKAH.length ? " kena" : "")}>
        <Ikon nama="circle-check-big" ukuran={18} warna={WARNA.tinta2} />
        <span>Tanpa tindakan bulan ini</span>
        {jalur && henti === LANGKAH.length && <span className="tanda">Tindakan peserta ini</span>}
      </div>
    </div>
  );
}
