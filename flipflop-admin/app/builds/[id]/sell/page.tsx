"use client";

import { useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { Send, Zap, Eye } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ListingData {
  title: string;
  description: string;
  keyFeatures: string[];
  perfectFor: string[];
  warranty: string;
  shipping: string;
}

function generateEbayHtml(listing: ListingData): string {
  return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${listing.title}</title>
    <style>
        body { font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; margin: 0; }
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

        <h1>${listing.title}</h1>

        <div class="description">${listing.description}</div>

        <div class="section section-blue">
            <h2>✨ Key Features</h2>
            <ul>
                ${listing.keyFeatures.map(f => `<li>${f.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')}</li>`).join("")}
            </ul>
        </div>

        ${listing.perfectFor && listing.perfectFor.length > 0 ? `
        <div class="section">
            <h2>🎮 Perfect For</h2>
            <ul>
                ${listing.perfectFor.map(f => `<li>• ${f}</li>`).join("")}
            </ul>
        </div>
        ` : ""}

        <div class="section section-orange">
            <h2>🛡️ Warranty & Returns</h2>
            <p>${listing.warranty}</p>
        </div>

        <div class="section">
            <h2>📦 Shipping</h2>
            <p>${listing.shipping}</p>
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
  `.trim();
}

export default function SellBuildPage() {
  const params = useParams();
  const router = useRouter();
  const buildId = params.id as string;

  const [listing, setListing] = useState<ListingData>({
    title: "Stunning Ryzen 7 7800X3D | RTX 3070 | 32GB DDR5 | Windows 11 Pro",
    description: `Experience elite gaming and demanding productivity with this pristine, high-end custom-built PC. Everything included is top-tier, meticulously assembled, and guaranteed to run games and applications at the highest settings.`,
    keyFeatures: [
      "**CPU:** AMD Ryzen 7 7800X3D - The king of gaming CPUs, offering unmatched performance.",
      "**GPU:** Palit RTX 3070 8GB - Perfect for high-refresh-rate 1440p gaming.",
      "**Memory:** 32GB DDR5 6400MHz - Massive headroom for multitasking and future-proofing.",
      "**Storage:** 1TB M.2 NVMe SSD - Lightning-fast boot times and load speeds.",
      "**Motherboard:** ASUS PRIME X870-P - Robust platform for excellent stability.",
      "**Cooling & Aesthetics:** Featuring the gorgeous APNX ChromaFlair Iridescent Chassis, white ARGB components (Thermalright Cooler & 6x Fans), and illuminated GPU bracket. This machine is as beautiful as powerful!",
      "**Power:** Corsair RM750i Gold PSU - Reliable, fully modular power delivery.",
      "**OS:** Includes Windows 11 Pro (Activated).",
    ],
    perfectFor: [
      "High-refresh-rate gaming (1080p/1440p)",
      "Video editing and content creation",
      "3D rendering and 3D modeling",
      "Streaming to Twitch/YouTube",
      "Multitasking power users",
    ],
    warranty: "30-day money-back guarantee. All components tested and working perfectly.",
    shipping: "Fully insured shipping. Careful packaging to ensure safe arrival.",
  });

  const [publishing, setPublishing] = useState(false);
  const [publishMode, setPublishMode] = useState<"ebay" | "flipflop" | null>(null);

  const handlePublish = async (target: "ebay" | "flipflop") => {
    setPublishing(true);
    setPublishMode(target);

    try {
      // TODO: Integrate with actual API
      const response = await fetch(`/api/builds/${buildId}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target,
          listing,
        }),
      });

      if (response.ok) {
        alert(`Published to ${target === "ebay" ? "eBay" : "FlipFlop.shop"}!`);
        if (target === "ebay") {
          // Redirect to eBay listing
          const data = await response.json();
          window.open(data.ebayUrl, "_blank");
        } else {
          router.push(`/builds/${buildId}`);
        }
      }
    } catch (error) {
      alert("Failed to publish. Please try again.");
      console.error(error);
    } finally {
      setPublishing(false);
      setPublishMode(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0f1a]">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Sell This Build</h1>
          <p className="text-sm text-slate-400">Create your eBay listing or publish to FlipFlop.shop</p>
        </div>

        {/* Split Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-6">
          {/* Left: Edit Form */}
          <div className="space-y-4 max-h-[calc(100vh-300px)] overflow-y-auto">
            {/* Title */}
            <Card className="bg-[#0f1620] border-slate-700">
              <CardHeader>
                <CardTitle className="text-sm text-white">Listing Title</CardTitle>
              </CardHeader>
              <CardContent>
                <textarea
                  value={listing.title}
                  onChange={(e) => setListing({ ...listing, title: e.target.value })}
                  className="w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none"
                  rows={3}
                />
                <p className="text-xs text-slate-500 mt-2">{listing.title.length}/80 characters recommended</p>
              </CardContent>
            </Card>

            {/* Description */}
            <Card className="bg-[#0f1620] border-slate-700">
              <CardHeader>
                <CardTitle className="text-sm text-white">Description</CardTitle>
              </CardHeader>
              <CardContent>
                <textarea
                  value={listing.description}
                  onChange={(e) => setListing({ ...listing, description: e.target.value })}
                  className="w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none"
                  rows={6}
                />
              </CardContent>
            </Card>

            {/* Key Features */}
            <Card className="bg-[#0f1620] border-slate-700">
              <CardHeader>
                <CardTitle className="text-sm text-white">Key Features</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {listing.keyFeatures.map((feature, idx) => (
                  <div key={idx} className="flex gap-2">
                    <input
                      type="text"
                      value={feature}
                      onChange={(e) => {
                        const updated = [...listing.keyFeatures];
                        updated[idx] = e.target.value;
                        setListing({ ...listing, keyFeatures: updated });
                      }}
                      className="flex-1 px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-xs text-slate-300 outline-none focus:border-orange-400"
                    />
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Warranty */}
            <Card className="bg-[#0f1620] border-slate-700">
              <CardHeader>
                <CardTitle className="text-sm text-white">Warranty & Returns</CardTitle>
              </CardHeader>
              <CardContent>
                <textarea
                  value={listing.warranty}
                  onChange={(e) => setListing({ ...listing, warranty: e.target.value })}
                  className="w-full px-3 py-2 bg-[#141d2d] border border-slate-600 rounded text-sm text-slate-300 outline-none focus:border-orange-400 resize-none"
                  rows={3}
                />
              </CardContent>
            </Card>
          </div>

          {/* Right: Live Preview */}
          <div className="hidden lg:flex sticky top-6 h-[calc(100vh-200px)] overflow-hidden flex-col">
            <div className="border border-orange-400/30 bg-orange-400/5 rounded-lg p-3 mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Eye size={16} className="text-orange-400" />
                <h2 className="text-xs font-bold text-orange-400 uppercase">Live eBay Preview</h2>
              </div>
              <p className="text-xs text-slate-400">This is how your listing will appear to eBay buyers</p>
            </div>

            <div className="flex-1 bg-white rounded-lg overflow-hidden shadow-2xl border border-slate-200">
              <iframe
                srcDoc={generateEbayHtml(listing)}
                className="w-full h-full border-0"
                title="eBay Listing Preview"
              />
            </div>
          </div>
        </div>

        {/* Publish Buttons */}
        <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-[#0a0f1a] via-[#0a0f1a] to-transparent p-6 border-t border-slate-700">
          <div className="max-w-7xl mx-auto flex gap-3 justify-end">
            <button
              onClick={() => router.back()}
              className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
              disabled={publishing}
            >
              Cancel
            </button>

            <button
              onClick={() => handlePublish("flipflop")}
              disabled={publishing}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              <Zap size={16} />
              {publishing && publishMode === "flipflop" ? "Publishing..." : "Publish to FlipFlop.shop"}
            </button>

            <button
              onClick={() => handlePublish("ebay")}
              disabled={publishing}
              className="flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-orange-400 to-orange-600 hover:from-orange-500 hover:to-orange-700 text-white rounded-lg font-bold transition-colors disabled:opacity-50"
            >
              <Send size={16} />
              {publishing && publishMode === "ebay" ? "Publishing..." : "Publish to eBay"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
