// Salin font dan logo dari static/ (sumber tunggal, dipakai juga aplikasi Streamlit) ke public/.
import { cpSync, mkdirSync } from "node:fs";

for (const folder of ["fonts", "logo"]) {
  mkdirSync(`public/${folder}`, { recursive: true });
  cpSync(`../static/${folder}`, `public/${folder}`, { recursive: true });
}
