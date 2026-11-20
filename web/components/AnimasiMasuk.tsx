"use client";

import { useRef, type ReactNode } from "react";
import { useAnimeMasuk } from "@/lib/animasi";

/** Membungkus grafik tanpa mengubah tata letak (display: contents) dan menjalankan animasi masuk anime.js. */
export function AnimasiMasuk({ kunci, children }: { kunci?: unknown; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useAnimeMasuk(ref, kunci);
  return <div ref={ref} style={{ display: "contents" }}>{children}</div>;
}
