"use client";

import { useState } from "react";
import { useSesi } from "@/components/Sesi";
import { JudulBagian, Kepala, Tombol } from "@/components/ui";

export default function Masuk() {
  const { sesi, masuk } = useSesi();
  const daftar = sesi?.daftar_akun ?? [];
  const [pilih, setPilih] = useState(daftar[0]?.kunci ?? "pusat");
  const [sibuk, setSibuk] = useState(false);
  return (
    <>
      <Kepala judul="Masuk" penjelasan="Pilih akun demo. Pusat melihat semua wilayah dan menetapkan kapasitas; kantor cabang bekerja di wilayahnya dan mencatat keputusan." />
      <div className="tp-masuk">
        <form className="tp-panel-kotak" onSubmit={async (e) => {
          e.preventDefault();
          setSibuk(true);
          try { await masuk(pilih); } finally { setSibuk(false); }
        }}>
          <JudulBagian teks="Akun demo" ikon="user-round" />
          <div className="tp-radio-blok" role="radiogroup" aria-label="Akun">
            {daftar.map((a) => (
              <label key={a.kunci}>
                <input type="radio" name="akun" value={a.kunci} checked={pilih === a.kunci}
                  onChange={() => setPilih(a.kunci)} />
                <span>{a.nama}{a.peran === "cabang" && ` · ${a.wilayah.length} wilayah`}</span>
              </label>
            ))}
          </div>
          <div style={{ marginTop: ".9rem" }}>
            <Tombol type="submit" utama lebar ikon="log-in" disabled={sibuk}>Masuk</Tombol>
          </div>
          <p className="tp-kecil">Akun demo tanpa kata sandi, data sintetis. Untuk pilot: login lewat SSO BPJS.</p>
        </form>
      </div>
    </>
  );
}
