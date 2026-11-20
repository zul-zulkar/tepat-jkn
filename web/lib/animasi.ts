"use client";

// Animasi masuk untuk grafik SVG dengan anime.js. Elemen ditandai lewat atribut data-anim:
//   batang  : tumbuh dari dasar (scaleY)      garis : digambar dari awal ke akhir (draw)
//   pita    : tumbuh dari kiri (scaleX)       lebar : sama, untuk batang HTML
// Dilewati bila pengguna meminta gerak dikurangi. Hasil akhir tampilan tidak bergantung pada animasi.

import { animate, stagger, svg } from "animejs";
import { useEffect, type RefObject } from "react";

export const kurangiGerak = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useAnimeMasuk(ref: RefObject<HTMLElement | null>, kunci: unknown) {
  useEffect(() => {
    const akar = ref.current;
    if (!akar || kurangiGerak()) return;
    const jalan: { revert: () => unknown }[] = [];
    const ambil = (nama: string) => akar.querySelectorAll<SVGElement | HTMLElement>(`[data-anim="${nama}"]`);

    const batang = ambil("batang");
    if (batang.length) jalan.push(animate(batang, { scaleY: [0, 1], duration: 650, delay: stagger(6), ease: "outCubic" }));
    const pita = ambil("pita");
    if (pita.length) jalan.push(animate(pita, { scaleX: [0, 1], duration: 700, delay: stagger(25), ease: "outCubic" }));
    const lebar = ambil("lebar");
    if (lebar.length) jalan.push(animate(lebar, { scaleX: [0, 1], duration: 700, delay: stagger(30), ease: "outCubic" }));
    const garis = ambil("garis");
    if (garis.length) jalan.push(animate(svg.createDrawable(garis), { draw: ["0 0", "0 1"], duration: 1100, delay: 250, ease: "inOutQuad" }));

    return () => jalan.forEach((a) => a.revert());
  }, [ref, kunci]);
}
