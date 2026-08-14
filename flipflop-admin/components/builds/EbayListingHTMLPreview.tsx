"use client";
/* eslint-disable @next/next/no-img-element */

import { X } from "lucide-react";
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
      "br", "hr", "span", "div", "img", "table", "tr", "td", "th", "tbody", "thead",
    ],
    ALLOWED_ATTR: ["style", "href", "target", "rel", "src", "alt", "class"],
  });

export function EbayListingHTMLPreview({
  title,
  description,
  images,
  price,
  onClose,
  isModal = false,
}: EbayListingHTMLPreviewProps) {
  const content = (
    <div
      style={{
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        backgroundColor: "#f8fafc",
        color: "#1e293b",
        padding: isModal ? "0" : "40px 20px",
      }}
    >
      {/* eBay-style listing header */}
      <div style={{ maxWidth: "900px", margin: "0 auto" }}>
        {/* Title */}
        <div style={{ marginBottom: 24 }}>
          <h1
            style={{
              fontSize: 28,
              fontWeight: "bold",
              color: "#000",
              lineHeight: 1.3,
              margin: 0,
            }}
          >
            {title}
          </h1>
        </div>

        {/* Price bar */}
        {price && (
          <div
            style={{
              marginBottom: 24,
              padding: "16px 20px",
              backgroundColor: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ fontSize: 12, color: "#666" }}>Price</div>
              <div
                style={{
                  fontSize: 28,
                  fontWeight: "bold",
                  color: "#28A745",
                }}
              >
                £{price.toFixed(2)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 12, color: "#666" }}>Condition</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#000" }}>
                Used - Excellent
              </div>
            </div>
          </div>
        )}

        {/* Images section */}
        {images.length > 0 && (
          <div style={{ marginBottom: 30 }}>
            {/* Main image */}
            <div
              style={{
                marginBottom: 16,
                borderRadius: 8,
                overflow: "hidden",
                backgroundColor: "#fff",
                border: "1px solid #e2e8f0",
              }}
            >
              <img
                src={images[0]}
                alt="Product"
                style={{
                  width: "100%",
                  height: "auto",
                  maxHeight: "500px",
                  objectFit: "contain",
                  display: "block",
                }}
              />
            </div>

            {/* Thumbnail strip */}
            {images.length > 1 && (
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  overflowX: "auto",
                  paddingBottom: 8,
                }}
              >
                {images.slice(0, 5).map((img, idx) => (
                  <img
                    key={idx}
                    src={img}
                    alt={`Thumbnail ${idx + 1}`}
                    style={{
                      width: 80,
                      height: 80,
                      objectFit: "cover",
                      borderRadius: 4,
                      border: "2px solid #e2e8f0",
                      cursor: "pointer",
                      flexShrink: 0,
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Generated HTML Description */}
        <div
          style={{
            marginBottom: 30,
            backgroundColor: "#fff",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            padding: 20,
          }}
        >
          {/* Apply eBay-style prose typography */}
          <div
            style={{
              fontSize: 14,
              lineHeight: 1.7,
              color: "#333",
            }}
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(description),
            }}
          />
        </div>

        {/* eBay purchase section at bottom */}
        <div
          style={{
            marginBottom: 30,
            padding: 20,
            backgroundColor: "#fff",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            textAlign: "center",
          }}
        >
          <button
            style={{
              backgroundColor: "#E53238",
              color: "white",
              padding: "12px 40px",
              fontSize: 16,
              fontWeight: "bold",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              marginBottom: 12,
            }}
          >
            Buy It Now
          </button>
          <div style={{ fontSize: 12, color: "#666" }}>
            This is a preview. Actual eBay purchase would happen on eBay.com
          </div>
        </div>
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
          backgroundColor: "rgba(0, 0, 0, 0.5)",
          zIndex: 50,
          overflowY: "auto",
        }}
      >
        <div
          style={{
            position: "relative",
            backgroundColor: "#f8fafc",
            maxWidth: "1000px",
            margin: "20px auto",
            borderRadius: 12,
          }}
        >
          {onClose && (
            <button
              onClick={onClose}
              style={{
                position: "absolute",
                top: 16,
                right: 16,
                zIndex: 10,
                backgroundColor: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                padding: "8px 12px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <X size={20} />
              Close
            </button>
          )}
          <div style={{ padding: "40px 20px" }}>{content}</div>
        </div>
      </div>
    );
  }

  return content;
}
