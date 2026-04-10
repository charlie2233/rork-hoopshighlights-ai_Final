import type { ReactNode } from "react";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { getDashboardEnv } from "@/lib/env";

const sans = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap"
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  display: "swap"
});

export const metadata = {
  title: "HoopsClips Review Dashboard",
  description: "Internal review and admin surface for the HoopsClips production pipeline."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const env = getDashboardEnv();

  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <div className="shell">
          <header className="topbar">
            <div className="brand">
              <div className="brand-mark">HC</div>
              <div className="brand-title">
                <strong>{env.dashboardName}</strong>
                <span>
                  Internal review surface for the Cloudflare control plane
                  {" "}
                  <span className="badge" style={{ marginLeft: 8 }}>
                    {env.environment}
                  </span>
                </span>
              </div>
            </div>
            <nav className="nav" aria-label="Primary">
              <Link href="/">Overview</Link>
              <Link href="/jobs">Jobs</Link>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
