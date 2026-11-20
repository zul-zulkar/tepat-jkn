"use client";

// Sesi aplikasi: akun yang masuk, kapasitas k, dan filter wilayah. Akun dan k disimpan server (kuki sesi);
// filter wilayah dan peserta terakhir disimpan di sessionStorage peramban supaya tetap saat pindah halaman.

import Link from "next/link";
import { MotionConfig, motion } from "motion/react";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Sesi } from "@/lib/api";
import { bacaSimpanan, tulisSimpanan } from "@/lib/simpanan";
import { Ikon, type NamaIkon } from "./Ikon";
import { Memuat } from "./ui";

interface NilaiSesi {
  sesi: Sesi | null;
  wilayah: string[];
  setWilayah: (w: string[]) => void;
  pidTerakhir: string;
  setPidTerakhir: (id: string) => void;
  masuk: (kunci: string) => Promise<void>;
  keluar: () => Promise<void>;
  aturK: (k: number) => Promise<void>;
}

const Konteks = createContext<NilaiSesi | null>(null);

export function useSesi(): NilaiSesi {
  const v = useContext(Konteks);
  if (!v) throw new Error("useSesi di luar <PenyediaSesi>");
  return v;
}

const HALAMAN: { href: string; judul: string; ikon: NamaIkon; pusat?: boolean }[] = [
  { href: "/daftar-kerja/", judul: "Daftar kerja", ikon: "list-checks" },
  { href: "/profil/", judul: "Profil peserta", ikon: "user" },
  { href: "/kebijakan/", judul: "Kebijakan", ikon: "gavel", pusat: true },
  { href: "/keadilan/", judul: "Keadilan", ikon: "scale", pusat: true },
];

export function PenyediaSesi({ children }: { children: ReactNode }) {
  const [sesi, setSesi] = useState<Sesi | null>(null);
  const [galat, setGalat] = useState("");
  const [wilayah, setWilayahState] = useState<string[]>([]);
  const [pidTerakhir, setPidState] = useState("");
  const path = usePathname();
  const router = useRouter();

  useEffect(() => {
    setWilayahState(bacaSimpanan("tepat_wilayah", []));
    setPidState(bacaSimpanan("tepat_pid", ""));
    (async () => {
      try {
        let s = await api.sesi();
        // tautan langsung untuk juri: ?akun=pusat atau ?akun=cabang_a
        const url = new URL(window.location.href);
        const langsung = url.searchParams.get("akun");
        if (langsung !== null) {
          if (!s.akun && s.daftar_akun.some((a) => a.kunci === langsung)) s = await api.masuk(langsung);
          url.searchParams.delete("akun");
          window.history.replaceState(null, "", url.pathname + url.search);
        }
        setSesi(s);
      } catch {
        setGalat("Server TEPAT tidak menjawab. Pastikan program server berjalan, lalu muat ulang halaman.");
      }
    })();
  }, []);

  // pengalihan: belum masuk -> Masuk; Kebijakan dan Keadilan hanya untuk Pusat
  useEffect(() => {
    if (!sesi) return;
    const diMasuk = path.startsWith("/masuk");
    if (!sesi.akun && !diMasuk) router.replace("/masuk/");
    else if (sesi.akun && (diMasuk || path === "/")) router.replace("/daftar-kerja/");
    else if (sesi.akun?.peran === "cabang" && HALAMAN.some((h) => h.pusat && path.startsWith(h.href)))
      router.replace("/daftar-kerja/");
  }, [sesi, path, router]);

  const setWilayah = useCallback((w: string[]) => { setWilayahState(w); tulisSimpanan("tepat_wilayah", w); }, []);
  const setPidTerakhir = useCallback((id: string) => { setPidState(id); tulisSimpanan("tepat_pid", id); }, []);
  const nilai = useMemo<NilaiSesi>(() => ({
    sesi, wilayah, setWilayah, pidTerakhir, setPidTerakhir,
    // filter dan peserta terakhir akun sebelumnya dibuang supaya tidak bocor antar akun
    masuk: async (kunci) => { setWilayah([]); setPidTerakhir(""); setSesi(await api.masuk(kunci)); },
    keluar: async () => setSesi(await api.keluar()),
    aturK: async (k) => setSesi(await api.kapasitas(k)),
  }), [sesi, wilayah, setWilayah, pidTerakhir, setPidTerakhir]);

  const khususPusat = HALAMAN.some((h) => h.pusat && path.startsWith(h.href));
  const siap = sesi && (sesi.akun ? !path.startsWith("/masuk") && !(sesi.akun.peran === "cabang" && khususPusat)
    : path.startsWith("/masuk"));
  return (
    <Konteks.Provider value={nilai}>
      <MotionConfig reducedMotion="user">
      <Kepala sesi={sesi} path={path} />
      <main className="tp-utama">
        {galat ? <div className="tp-pesan"><Ikon nama="circle-alert" ukuran={18} />{galat}</div>
          : siap ? (
          <motion.div key={path} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: "easeOut" }}>
            {sesi.akun && <Pita />}{children}
          </motion.div>
        ) : <Memuat teks="Membuka TEPAT…" />}
      </main>
      </MotionConfig>
    </Konteks.Provider>
  );
}

function Kepala({ sesi, path }: { sesi: Sesi | null; path: string }) {
  const akun = sesi?.akun;
  const halaman = akun ? HALAMAN.filter((h) => !h.pusat || akun.peran === "pusat") : [];
  return (
    <header className="tp-header">
      <div className="dalam">
        <Link href={akun ? "/daftar-kerja/" : "/masuk/"} className="logo" aria-label="TEPAT, beranda">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo/tepat-logo.svg" alt="TEPAT" width={115} height={32} />
        </Link>
        <nav aria-label="Halaman">
          {akun ? halaman.map((h) => (
            <Link key={h.href} href={h.href} className={path.startsWith(h.href) ? "aktif" : ""}
              aria-current={path.startsWith(h.href) ? "page" : undefined}>
              <Ikon nama={h.ikon} ukuran={17} />{h.judul}
            </Link>
          )) : (
            <Link href="/masuk/" className="aktif"><Ikon nama="log-in" ukuran={17} />Masuk</Link>
          )}
        </nav>
      </div>
    </header>
  );
}

function Pita() {
  const { sesi, keluar } = useSesi();
  const a = sesi?.akun;
  if (!a) return null;
  const ket = a.peran === "pusat" ? "Semua wilayah" : `${a.wilayah.length} wilayah: ${a.wilayah.join(", ")}`;
  return (
    <div className="tp-pita-baris">
      <div className="tp-pita">
        <span className={`tp-chip tp-peran-${a.peran}`}>{a.peran === "pusat" ? "Pusat" : "Cabang"}</span>
        <b>{a.nama}</b>
        <span className="ket">{ket}</span>
      </div>
      <button type="button" className="tp-tombol" onClick={() => void keluar()}>
        <Ikon nama="arrow-left-right" ukuran={16} /><span>Ganti akun</span>
      </button>
    </div>
  );
}
