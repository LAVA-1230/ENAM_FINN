import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Condensed, IBM_Plex_Serif } from "next/font/google";
import { Providers } from "@/components/providers";
import { Banners, BottomNav } from "@/components/shell";
import "./globals.css";

// Three voices of one superfamily: FINN speaks in sans, numbers in condensed, documents in serif.
const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-sans", display: "swap" });
const num = IBM_Plex_Sans_Condensed({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-num", display: "swap" });
const quote = IBM_Plex_Serif({ subsets: ["latin"], weight: ["400"], style: ["italic"], variable: "--font-quote", display: "swap" });

export const metadata: Metadata = {
  title: "FINN",
  description: "FINN interrupts you only when your thesis might be broken. Everything else waits for a batched brief.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "FINN", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/icon-192.png" },
};

export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover",
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#E6EBE7" }, { media: "(prefers-color-scheme: dark)", color: "#12171F" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${sans.variable} ${num.variable} ${quote.variable}`} suppressHydrationWarning>
      <head>
        {/* apply the saved light/dark choice before first paint */}
        <script dangerouslySetInnerHTML={{ __html: "try{var t=localStorage.getItem('finn-theme');if(t&&t!=='system')document.documentElement.setAttribute('data-theme',t)}catch(e){}" }} />
      </head>
      <body>
        <Providers>
          <div className="mx-auto min-h-screen max-w-app pb-24">
            <Banners />
            {children}
          </div>
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
