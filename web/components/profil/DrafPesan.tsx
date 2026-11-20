"use client";

import { useEffect, useState } from "react";
import { useSesi } from "@/components/Sesi";
import { Chip, JudulBagian, Saklar, Tombol } from "@/components/ui";
import { api, type HasilAI, type Peserta } from "@/lib/api";
import { useSimpanan } from "@/lib/simpanan";
import { WARNA } from "@/lib/tepat";

export function DrafPesan({ p }: { p: Peserta }) {
  const { sesi, wilayah } = useSesi();
  const [isi, setIsi] = useState<Record<string, string>>({});
  const [aiAktif, setAiAktif] = useSimpanan("tepat_ai_aktif", true);
  const [sibuk, setSibuk] = useState(false);
  const [hasil, setHasil] = useState<HasilAI | null>(null);
  useEffect(() => {
    setIsi(Object.fromEntries(p.draf.map((d) => [d.sumber, d.isi])));
    setHasil(null);
  }, [p.id, p.draf]);

  const tulisUlang = async () => {
    setSibuk(true);
    try {
      const h = await api.pesan(p.id, wilayah, aiAktif);
      setHasil(h);
      // kotak hanya ditimpa bila AI berhasil dan lolos aturan; sunting petugas tidak hilang bila gagal
      if (h.hasil.status === "ai" && h.hasil.draf[0]) setIsi((x) => ({ ...x, [h.hasil.draf[0].sumber]: h.hasil.draf[0].isi }));
    } catch {
      setHasil({ hasil: { jalur: p.utama, draf: [], status: "template", cadangan: "api_error", rinci: "",
        ringkasan_petugas: "", model: "", penyedia: "" , dirapikan: 0 }, keterangan: "Memakai template (server tidak menjawab)." });
    } finally {
      setSibuk(false);
    }
  };
  const batas = sesi?.ai.batas_waktu ?? 45;

  return (
    <div className="tp-draf">
      <JudulBagian teks="Draf pesan" ikon="message-square-text" penjelasan="Draf awal dari template, bisa disunting sebelum dikirim. Tombol AI menulis ulang kata-katanya: rute tidak berubah, nomor peserta tidak dikirim ke AI, dan bila AI tidak tersedia template tetap dipakai. Rute verifikasi hanya punya catatan untuk petugas, tanpa AI." />
      {p.draf.length === 0 ? <p>Tidak ada pesan bulan ini.</p> : p.draf.map((d) => (
        <div key={d.sumber}>
          <div style={{ margin: "0 0 .5rem" }}><Chip teks={d.judul} ikon="file-text" /></div>
          <textarea className="tp-area" value={isi[d.sumber] ?? d.isi} aria-label={d.judul}
            onChange={(e) => setIsi((x) => ({ ...x, [d.sumber]: e.target.value }))} />
          {d.jenis === "pesan_peserta" && (
            <>
              <div className="tp-draf-aksi">
                <Tombol ikon="sparkles" disabled={!aiAktif || sibuk} onClick={() => void tulisUlang()}>Tulis ulang dengan AI</Tombol>
                <Saklar label="Pakai AI" nilai={aiAktif} title="Matikan untuk bekerja hanya dengan template, misalnya saat API tidak tersedia."
                  onUbah={setAiAktif} />
              </div>
              {sibuk ? (
                <div className="tp-memuat" style={{ padding: ".4rem 0" }}><span className="putar" aria-hidden="true" />
                  AI sedang menyusun draf. Biasanya 3 sampai 30 detik, paling lama {batas} detik. Bila gagal, template tetap dipakai.</div>
              ) : !aiAktif ? <p className="tp-kecil">AI dimatikan petugas. Draf dari template.</p>
                : !hasil || hasil.hasil.jalur !== p.utama ? <p className="tp-kecil">Draf dari template.</p>
                : hasil.hasil.status === "ai" ? (
                  <div>
                    <Chip teks="Disusun AI" ikon="message-square-text" warna={WARNA.utama} latar="#E1EEE6" />
                    <p className="tp-kecil">{hasil.keterangan}</p>
                    {hasil.hasil.ringkasan_petugas && <p className="tp-kecil">Ringkasan untuk petugas: {hasil.hasil.ringkasan_petugas}</p>}
                  </div>
                ) : (
                  <div>
                    <Chip teks="Template" ikon="info" warna="#9A5F0E" latar="#F5E6C8" />
                    <p className="tp-kecil">{hasil.keterangan} Isi kotak tidak diubah.</p>
                  </div>
                )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
