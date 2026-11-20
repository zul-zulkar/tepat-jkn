import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Gabungkan nama kelas; kelas Tailwind yang bentrok diselesaikan (yang terakhir menang). */
export function cn(...input: ClassValue[]) {
  return twMerge(clsx(input));
}
