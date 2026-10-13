import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "JARVAS — Face Detection & Recognition",
    template: "%s · JARVAS",
  },
  description:
    "Privacy-first face detection with optional, consent-gated recognition. Detection-only by default; every match requires human review.",
  applicationName: "JARVAS",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#070b1a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} dark`} suppressHydrationWarning>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
