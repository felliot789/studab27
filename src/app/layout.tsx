import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./redesign.css";

export const metadata: Metadata = { title: { default: "StudAb27 · Scholarship tracker", template: "%s · StudAb27" }, description: "Undergraduate engineering scholarship research, application tracking, deadlines, and document readiness.", robots: { index: false, follow: false } };
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", interactiveWidget: "resizes-content", themeColor: "#181818", colorScheme: "dark" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
