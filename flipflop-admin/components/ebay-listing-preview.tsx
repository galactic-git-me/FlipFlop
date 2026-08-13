"use client";
/* eslint-disable @next/next/no-img-element */

import { Play } from "lucide-react";

interface ListingData {
  title: string;
  description: string;
  keyFeatures: string[];
  perfectFor: string[];
  warranty: string;
  shipping: string;
}

interface EbayListingPreviewProps {
  listing: ListingData;
  heroVideoUrl?: string;
  heroImageUrl?: string;
}

export function EbayListingPreview({ listing, heroVideoUrl, heroImageUrl }: EbayListingPreviewProps) {
  return (
    <div style={{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", backgroundColor: "#f8fafc", color: "#1e293b", padding: "40px 20px" }}>
      {/* FlipFlop Header */}
      <div style={{ maxWidth: "100%", marginBottom: 30, paddingBottom: 30, borderBottom: "2px solid #0066ff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
          <div style={{ width: 60, height: 60, backgroundColor: "#0066ff", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #0066ff 0%, #ff6600 100%)" }}>
            <span style={{ color: "white", fontSize: 32, fontWeight: "bold" }}>F</span>
          </div>
          <div>
            <div style={{ fontSize: 20, fontWeight: "bold", color: "#000" }}>FlipFlop</div>
            <div style={{ fontSize: 12, color: "#666" }}>Beautiful Machines Built to Be Admired</div>
          </div>
        </div>
      </div>

      {/* Hero Section */}
      {(heroVideoUrl || heroImageUrl) && (
        <div style={{ marginBottom: 30, borderRadius: 12, overflow: "hidden", boxShadow: "0 10px 30px rgba(0,0,0,0.15)", backgroundColor: "#000", position: "relative", aspectRatio: "16/9" }}>
          {heroVideoUrl ? (
            <video
              src={heroVideoUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
              controls
            />
          ) : heroImageUrl ? (
            <img
              src={heroImageUrl}
              alt="Build"
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#1a1a1a" }}>
              <div style={{ textAlign: "center", color: "#666" }}>
                <Play size={48} style={{ margin: "0 auto 16px" }} />
                <div>Video Preview</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Title */}
      <h1 style={{ fontSize: 32, fontWeight: "bold", marginBottom: 24, color: "#000", lineHeight: 1.3 }}>{listing.title}</h1>

      {/* Description Section */}
      <div style={{ marginBottom: 30, padding: 20, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0" }}>
        <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 16, color: "#000" }}>About This Build</h2>
        <p style={{ fontSize: 15, lineHeight: 1.8, color: "#444", whiteSpace: "pre-wrap", marginBottom: 20 }}>{listing.description}</p>
      </div>

      {/* Key Features */}
      <div style={{ marginBottom: 30, padding: 20, backgroundColor: "#f0f9ff", borderRadius: 12, border: "2px solid #0066ff" }}>
        <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 16, color: "#000" }}>✨ Key Features</h2>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {listing.keyFeatures.map((feature, idx) => (
            <li key={idx} style={{ fontSize: 14, lineHeight: 1.7, color: "#333", marginBottom: 12, paddingLeft: 24, position: "relative" }}>
              <span style={{ position: "absolute", left: 0, color: "#0066ff", fontWeight: "bold" }}>▸</span>
              <span dangerouslySetInnerHTML={{ __html: feature.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>") }} />
            </li>
          ))}
        </ul>
      </div>

      {/* Perfect For */}
      {listing.perfectFor && listing.perfectFor.length > 0 && (
        <div style={{ marginBottom: 30, padding: 20, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0" }}>
          <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 16, color: "#000" }}>🎮 Perfect For</h2>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            {listing.perfectFor.map((item, idx) => (
              <li key={idx} style={{ fontSize: 14, color: "#333", padding: 12, backgroundColor: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                • {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warranty Section */}
      <div style={{ marginBottom: 30, padding: 20, backgroundColor: "#fff9f0", borderRadius: 12, border: "2px solid #ff6600" }}>
        <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 12, color: "#000", display: "flex", alignItems: "center", gap: 8 }}>
          🛡️ Warranty & Returns
        </h2>
        <p style={{ fontSize: 14, lineHeight: 1.7, color: "#333", margin: 0 }}>{listing.warranty}</p>
      </div>

      {/* Shipping Section */}
      <div style={{ marginBottom: 30, padding: 20, backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0" }}>
        <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 12, color: "#000", display: "flex", alignItems: "center", gap: 8 }}>
          📦 Shipping
        </h2>
        <p style={{ fontSize: 14, lineHeight: 1.7, color: "#333", margin: 0 }}>{listing.shipping}</p>
      </div>

      {/* Trust Section */}
      <div style={{ padding: 24, backgroundColor: "linear-gradient(135deg, #0066ff 0%, #ff6600 100%)", borderRadius: 12, color: "white", textAlign: "center" }}>
        <h2 style={{ fontSize: 20, fontWeight: "bold", marginBottom: 12, color: "white" }}>💯 Why Buy From FlipFlop?</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 16, marginTop: 20 }}>
          <div style={{ padding: 16, backgroundColor: "rgba(255,255,255,0.1)", borderRadius: 8 }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>✓</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Fully Tested</div>
            <div style={{ fontSize: 12, opacity: 0.9 }}>Every build verified</div>
          </div>
          <div style={{ padding: 16, backgroundColor: "rgba(255,255,255,0.1)", borderRadius: 8 }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⚡</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Expert Built</div>
            <div style={{ fontSize: 12, opacity: 0.9 }}>20+ years experience</div>
          </div>
          <div style={{ padding: 16, backgroundColor: "rgba(255,255,255,0.1)", borderRadius: 8 }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>💎</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Great Value</div>
            <div style={{ fontSize: 12, opacity: 0.9 }}>Transparent pricing</div>
          </div>
        </div>
      </div>

      {/* eBay-Safe Footer */}
      <div style={{ marginTop: 30, paddingTop: 30, borderTop: "2px solid #e2e8f0", textAlign: "center" }}>
        <p style={{ fontSize: 12, color: "#999", margin: 0 }}>
          FlipFlop • Professional PC Builds • Every machine is inspected and tested before shipment.
        </p>
      </div>
    </div>
  );
}
