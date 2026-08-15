"use client";
/* eslint-disable @next/next/no-img-element */

import { X, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import DOMPurify from "dompurify";

interface EbayListingHTMLPreviewProps {
  title: string;
  description: string;
  images: string[];
  price?: number;
  onClose?: () => void;
  isModal?: boolean;
}

const sanitizeHtml = (html: string) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "h1", "h2", "h3", "h4", "h5", "h6",
      "p", "ul", "ol", "li", "blockquote",
      "strong", "b", "em", "i", "u", "a",
      "br", "hr", "span", "div", "img", "table", "tr", "td", "th", "tbody", "thead", "section", "article",
    ],
    ALLOWED_ATTR: ["style", "href", "target", "rel", "src", "alt", "class", "id", "width", "height"],
    ALLOW_DATA_ATTR: false,
    ALLOW_UNKNOWN_PROTOCOLS: false,
  });

export function EbayListingHTMLPreview({
  title,
  description,
  images,
  price,
  onClose,
  isModal = false,
}: EbayListingHTMLPreviewProps) {
  const [selectedImageIdx, setSelectedImageIdx] = useState(0);

  const content = (
    <div style={{ fontFamily: "'Helvetica Neue', Arial, sans-serif", backgroundColor: "#fff", color: "#333" }}>
      {/* eBay Header Bar */}
      <div style={{ backgroundColor: "#e53238", padding: "8px 20px", color: "white", fontSize: 12 }}>
        <span>eBay › </span>
        <span>Electronics › Computers & Tablets › Desktop Computers</span>
      </div>

      {/* Main Content Area */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "20px" }}>
        {/* Title */}
        <h1 style={{ fontSize: 24, fontWeight: "bold", marginBottom: 16, color: "#000", lineHeight: 1.3 }}>
          {title}
        </h1>

        {/* Two-Column Layout */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 30, marginBottom: 40 }}>
          {/* Left Column - Images */}
          <div>
            {images.length > 0 && (
              <>
                {/* Main Image */}
                <div
                  style={{
                    backgroundColor: "#f5f5f5",
                    border: "1px solid #ddd",
                    borderRadius: 4,
                    marginBottom: 12,
                    position: "relative",
                    height: 500,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    overflow: "hidden",
                  }}
                >
                  <img
                    src={images[selectedImageIdx]}
                    alt="Product"
                    style={{
                      maxWidth: "100%",
                      maxHeight: "100%",
                      objectFit: "contain",
                    }}
                  />
                  {images.length > 1 && (
                    <>
                      <button
                        onClick={() => setSelectedImageIdx((i) => (i - 1 + images.length) % images.length)}
                        style={{
                          position: "absolute",
                          left: 10,
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "rgba(0,0,0,0.5)",
                          color: "white",
                          border: "none",
                          padding: 8,
                          cursor: "pointer",
                          borderRadius: 4,
                        }}
                      >
                        <ChevronLeft size={20} />
                      </button>
                      <button
                        onClick={() => setSelectedImageIdx((i) => (i + 1) % images.length)}
                        style={{
                          position: "absolute",
                          right: 10,
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "rgba(0,0,0,0.5)",
                          color: "white",
                          border: "none",
                          padding: 8,
                          cursor: "pointer",
                          borderRadius: 4,
                        }}
                      >
                        <ChevronRight size={20} />
                      </button>
                    </>
                  )}
                </div>

                {/* Thumbnail Strip */}
                {images.length > 1 && (
                  <div style={{ display: "flex", gap: 6, overflowX: "auto" }}>
                    {images.slice(0, 10).map((img, idx) => (
                      <img
                        key={idx}
                        src={img}
                        alt={`Thumbnail ${idx + 1}`}
                        onClick={() => setSelectedImageIdx(idx)}
                        style={{
                          width: 80,
                          height: 80,
                          objectFit: "cover",
                          border: selectedImageIdx === idx ? "3px solid #e53238" : "1px solid #ddd",
                          cursor: "pointer",
                          flexShrink: 0,
                          borderRadius: 4,
                        }}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Right Column - Purchase Info */}
          <div>
            {/* Price Section */}
            <div style={{ backgroundColor: "#f5f5f5", padding: 12, borderRadius: 4, marginBottom: 16 }}>
              {price && (
                <>
                  <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>Price</div>
                  <div style={{ fontSize: 32, fontWeight: "bold", color: "#000", marginBottom: 12 }}>
                    £{price.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>Condition</div>
                  <div style={{ fontSize: 14, marginBottom: 16 }}>Used - Excellent</div>
                  <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>Shipping</div>
                  <div style={{ fontSize: 14, marginBottom: 16 }}>Free tracked shipping</div>
                </>
              )}
            </div>

            {/* Action Buttons */}
            <button
              style={{
                width: "100%",
                padding: "10px 0",
                backgroundColor: "#e53238",
                color: "white",
                border: "none",
                borderRadius: 4,
                fontSize: 16,
                fontWeight: "bold",
                cursor: "pointer",
                marginBottom: 8,
              }}
            >
              Buy It Now
            </button>
            <button
              style={{
                width: "100%",
                padding: "10px 0",
                backgroundColor: "#fff",
                color: "#333",
                border: "1px solid #ddd",
                borderRadius: 4,
                fontSize: 14,
                cursor: "pointer",
                marginBottom: 20,
              }}
            >
              Make an Offer
            </button>

            {/* Item Info */}
            <div style={{ borderTop: "1px solid #ddd", paddingTop: 12 }}>
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: "#666", marginBottom: 2 }}>SELLER INFORMATION</div>
                <div style={{ fontSize: 13, color: "#0066cc", cursor: "pointer", textDecoration: "underline" }}>
                  flipflop_gamer_shop
                </div>
                <div style={{ fontSize: 11, color: "#666", marginTop: 4 }}>100% Positive feedback</div>
              </div>
            </div>

            {/* Trust Badge */}
            <div style={{ backgroundColor: "#e8f4f8", padding: 12, borderRadius: 4, marginTop: 16, fontSize: 11 }}>
              <div style={{ fontWeight: "bold", marginBottom: 6 }}>✓ Shop with confidence</div>
              <div style={{ lineHeight: 1.6 }}>eBay Money Back Guarantee. Every item 100% inspected & tested before dispatch.</div>
            </div>
          </div>
        </div>

        {/* ITEM SPECIFICS SECTION */}
        <div style={{ borderTop: "1px solid #ddd", paddingTop: 20, marginBottom: 40 }}>
          <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 16 }}>Item specifics</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", width: "30%", fontSize: 13 }}>Brand</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>FlipFlop</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>Type</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>Desktop Computer</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>Condition</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>Used</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>Processor</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>AMD Ryzen 7 7800X3D</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>Graphics Processing Type</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>Dedicated</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>RAM Size</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>32GB</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>Storage Type</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>SSD</td>
              </tr>
              <tr style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "8px 0", fontWeight: "bold", fontSize: 13 }}>Operating System</td>
                <td style={{ padding: "8px 0", fontSize: 13 }}>Windows 11 Pro</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* FULL WIDTH DESCRIPTION - YOUR AI-GENERATED HTML */}
      </div>

      {/* Full-width description container - no interference from parent styling */}
      <div
        style={{
          width: "100%",
          backgroundColor: "#fafafa",
          padding: "40px 20px",
          marginTop: 40,
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <h2 style={{ fontSize: 18, fontWeight: "bold", marginBottom: 20, color: "#000" }}>Item description from the seller</h2>
          {/* Render ONLY your AI-generated HTML - no CSS interference */}
          <div
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(description),
            }}
          />
        </div>
      </div>

      {/* Footer */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 20px", borderTop: "1px solid #ddd", fontSize: 12, color: "#666" }}>
        <div>About this seller • Contact seller • Visit seller's store • See other items</div>
        <div style={{ marginTop: 12 }}>This is a preview. Actual eBay purchase would happen on eBay.com</div>
      </div>
    </div>
  );

  if (isModal) {
    return (
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0, 0, 0, 0.7)",
          zIndex: 50,
          overflowY: "auto",
        }}
      >
        <div style={{ position: "relative", backgroundColor: "#fff" }}>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                position: "sticky",
                top: 0,
                right: 0,
                float: "right",
                zIndex: 10,
                backgroundColor: "#fff",
                border: "1px solid #ddd",
                borderRadius: 4,
                padding: "8px 12px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                margin: 12,
              }}
            >
              <X size={20} />
              Close Preview
            </button>
          )}
          {content}
        </div>
      </div>
    );
  }

  return content;
}
