import type { NextConfig } from "next";

// Produksi: static export (folder out/) yang disajikan server Go bersama API-nya, satu proses.
// Pengembangan: `next dev` meneruskan /api ke server Go di TEPAT_API (bawaan http://127.0.0.1:8080).
const api = process.env.TEPAT_API ?? "http://127.0.0.1:8080";
const dev = process.env.NODE_ENV === "development";

const config: NextConfig = {
  output: dev ? undefined : "export",
  trailingSlash: true,
  skipTrailingSlashRedirect: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  ...(dev && {
    async rewrites() {
      return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
    },
  }),
};

export default config;
