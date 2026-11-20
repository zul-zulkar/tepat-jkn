"use client";

// Tooltip untuk grafik SVG: posisi mengikuti kursor di dalam wadah grafik.

import { useCallback, useRef, useState, type ReactNode } from "react";

export interface IsiTip { judul: string; teks: string }

export function useTip() {
  const wadah = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<(IsiTip & { x: number; y: number }) | null>(null);
  const tunjuk = useCallback((isi: IsiTip) => ({
    onMouseMove: (e: React.MouseEvent) => {
      const r = wadah.current?.getBoundingClientRect();
      if (r) setTip({ ...isi, x: e.clientX - r.left, y: e.clientY - r.top });
    },
    onMouseLeave: () => setTip(null),
  }), []);
  const lapisan: ReactNode = tip && (
    <div className="tp-tip" style={{ left: tip.x, top: tip.y }} role="tooltip">
      <b>{tip.judul}</b>{tip.teks}
    </div>
  );
  return { wadah, tunjuk, lapisan };
}
