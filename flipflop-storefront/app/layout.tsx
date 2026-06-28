import type { Metadata } from "next";
import { Space_Grotesk, Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

// Fonts from design-tokens.md
const heading = Space_Grotesk({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const body = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "FlipFlop — Made-to-Order PCs",
  description: "Curated second-hand components. Expert assembly. Delivered to your door.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${heading.variable} ${body.variable}`}>
      <body>
        <header
          className="sticky top-0 z-50 backdrop-blur-sm border-b"
          style={{
            borderColor: "var(--color-border)",
            background: "color-mix(in srgb, var(--color-bg) 80%, transparent)",
          }}
        >
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
            <Link href="/" className="font-bold text-lg tracking-tight" style={{ fontFamily: "var(--font-heading)" }}>
              FlipFlop
            </Link>
            <nav className="flex items-center gap-6 text-sm">
              <Link href="/#how-it-works" className="text-muted hover:text-white transition-colors">
                How it works
              </Link>
              <Link href="mailto:hello@flipflop.co.uk" className="text-muted hover:text-white transition-colors">
                Contact
              </Link>
            </nav>
          </div>
        </header>

        <main>{children}</main>

        <footer
          className="mt-24 py-12 text-center text-sm border-t"
          style={{
            borderColor: "var(--color-border)",
            color: "var(--color-text-muted)",
          }}
        >
          <p>© {new Date().getFullYear()} FlipFlop. All components are tested before dispatch.</p>
          <p className="mt-1">
            Questions?{" "}
            <a href="mailto:hello@flipflop.co.uk" className="underline hover:text-white">
              hello@flipflop.co.uk
            </a>
          </p>
        </footer>
      </body>
    </html>
  );
}
