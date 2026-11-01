import type { NextConfig } from "next";
const config: NextConfig = {
  poweredByHeader: false,
  outputFileTracingExcludes: { "/*": ["./private/**/*", "./**/*.local.*", "./.env*", "./artifacts/**/*"] },
  experimental: { cpus: 2 },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "Cache-Control", value: "no-store, private" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws://127.0.0.1:3270 ws://localhost:3270; font-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'" },
    ] }];
  },
};
export default config;
