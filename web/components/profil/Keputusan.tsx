"use client";

import { useEffect, useState } from "react";
import { Ikon } from "@/components/Ikon";
import { useSesi } from "@/components/Sesi";
import { Chip, JudulBagian, Tombol } from "@/components/ui";
import { api, type Keputusan, type Peserta } from "@/lib/api";
import { tgl } from "@/lib/format";
import {
  ALASAN_TOLAK,
  PERINGATAN_DINI,
  RUTE,
  RUTE_AKSI,
  SARAN,
  WARNA,
  warnaTindakan,
  type KodeRute,
} from "@/lib/tepat";

export function KeputusanPetugas({ p, setP }: { p: Peserta; setP: (p: Peserta) => void }) {
  const { sesi, wilayah } = useSesi();
  const pusat = sesi?.akun?.peran === "pusat";
  const [kep, setKep] = useState<"" | "setuju" | "tolak">("");
  const [alasan, setAlasan] = useState("");
  const [catatan, setCatatan] = useState("");
  const [pesan, setPesan] = useState<{ galat: boolean; teks: string } | null>(null);
  useEffect(() => { setKep(""); setAlasan(""); setCatatan(""); setPesan(null); }, [p.id]);

  let sasaran: { nama: string; t: typeof p.utama } | null = null;
  if (p.utama === PERINGATAN_DINI && p.ew) sasaran = { nama: SARAN[p.ew.saran]?.nama ?? p.ew.saran, t: p.utama };
  else if (RUTE_AKSI.includes(p.utama as KodeRute)) sasaran = { nama: RUTE[p.utama as KodeRute].nama, t: p.utama };

  const simpan = async () => {
    if (kep === "tolak" && !alasan) return setPesan({ galat: true, teks: "Pilih alasan menolak, lalu simpan lagi." });
    if (alasan === "Lainnya" && !catatan.trim()) return setPesan({ galat: true, teks: "Tulis catatan untuk alasan Lainnya, lalu simpan lagi." });
    try {
      const k = await api.keputusan(p.id, wilayah, kep, kep === "tolak" ? alasan : "", catatan);
      setP({ ...p, keputusan: k });
      setPesan({ galat: false, teks: "Keputusan disimpan" });
    } catch {
      setPesan({ galat: true, teks: "Keputusan tidak tersimpan. Coba lagi." });
    }
  };

  return (
    <div>
      <JudulBagian teks="Keputusan petugas" ikon="gavel" penjelasan="Keputusan tidak mengubah rute. Tersimpan selama sesi ini dan ikut di CSV unduhan daftar kerja; penyimpanan permanen menyusul." />
      {!sasaran ? <p>Tidak ada yang perlu diputuskan.</p> : (
        <>
          <div style={{ margin: "0 0 .6rem" }}>
            <Chip teks={sasaran.nama} ikon={warnaTindakan(sasaran.t)[2]} warna={warnaTindakan(sasaran.t)[0]} latar={warnaTindakan(sasaran.t)[1]} />
          </div>
          {pusat ? (
            <p className="tp-kecil"><Ikon nama="lock" ukuran={14} /> Keputusan dicatat oleh petugas kantor cabang</p>
          ) : (
            <div style={{ display: "grid", gap: ".6rem" }}>
              <div className="tp-radio" role="radiogroup" aria-label="Keputusan">
                <label><input type="radio" name={`kep-${p.id}`} checked={kep === "setuju"} onChange={() => setKep("setuju")} />
                  <Ikon nama="circle-check-big" ukuran={16} warna={WARNA.utama} />Setuju</label>
                <label><input type="radio" name={`kep-${p.id}`} checked={kep === "tolak"} onChange={() => setKep("tolak")} />
                  <Ikon nama="circle-x" ukuran={16} warna="#9A3F12" />Tolak</label>
              </div>
              {kep === "tolak" && (
                <select className="tp-select" value={alasan} onChange={(e) => setAlasan(e.target.value)} aria-label="Alasan menolak">
                  <option value="" disabled>Pilih alasan</option>
                  {ALASAN_TOLAK.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              )}
              <textarea className="tp-area" rows={3} value={catatan} onChange={(e) => setCatatan(e.target.value)}
                placeholder="Wajib bila alasannya Lainnya" aria-label="Catatan" />
              <div><Tombol utama ikon="save" disabled={!kep} onClick={() => void simpan()}>Simpan keputusan</Tombol></div>
              {pesan && <div className={"tp-pesan" + (pesan.galat ? " galat" : "")} role="status">
                <Ikon nama={pesan.galat ? "circle-alert" : "check"} ukuran={16} />{pesan.teks}</div>}
            </div>
          )}
          <KeputusanTersimpan k={p.keputusan} pusat={pusat} />
        </>
      )}
    </div>
  );
}

function KeputusanTersimpan({ k, pusat }: { k: Keputusan | null; pusat: boolean }) {
  if (!k) return pusat ? <p>Belum ada keputusan dari kantor cabang.</p> : null;
  const [tanggal, jam] = k.waktu.split(" ");
  let teks = `, ${tgl(tanggal).split(" ").slice(0, 2).join(" ")} pukul ${jam.replace(":", ".")}`;
  if (k.alasan) teks += `. ${k.alasan}`;
  if (k.catatan && pusat) teks += `. Catatan: ${k.catatan}`;
  if (k.dicatat_oleh) teks += `. Dicatat oleh ${k.dicatat_oleh}.`;
  return (
    <p style={{ marginTop: ".7rem" }}>
      <Ikon nama="check" ukuran={16} warna={WARNA.utama} /> <b>{k.keputusan === "setuju" ? "Disetujui" : "Ditolak"}</b>{teks}
    </p>
  );
}
