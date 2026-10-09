import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FlipFlop.shop - Curated PC Builds',
  description: 'Professional curated PC builds for gaming, work, and AI. Built from quality components with warranty.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <nav className="border-b border-[var(--card-border)] bg-[var(--background)]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center">
                <a href="/" className="text-xl font-bold">
                  FlipFlop<span className="text-[var(--accent)]">.shop</span>
                </a>
              </div>
              <div className="flex gap-6">
                <a href="/" className="hover:text-[var(--accent)] transition-colors">
                  Browse Builds
                </a>
                <a href="/about" className="hover:text-[var(--accent)] transition-colors">
                  About
                </a>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
        <footer className="border-t border-[var(--card-border)] mt-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div>
                <h3 className="font-bold mb-4">FlipFlop</h3>
                <p className="text-[var(--muted)] text-sm">
                  Professional PC builds from curated components. Every build includes warranty and delivery.
                </p>
              </div>
              <div>
                <h3 className="font-bold mb-4">Support</h3>
                <ul className="space-y-2 text-sm text-[var(--muted)]">
                  <li><a href="/warranty" className="hover:text-[var(--foreground)]">Warranty</a></li>
                  <li><a href="/delivery" className="hover:text-[var(--foreground)]">Delivery</a></li>
                  <li><a href="/returns" className="hover:text-[var(--foreground)]">Returns</a></li>
                </ul>
              </div>
              <div>
                <h3 className="font-bold mb-4">Company</h3>
                <ul className="space-y-2 text-sm text-[var(--muted)]">
                  <li><a href="/about" className="hover:text-[var(--foreground)]">About Us</a></li>
                  <li><a href="/contact" className="hover:text-[var(--foreground)]">Contact</a></li>
                </ul>
              </div>
            </div>
            <div className="mt-8 pt-8 border-t border-[var(--card-border)] text-center text-sm text-[var(--muted)]">
              © {new Date().getFullYear()} FlipFlop. All rights reserved.
            </div>
          </div>
        </footer>
      </body>
    </html>
  )
}
