"use client";
/* eslint-disable @next/next/no-img-element */

import { Star, Zap, Shield, Cpu, TrendingUp, Play } from "lucide-react";

interface BuildListingTemplateProps {
  buildName: string;
  totalCost: number;
  components: {
    slot: string;
    name: string;
    price_paid: number;
    market_price_avg?: number;
  }[];
  totalMarketValue?: number;
  profitPotential?: number;
  dealScore?: number;
  condition?: "new" | "used" | "refurb";
  heroImageUrl?: string;
  heroVideoUrl?: string;
  description?: string;
}

const COMPANY_STORY = `
<div style="background: linear-gradient(135deg, #0066ff 0%, #ff6600 100%); padding: 40px; border-radius: 12px; margin-bottom: 30px; color: white;">
  <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 24px;">
    <img src="/flipflop.shop/public/media/flipflop-glow-transparent.png" alt="FlipFlop Logo" style="width: 80px; height: 80px; object-fit: contain; filter: drop-shadow(0 0 10px rgba(255,255,255,0.3));" />
    <div>
      <h2 style="font-size: 28px; font-weight: bold; margin: 0 0 8px 0; color: white;">About FlipFlop</h2>
      <p style="font-size: 14px; margin: 0; opacity: 0.95;">Expert PC builds. Transparent pricing. 20+ years experience.</p>
    </div>
  </div>
  <p style="font-size: 16px; line-height: 1.6; margin: 0 0 12px 0;">
    FlipFlop was founded by a passionate software engineer with over 20 years of experience in technology, who has spent countless hours building high-performance PCs for friends and family. What started as a hobby evolved into a mission: to bring expertly-crafted, value-driven PC builds to the broader market.
  </p>
  <p style="font-size: 16px; line-height: 1.6; margin: 0 0 12px 0;">
    We believe that getting a powerful PC shouldn't mean breaking the bank. By leveraging market insight and meticulous component selection, we source premium hardware at exceptional value and assemble them into complete, tested systems ready to perform.
  </p>
  <p style="font-size: 16px; line-height: 1.6; margin: 0;">
    <strong>Every build is a reflection of our commitment to quality, transparency, and customer satisfaction.</strong>
  </p>
</div>
`;

