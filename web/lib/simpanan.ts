"use client";

// Penyimpanan per tab peramban (sessionStorage) untuk filter dan pilihan yang harus bertahan saat pindah halaman.
// Mode privat atau penyimpanan yang diblokir tidak boleh merusak halaman, jadi semua galat diabaikan.

import { useEffect, useState } from "react";

export function bacaSimpanan<T>(kunci: string, bawaan: T): T {
  try {
    const mentah = sessionStorage.getItem(kunci);
    return mentah === null ? bawaan : (JSON.parse(mentah) as T) ?? bawaan;
  } catch {
    return bawaan;
  }
}

export function tulisSimpanan(kunci: string, nilai: unknown): void {
  try {
    sessionStorage.setItem(kunci, JSON.stringify(nilai));
  } catch {
    /* penyimpanan tidak tersedia: nilai hanya hidup di memori */
  }
}

/** State React yang dipulihkan dari sessionStorage sesudah mount (aman untuk static export) dan disimpan tiap diubah. */
export function useSimpanan<T>(kunci: string, bawaan: T): [T, (v: T) => void] {
  const [nilai, setNilai] = useState<T>(bawaan);
  useEffect(() => { setNilai(bacaSimpanan(kunci, bawaan)); }, [kunci]); // eslint-disable-line react-hooks/exhaustive-deps
  return [nilai, (v: T) => { setNilai(v); tulisSimpanan(kunci, v); }];
}
