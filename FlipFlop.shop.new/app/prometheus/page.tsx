import { formatPrice } from '@/lib/utils'
import Link from 'next/link'

export default function PrometheusPage() {
  const productionCost = 944.74
  const sellPrice = 1449
  const margin = sellPrice - productionCost

  return (
    <div className="min-h-screen bg-[var(--background)] py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <Link href="/" className="text-[var(--accent)] hover:underline mb-8 inline-block">
          ← Back to Browse
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
          {/* Left - Images & Preview */}
          <div>
            <div className="bg-[var(--card-bg)] border-2 border-[var(--accent)] rounded-lg p-12 aspect-square flex items-center justify-center mb-6">
              <div className="text-center space-y-4">
                <div className="text-8xl">✨</div>
                <div className="text-2xl font-bold">Prometheus ChromaFlair</div>
                <div className="text-[var(--muted)]">Pre-built Showcase System</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded aspect-square flex items-center justify-center">
                  <span className="text-2xl">📸</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right - Details */}
          <div>
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-3">
                <span className="px-3 py-1 bg-[var(--accent)]/20 border border-[var(--accent)] text-[var(--accent)] text-sm rounded font-medium">
                  Pre-built • In Stock
                </span>
                <span className="px-3 py-1 bg-blue-900/20 border border-blue-700 text-blue-400 text-sm rounded">
                  High-performance Gaming
                </span>
              </div>
              <h1 className="text-5xl font-bold mb-4">Prometheus ChromaFlair</h1>
              <p className="text-xl text-[var(--muted)] mb-6">
                Beautiful machines, built to be admired. Our signature showcase build featuring 
                the stunning APNX Creator C1 ChromaFlair case.
              </p>
            </div>

            {/* Specifications */}
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6 mb-6">
              <h2 className="text-2xl font-bold mb-4">Specifications</h2>
              <div className="space-y-3">
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Processor</span>
                  <span className="text-right font-medium">AMD Ryzen 7 7800X3D</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Graphics Card</span>
                  <span className="text-right font-medium">AMD Radeon RX 9070 XT 16GB</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Memory</span>
                  <span className="text-right font-medium">32GB Lexar DDR5-6400 CL38</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Storage</span>
                  <span className="text-right font-medium">1TB PCIe 3.0 NVMe SSD</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Motherboard</span>
                  <span className="text-right font-medium">ASUS PRIME X870-P</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Power Supply</span>
                  <span className="text-right font-medium">Corsair RM750i 750W Modular</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Cooling</span>
                  <span className="text-right font-medium">Thermalright Aqua Elite 240 V3</span>
                </div>
                <div className="flex justify-between py-2 border-b border-[var(--card-border)]">
                  <span className="text-[var(--muted)]">Case</span>
                  <span className="text-right font-medium">APNX Creator C1 ChromaFlair</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-[var(--muted)]">Operating System</span>
                  <span className="text-right font-medium">Windows 11 Home</span>
                </div>
              </div>
            </div>

            {/* Pricing */}
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-6 mb-6">
              <div className="flex items-baseline justify-between mb-4">
                <span className="text-4xl font-bold">{formatPrice(sellPrice)}</span>
                <span className="text-sm text-[var(--muted)]">
                  Production cost: {formatPrice(productionCost)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm mb-4 pb-4 border-b border-[var(--card-border)]">
                <span className="text-[var(--muted)]">Margin</span>
                <span className="text-green-400 font-medium">
                  +{formatPrice(margin)} ({Math.round((margin / productionCost) * 100)}%)
                </span>
              </div>
              
              <button className="w-full py-4 bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded-lg font-bold text-lg transition-colors mb-3">
                Add to Cart
              </button>
              
              <p className="text-xs text-[var(--muted)] text-center">
                Pre-built and tested. Ships within 2 working days.
              </p>
            </div>

            {/* Features */}
            <div className="space-y-4">
              <h3 className="font-bold text-lg">What Makes This Special</h3>
              <ul className="space-y-2 text-[var(--muted)]">
                <li className="flex items-start gap-2">
                  <span className="text-[var(--accent)]">✓</span>
                  <span>Stunning APNX Creator C1 ChromaFlair case with color-shifting finish</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--accent)]">✓</span>
                  <span>AMD Ryzen 7 7800X3D - best gaming CPU for 1440p/4K</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--accent)]">✓</span>
                  <span>Premium liquid cooling with RGB synchronization</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--accent)]">✓</span>
                  <span>Professional cable management and build quality</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--accent)]">✓</span>
                  <span>12-month comprehensive warranty</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--accent)]">✓</span>
                  <span>Fully tested and benchmarked before shipping</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
