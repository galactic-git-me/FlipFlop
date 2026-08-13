"use client";

export default function EbayPreviewDemo() {
  const ebayHtml = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Stunning Ryzen 7 7800X3D | RTX 3070 | 32GB DDR5 | Windows 11 Pro</title>
    <style>
        body { font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; }
        .header { border-bottom: 3px solid #0066ff; padding-bottom: 20px; margin-bottom: 30px; }
        .logo { font-size: 24px; font-weight: bold; background: linear-gradient(135deg, #0066ff 0%, #ff6600 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
        .tagline { font-size: 14px; color: #666; }
        h1 { font-size: 28px; font-weight: bold; margin: 30px 0 20px 0; color: #000; }
        h2 { font-size: 16px; font-weight: bold; margin: 20px 0 15px 0; color: #000; }
        .description { font-size: 14px; line-height: 1.8; color: #444; white-space: pre-wrap; margin-bottom: 30px; padding: 20px; background: #f8fafc; border-radius: 8px; }
        .section { margin-bottom: 30px; padding: 20px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
        .section-blue { border: 2px solid #0066ff; background: #f0f9ff; }
        .section-orange { border: 2px solid #ff6600; background: #fff9f0; }
        ul { list-style: none; padding: 0; margin: 0; }
        li { font-size: 14px; line-height: 1.7; color: #333; margin-bottom: 12px; padding-left: 24px; position: relative; }
        li:before { content: "▸"; position: absolute; left: 0; color: #0066ff; font-weight: bold; }
        .trust-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 20px; }
        .trust-item { padding: 16px; background: rgba(255,255,255,0.1); border-radius: 8px; text-align: center; color: white; font-size: 13px; }
        .trust-emoji { font-size: 24px; margin-bottom: 8px; }
        .footer { border-top: 2px solid #e2e8f0; padding-top: 20px; margin-top: 30px; text-align: center; font-size: 12px; color: #999; }
        strong { color: #0066ff; font-weight: 600; }
        p { margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">FlipFlop</div>
            <div class="tagline">Beautiful Machines Built to Be Admired</div>
        </div>

        <h1>Stunning Ryzen 7 7800X3D | RTX 3070 | 32GB DDR5 | Windows 11 Pro</h1>

        <div class="description">Experience elite gaming and demanding productivity with this pristine, high-end custom-built PC. Everything included is top-tier, meticulously assembled, and guaranteed to run games and applications at the highest settings.</div>

        <div class="section section-blue">
            <h2>✨ Key Features</h2>
            <ul>
                <li><strong>CPU:</strong> AMD Ryzen 7 7800X3D - The king of gaming CPUs, offering unmatched performance.</li>
                <li><strong>GPU:</strong> Palit RTX 3070 8GB - Perfect for high-refresh-rate 1440p gaming.</li>
                <li><strong>Memory:</strong> 32GB DDR5 6400MHz - Massive headroom for multitasking and future-proofing.</li>
                <li><strong>Storage:</strong> 1TB M.2 NVMe SSD - Lightning-fast boot times and load speeds.</li>
                <li><strong>Motherboard:</strong> ASUS PRIME X870-P - Robust platform for excellent stability.</li>
                <li><strong>Cooling & Aesthetics:</strong> Featuring the gorgeous APNX ChromaFlair Iridescent Chassis, white ARGB components (Thermalright Cooler & 6x Fans), and illuminated GPU bracket. This machine is as beautiful as powerful!</li>
                <li><strong>Power:</strong> Corsair RM750i Gold PSU - Reliable, fully modular power delivery.</li>
                <li><strong>OS:</strong> Includes Windows 11 Pro (Activated).</li>
            </ul>
        </div>

        <div class="section">
            <h2>🎮 Perfect For</h2>
            <ul>
                <li>• High-refresh-rate gaming (1080p/1440p)</li>
                <li>• Video editing and content creation</li>
                <li>• 3D rendering and 3D modeling</li>
                <li>• Streaming to Twitch/YouTube</li>
                <li>• Multitasking power users</li>
            </ul>
        </div>

        <div class="section section-orange">
            <h2>🛡️ Warranty & Returns</h2>
            <p>30-day money-back guarantee. All components tested and working perfectly.</p>
        </div>

        <div class="section">
            <h2>📦 Shipping</h2>
            <p>Fully insured shipping. Careful packaging to ensure safe arrival.</p>
        </div>

        <div class="section" style="background: linear-gradient(135deg, #0066ff 0%, #ff6600 100%); color: white; border: none; text-align: center;">
            <h2 style="color: white;">💯 Why Buy From FlipFlop?</h2>
            <div class="trust-grid">
                <div class="trust-item">
                    <div class="trust-emoji">✓</div>
                    <div><strong style="color: white;">Fully Tested</strong></div>
                    <div>Every build verified</div>
                </div>
                <div class="trust-item">
                    <div class="trust-emoji">⚡</div>
                    <div><strong style="color: white;">Expert Built</strong></div>
                    <div>20+ years experience</div>
                </div>
                <div class="trust-item">
                    <div class="trust-emoji">💎</div>
                    <div><strong style="color: white;">Great Value</strong></div>
                    <div>Transparent pricing</div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>FlipFlop • Professional PC Builds • Every machine is inspected and tested before shipment.</p>
        </div>
    </div>
</body>
</html>
  `;

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-2">eBay Listing Preview</h1>
          <p className="text-slate-400">This is what your beautiful HTML listing looks like when published to eBay</p>
        </div>

        {/* Embedded HTML Preview */}
        <div className="bg-white rounded-lg shadow-2xl overflow-hidden">
          <iframe
            srcDoc={ebayHtml}
            className="w-full h-screen border-0"
            title="eBay Listing Preview"
          />
        </div>
      </div>
    </div>
  );
}