export function BuildListingTemplate({
  buildName,
  totalCost,
  components,
  totalMarketValue = 0,
  profitPotential = 0,
  dealScore = 0,
  condition = "used",
  heroImageUrl,
  description,
}: BuildListingTemplateProps) {
  const markup = totalMarketValue - totalCost;
  const roi = totalCost > 0 ? ((markup / totalCost) * 100).toFixed(0) : "0";

  return (
    <div style={{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", backgroundColor: "#f8fafc", color: "#1e293b" }}>
      {/* Company Story Section */}
      <div style={{ maxWidth: "900px", margin: "0 auto", padding: "40px 20px" }} dangerouslySetInnerHTML={{ __html: COMPANY_STORY }} />

      {/* Main Build Showcase */}
      <div style={{ maxWidth: "900px", margin: "0 auto", padding: "0 20px 60px" }}>
        {/* Hero Section */}
        {heroImageUrl && (
          <div style={{ marginBottom: 30, borderRadius: 12, overflow: "hidden", boxShadow: "0 20px 60px rgba(0,0,0,0.1)", height: 400, backgroundColor: "#e2e8f0" }}>
            <img
              src={heroImageUrl}
              alt={buildName}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>
        )}

        {/* Build Header */}
        <div style={{ marginBottom: 30 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              {[...Array(5)].map((_, i) => (
                <Star key={i} size={16} style={{ fill: i < 5 ? "#f59e0b" : "#e5e7eb", color: i < 5 ? "#f59e0b" : "#e5e7eb" }} />
              ))}
            </div>
            <span style={{ fontSize: 14, color: "#666", fontWeight: 500 }}>Expert-Selected Components</span>
          </div>

          <h1 style={{ fontSize: 40, fontWeight: "bold", margin: "0 0 12px 0", color: "#000" }}>{buildName}</h1>

          <p style={{ fontSize: 18, color: "#666", lineHeight: 1.6, margin: 0 }}>
            {description || "A carefully curated PC build featuring premium components, rigorously tested and ready to deliver exceptional performance."}
          </p>
        </div>

        {/* Key Metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 20, marginBottom: 40 }}>
          {/* Total Cost */}
          <div style={{ padding: 24, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
            <div style={{ fontSize: 13, color: "#666", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.5px" }}>Total Build Cost</div>
            <div style={{ fontSize: 32, fontWeight: "bold", color: "#0066ff" }}>£{totalCost.toFixed(2)}</div>
            <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>Invested in quality</div>
          </div>

          {/* Market Value */}
          {totalMarketValue > 0 && (
            <div style={{ padding: 24, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <div style={{ fontSize: 13, color: "#666", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.5px" }}>Market Value</div>
              <div style={{ fontSize: 32, fontWeight: "bold", color: "#10b981" }}>£{totalMarketValue.toFixed(2)}</div>
              <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>Current market retail</div>
            </div>
          )}

          {/* Potential Markup */}
          {markup > 0 && (
            <div style={{ padding: 24, backgroundColor: "linear-gradient(135deg, #0066ff 0%, #ff6600 100%)", borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", color: "white" }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.5px", opacity: 0.9 }}>Value Potential</div>
              <div style={{ fontSize: 32, fontWeight: "bold" }}>£{markup.toFixed(2)}</div>
              <div style={{ fontSize: 12, marginTop: 4, opacity: 0.9 }}>+{roi}% potential markup</div>
            </div>
          )}

          {/* Deal Score */}
          {dealScore > 0 && (
            <div style={{ padding: 24, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <div style={{ fontSize: 13, color: "#666", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.5px" }}>Deal Score</div>
              <div style={{ fontSize: 32, fontWeight: "bold", color: "#ff6600" }}>{dealScore.toFixed(1)}/10</div>
              <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>Exceptional value</div>
            </div>
          )}
        </div>

        {/* Component Breakdown */}
        <div style={{ marginBottom: 40 }}>
          <h2 style={{ fontSize: 24, fontWeight: "bold", marginBottom: 24, color: "#000" }}>Component Specifications</h2>

          <div style={{ display: "grid", gap: 12 }}>
            {components.map((comp, idx) => (
              <div key={idx} style={{ padding: 20, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 12, color: "#999", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>{comp.slot}</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: "#000" }}>{comp.name}</div>
                </div>

                <div>
                  <div style={{ fontSize: 12, color: "#999", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Your Price</div>
                  <div style={{ fontSize: 18, fontWeight: "bold", color: "#667eea" }}>£{comp.price_paid.toFixed(2)}</div>
                </div>

                {comp.market_price_avg && (
                  <div>
                    <div style={{ fontSize: 12, color: "#999", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Market Value</div>
                    <div style={{ fontSize: 18, fontWeight: "bold", color: "#10b981" }}>£{comp.market_price_avg.toFixed(2)}</div>
                    <div style={{ fontSize: 11, color: comp.market_price_avg > comp.price_paid ? "#10b981" : "#ef4444", marginTop: 2, fontWeight: 500 }}>
                      {comp.market_price_avg > comp.price_paid ? "✓ Great deal" : "Standard price"}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Why Choose FlipFlop */}
        <div style={{ backgroundColor: "#f0f9ff", padding: 40, borderRadius: 12, marginBottom: 40, border: "2px solid #0066ff" }}>
          <h2 style={{ fontSize: 24, fontWeight: "bold", marginBottom: 24, color: "#000" }}>Why This Build is Special</h2>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 24 }}>
            <div style={{ display: "flex", gap: 16 }}>
              <div style={{ flexShrink: 0 }}>
                <Zap size={24} style={{ color: "#0066ff" }} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: "bold", marginBottom: 8, color: "#000" }}>Performance Optimized</h3>
                <p style={{ fontSize: 14, color: "#666", margin: 0, lineHeight: 1.6 }}>Each component is selected for compatibility and performance synergy, not just specs.</p>
              </div>
            </div>

            <div style={{ display: "flex", gap: 16 }}>
              <div style={{ flexShrink: 0 }}>
                <Shield size={24} style={{ color: "#0066ff" }} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: "bold", marginBottom: 8, color: "#000" }}>Fully Tested</h3>
                <p style={{ fontSize: 14, color: "#666", margin: 0, lineHeight: 1.6 }}>Every build is assembled, stress-tested, and verified to work flawlessly before shipping.</p>
              </div>
            </div>

            <div style={{ display: "flex", gap: 16 }}>
              <div style={{ flexShrink: 0 }}>
                <TrendingUp size={24} style={{ color: "#0066ff" }} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: "bold", marginBottom: 8, color: "#000" }}>Exceptional Value</h3>
                <p style={{ fontSize: 14, color: "#666", margin: 0, lineHeight: 1.6 }}>Sourced at market lows and priced competitively to deliver real value to your investment.</p>
              </div>
            </div>

            <div style={{ display: "flex", gap: 16 }}>
              <div style={{ flexShrink: 0 }}>
                <Cpu size={24} style={{ color: "#0066ff" }} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: "bold", marginBottom: 8, color: "#000" }}>Expert Selection</h3>
                <p style={{ fontSize: 14, color: "#666", margin: 0, lineHeight: 1.6 }}>Curated by a seasoned engineer with 20+ years of PC building experience for friends and family.</p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA Section */}
        <div style={{ backgroundColor: "linear-gradient(135deg, #0066ff 0%, #ff6600 100%)", color: "white", padding: 40, borderRadius: 12, textAlign: "center" }}>
          <h2 style={{ fontSize: 28, fontWeight: "bold", marginBottom: 12, color: "white" }}>Ready to Own This Build?</h2>
          <p style={{ fontSize: 16, marginBottom: 24, color: "rgba(255,255,255,0.9)", lineHeight: 1.6 }}>
            Get a pre-assembled, tested, and ready-to-use PC that delivers exceptional performance and value.
          </p>
          <button style={{ backgroundColor: "white", color: "#0066ff", padding: "14px 32px", fontSize: 16, fontWeight: "bold", borderRadius: 8, border: "none", cursor: "pointer", transition: "transform 0.2s, box-shadow 0.2s" }} onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 10px 20px rgba(0,0,0,0.2)"; }} onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "none"; }}>
            Inquire About This Build
          </button>
        </div>
      </div>
    </div>
  );
}
