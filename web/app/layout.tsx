import type { Metadata, Viewport } from "next";
import { PenyediaSesi } from "@/components/Sesi";
import "./globals.css";

export const metadata: Metadata = {
  title: "TEPAT",
  description: "Triase peserta tertunggak JKN: daftar kerja, profil peserta, kebijakan, dan keadilan.",
  icons: { icon: "/logo/tepat-mark.svg" },
};

export const viewport: Viewport = { themeColor: "#F6F5F0" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        <PenyediaSesi>{children}</PenyediaSesi>
      </body>
    </html>
  );
}
