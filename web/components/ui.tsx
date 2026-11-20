"use client";

// Komponen kecil yang dipakai semua halaman. Gaya ada di app/globals.css (kelas tp-*).

import { AnimatePresence, motion } from "motion/react";
import { useId, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Ikon, type NamaIkon } from "./Ikon";
import { useSesi } from "./Sesi";
import { BULAN_PANJANG, tgl } from "@/lib/format";

/** Ikon info yang membuka penjelasan (popover Radix: Esc dan klik di luar menutup, fokus dikelola). */
export function Info({ children, kanan = false, label = "Penjelasan" }: {
  children: ReactNode; kanan?: boolean; label?: string;
}) {
  return (
    <span className="tp-info">
      <Popover>
        <PopoverTrigger asChild>
          <button type="button" className="tp-info-pemicu" aria-label={label} title={label}>
            <Ikon nama="info" ukuran={18} />
          </button>
        </PopoverTrigger>
        <PopoverContent align={kanan ? "end" : "start"} sideOffset={6} className="tp-info-isi">{children}</PopoverContent>
      </Popover>
    </span>
  );
}

export function Chip({ teks, ikon, warna, latar, className }: {
  teks: ReactNode; ikon?: NamaIkon; warna?: string; latar?: string; className?: string;
}) {
  return (
    <span className={"tp-chip" + (className ? " " + className : "")} style={{ color: warna, background: latar }}>
      {ikon && <Ikon nama={ikon} ukuran={14} warna={warna ?? "#3D4B46"} />}
      {teks}
    </span>
  );
}

export function ChipData() {
  const { sesi } = useSesi();
  const m = sesi?.manifest;
  return (
    <span className="tp-kanan">
      <Chip teks="Data sintetis" ikon="flask-conical" />
      {m && (
        <Info kanan label="Tentang data">
          Data buatan untuk prototipe, bukan data peserta asli. Triase per {tgl(m.triase_per_tanggal)}; risiko
          menunggak dihitung untuk {BULAN_PANJANG[Number(m.ew_bulan_operasional.slice(5)) - 1]}{" "}
          {m.ew_bulan_operasional.slice(0, 4)}.
        </Info>
      )}
    </span>
  );
}

export function Kepala({ judul, penjelasan }: { judul: string; penjelasan: ReactNode }) {
  return (
    <div className="tp-kepala">
      <h1>{judul}</h1>
      <Info>{penjelasan}</Info>
      <ChipData />
    </div>
  );
}

export interface ItemKartu { ikon: NamaIkon; c: string; l: string; n: ReactNode; label: ReactNode; ket?: ReactNode; mati?: boolean }

