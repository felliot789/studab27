import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: { default: "StudAb27 · Your next step abroad", template: "%s · StudAb27" }, description: "A quieter way to plan undergraduate engineering applications. Local scholarship research, document readiness, and three small next steps.", robots: { index: false, follow: false } };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
