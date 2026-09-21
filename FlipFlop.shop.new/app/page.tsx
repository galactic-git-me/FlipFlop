import Link from 'next/link'

export default function Home() {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Build Your Perfect PC,<br />
            <span className="text-[var(--accent)]">Backed by Experts</span>
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto mb-12">
            Professional curated builds from quality components. Tested, warranted, and delivered.
            Tell us your budget and what you'll use it for — we'll show you the perfect match.
          </p>
          
          <Link
            href="/build"
            className="inline-block px-8 py-4 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-bold text-lg transition-colors"
          >
            Start Building →
          </Link>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-[var(--card-bg)]">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-[var(--accent)]/20 border border-[var(--accent)] rounded-full flex items-center justify-center text-2xl font-bold">
                1
              </div>
              <h3 className="font-bold mb-2">Choose Budget</h3>
              <p className="text-sm text-[var(--muted)]">
                Tell us what you're comfortable spending (all-in price)
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-[var(--accent)]/20 border border-[var(--accent)] rounded-full flex items-center justify-center text-2xl font-bold">
                2
              </div>
              <h3 className="font-bold mb-2">Pick Your Type</h3>
              <p className="text-sm text-[var(--muted)]">
                Gaming? Work? AI? Choose what matters to you
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-[var(--accent)]/20 border border-[var(--accent)] rounded-full flex items-center justify-center text-2xl font-bold">
                3
              </div>
              <h3 className="font-bold mb-2">See Your Match</h3>
              <p className="text-sm text-[var(--muted)]">
                We show you the best build for your budget × purpose
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-[var(--accent)]/20 border border-[var(--accent)] rounded-full flex items-center justify-center text-2xl font-bold">
                4
              </div>
              <h3 className="font-bold mb-2">Customize & Order</h3>
              <p className="text-sm text-[var(--muted)]">
                Fine-tune case, RAM, storage — then checkout
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Prometheus Pre-built Banner */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="p-8 rounded-lg border-2 border-[var(--accent)] bg-[var(--card-bg)]">
            <div className="flex items-start gap-4 flex-col md:flex-row">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-2xl font-bold">Prometheus ChromaFlair</h2>
                  <span className="text-xs px-2 py-1 rounded bg-[var(--accent)]/20 text-[var(--accent)] border border-[var(--accent)]/50">
                    Pre-built • Ready to Ship
                  </span>
                </div>
                <p className="text-[var(--muted)] mb-4">
                  Our signature showcase build featuring the stunning APNX Creator C1 ChromaFlair case. 
                  Pre-built, tested, and ready for immediate dispatch.
                </p>
                <div className="flex items-center gap-4 mb-4">
                  <span className="text-3xl font-bold">£1,449</span>
                  <span className="text-sm text-[var(--muted)]">Ships within 2 days</span>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                <Link
                  href="/prometheus"
                  className="inline-block px-6 py-3 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-medium transition-colors text-center"
                >
                  View Details →
                </Link>
                <Link
                  href="/build"
                  className="inline-block px-6 py-3 border border-[var(--card-border)] hover:border-[var(--accent)] rounded-lg font-medium transition-colors text-center"
                >
                  Build Custom Instead
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Trust Indicators */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
            <div>
              <div className="text-4xl mb-3">✓</div>
              <h3 className="font-bold mb-2">12-Month Warranty</h3>
              <p className="text-sm text-[var(--muted)]">
                Every build covered for parts and labour
              </p>
            </div>
            <div>
              <div className="text-4xl mb-3">⚡</div>
              <h3 className="font-bold mb-2">Tested & Benchmarked</h3>
              <p className="text-sm text-[var(--muted)]">
                Stress-tested and performance verified before shipping
              </p>
            </div>
            <div>
              <div className="text-4xl mb-3">📦</div>
              <h3 className="font-bold mb-2">Insured Delivery</h3>
              <p className="text-sm text-[var(--muted)]">
                Fully insured shipping, delivered in 3-5 working days
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