export function Kartu({ item }: { item: ItemKartu[] }) {
  return (
    <div className="tp-kartu-grid">
      {item.map((k, i) => (
        <motion.div key={i} className={"tp-kartu" + (k.mati ? " mati" : "") + (k.ket ? " atas" : "")}
          style={{ "--c": k.c, "--l": k.l } as React.CSSProperties}
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: i * 0.05, ease: "easeOut" }}>
          <div className="tp-bulat"><Ikon nama={k.ikon} ukuran={20} warna={k.c} /></div>
          <div>
            <div className="n">{k.n}</div>
            <div className={"l" + (k.ket ? " tebal" : "")}>{k.label}</div>
            {k.ket && <div className="l">{k.ket}</div>}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

export function JudulBagian({ teks, ikon, penjelasan }: { teks: string; ikon: NamaIkon; penjelasan?: ReactNode }) {
  return (
    <div className="tp-judul">
      <Ikon nama={ikon} ukuran={20} warna="#17704D" />
      <h3>{teks}</h3>
      {penjelasan && <Info>{penjelasan}</Info>}
    </div>
  );
}

/** Bagian yang bisa dibuka-tutup (expander): Collapsible shadcn, tinggi dianimasikan motion. */
export function Lipat({ judul, ikon, children, terbuka = false }: {
  judul: ReactNode; ikon: NamaIkon; children: ReactNode; terbuka?: boolean;
}) {
  const [buka, setBuka] = useState(terbuka);
  return (
    <Collapsible open={buka} onOpenChange={setBuka} className="tp-lipat" data-state={buka ? "open" : "closed"}>
      <CollapsibleTrigger className="tp-lipat-pemicu">
        <Ikon nama={ikon} ukuran={18} warna="#3D4B46" />
        <span>{judul}</span>
        <Ikon nama="chevron-down" ukuran={18} className="panah" />
      </CollapsibleTrigger>
      <AnimatePresence initial={false}>
        {buka && (
          <CollapsibleContent forceMount asChild>
            <motion.div className="isi" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: "easeInOut" }} style={{ overflow: "hidden" }}>
              <div className="dalam">{children}</div>
            </motion.div>
          </CollapsibleContent>
        )}
      </AnimatePresence>
    </Collapsible>
  );
}

export function Tombol({ children, ikon, utama = false, onClick, disabled, title, lebar, type = "button" }: {
  children: ReactNode; ikon?: NamaIkon; utama?: boolean; onClick?: () => void; disabled?: boolean;
  title?: string; lebar?: boolean; type?: "button" | "submit";
}) {
  return (
    <Button type={type} variant={utama ? "default" : "outline"} onClick={onClick} disabled={disabled} title={title}
      className={"tp-tombol" + (lebar ? " w-full" : "")}>
      {ikon && <Ikon nama={ikon} ukuran={16} />}
      <span>{children}</span>
    </Button>
  );
}

/** Pilihan tunggal berbentuk segmen. */
export function Segmen<T extends string>({ pilihan, nilai, onUbah, label }: {
  pilihan: { nilai: T; isi: ReactNode }[]; nilai: T; onUbah: (v: T) => void; label: string;
}) {
  return (
    <div className="tp-segmen" role="radiogroup" aria-label={label}>
      {pilihan.map((p) => (
        <button key={p.nilai} type="button" role="radio" aria-checked={p.nilai === nilai}
          className={p.nilai === nilai ? "aktif" : ""} onClick={() => onUbah(p.nilai)}>
          {p.isi}
        </button>
      ))}
    </div>
  );
}

/** Pilihan ganda berbentuk pil. */
export function Pil<T extends string>({ pilihan, nilai, onUbah, label }: {
  pilihan: { nilai: T; isi: ReactNode; warna?: string }[]; nilai: T[]; onUbah: (v: T[]) => void; label: string;
}) {
  return (
    <div className="tp-pil" role="group" aria-label={label}>
      {pilihan.map((p) => {
        const aktif = nilai.includes(p.nilai);
        return (
          <button key={p.nilai} type="button" aria-pressed={aktif} className={aktif ? "aktif" : ""}
            style={aktif && p.warna ? ({ "--w": p.warna } as React.CSSProperties) : undefined}
            onClick={() => onUbah(aktif ? nilai.filter((x) => x !== p.nilai) : [...nilai, p.nilai])}>
            {p.isi}
          </button>
        );
      })}
    </div>
  );
}

export function Saklar({ nilai, onUbah, label, title, disabled }: {
  nilai: boolean; onUbah: (v: boolean) => void; label: string; title?: string; disabled?: boolean;
}) {
  const id = useId();
  return (
    <span className={"tp-saklar" + (disabled ? " mati" : "")} title={title}>
      <Switch id={id} checked={nilai} disabled={disabled} onCheckedChange={onUbah} />
      <label htmlFor={id}>{label}</label>
    </span>
  );
}

/** Pilihan wilayah (multiselect): popover shadcn dengan daftar centang. */
export function PilihWilayah({ tersedia, nilai, onUbah, placeholder }: {
  tersedia: string[]; nilai: string[]; onUbah: (v: string[]) => void; placeholder: string;
}) {
  const [buka, setBuka] = useState(false);
  const id = useId();
  return (
    <div className="tp-wilayah">
      <label htmlFor={id}><Ikon nama="map-pin" ukuran={15} /> Wilayah</label>
      <Popover open={buka} onOpenChange={setBuka}>
        <PopoverAnchor asChild>
          <div className="kotak">
            {/* div, bukan button: tag di dalamnya punya tombol Hapus sendiri, dan button tidak boleh bersarang */}
            <div className="pemicu" onClick={() => setBuka(!buka)}>
              {nilai.length === 0 ? <span className="ph">{placeholder}</span> : (
                <span className="isi">
                  {nilai.map((w) => (
                    <span key={w} className="tag">
                      {w}
                      <button type="button" aria-label={`Hapus ${w}`}
                        onClick={(e) => { e.stopPropagation(); onUbah(nilai.filter((x) => x !== w)); }}>
                        <Ikon nama="x" ukuran={12} />
                      </button>
                    </span>
                  ))}
                </span>
              )}
              <span className="aksi">
                {nilai.length > 0 && (
                  <button type="button" className="hapus" aria-label="Kosongkan wilayah"
                    onClick={(e) => { e.stopPropagation(); onUbah([]); }}>
                    <Ikon nama="x" ukuran={14} />
                  </button>
                )}
                <PopoverTrigger asChild>
                  <button id={id} type="button" className="panah" aria-label="Pilih wilayah" onClick={(e) => e.stopPropagation()}>
                    <Ikon nama="chevron-down" ukuran={16} />
                  </button>
                </PopoverTrigger>
              </span>
            </div>
          </div>
        </PopoverAnchor>
        <PopoverContent align="start" sideOffset={4} className="tp-wilayah-daftar" role="listbox" aria-multiselectable="true">
          {tersedia.map((w) => {
            const pilih = nilai.includes(w);
            return (
              <button key={w} type="button" role="option" aria-selected={pilih} className={pilih ? "aktif" : ""}
                onClick={() => onUbah(pilih ? nilai.filter((x) => x !== w) : [...nilai, w].sort())}>
                <span className="centang">{pilih && <Ikon nama="check" ukuran={13} />}</span>{w}
              </button>
            );
          })}
        </PopoverContent>
      </Popover>
    </div>
  );
}

export function Tab({ tab, children }: { tab: { kunci: string; isi: ReactNode }[]; children: (aktif: string) => ReactNode }) {
  const [aktif, setAktif] = useState(tab[0]?.kunci ?? "");
  const id = useId();
  return (
    <Tabs value={aktif} onValueChange={setAktif} className="tp-tab">
      <TabsList variant="line" className="tp-tab-daftar">
        {tab.map((t) => (
          <TabsTrigger key={t.kunci} value={t.kunci} className="tp-tab-pemicu">
            {t.isi}
            {t.kunci === aktif && <motion.span layoutId={`garis-${id}`} className="tp-tab-garis" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value={aktif} className="tp-tab-isi">{children(aktif)}</TabsContent>
    </Tabs>
  );
}

export function Memuat({ teks = "Membaca data…" }: { teks?: string }) {
  return <div className="tp-memuat"><span className="putar" aria-hidden="true" />{teks}</div>;
}

export function Pesan({ ikon = "circle-alert", children }: { ikon?: NamaIkon; children: ReactNode }) {
  return <div className="tp-pesan"><Ikon nama={ikon} ukuran={18} />{children}</div>;
}
