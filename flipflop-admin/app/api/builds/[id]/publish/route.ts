import { NextRequest, NextResponse } from "next/server";

interface PublishRequest {
  target: "ebay" | "flipflop";
  listing: {
    title: string;
    description: string;
    keyFeatures: string[];
    perfectFor: string[];
    warranty: string;
    shipping: string;
  };
}

// Generate eBay-compatible HTML from listing data
function generateEbayHtml(listing: PublishRequest["listing"]): string {
  return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${listing.title}</title>
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

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: buildId } = await params;
    const body: PublishRequest = await request.json();

    if (!body.target || !body.listing) {
      return NextResponse.json(
        { error: "Missing target or listing data" },
        { status: 400 }
      );
    }

    if (body.target === "ebay") {
      // Generate eBay HTML
      const ebayHtml = generateEbayHtml(body.listing);

      // TODO: Integrate with eBay API to create listing
      // For now, we'll return the HTML and a mock eBay URL
      const mockEbayUrl = `https://www.ebay.com/itm/123456789`; // Mock URL

      // Store in database (TODO: implement actual DB save)
      console.log(`[eBay Publish] Build ${buildId}:`, {
        title: body.listing.title,
        htmlLength: ebayHtml.length,
      });

      return NextResponse.json({
        success: true,
        target: "ebay",
        ebayUrl: mockEbayUrl,
        message: "Listing prepared for eBay. Use the eBay API to publish.",
        html: ebayHtml, // Return HTML so frontend can display if needed
      });
    } else if (body.target === "flipflop") {
      // Publish to FlipFlop.shop database
      // TODO: Save to database with full listing data
      console.log(`[FlipFlop Publish] Build ${buildId}:`, {
        title: body.listing.title,
      });

      // Mock response - in reality would save to DB and return the URL
      const mockFlipFlopUrl = `/builds/${buildId}`;

      return NextResponse.json({
        success: true,
        target: "flipflop",
        url: mockFlipFlopUrl,
        message: "Successfully published to FlipFlop.shop",
      });
    } else {
      return NextResponse.json(
        { error: "Invalid target. Must be 'ebay' or 'flipflop'" },
        { status: 400 }
      );
    }
  } catch (error) {
    console.error("Publish error:", error);
    return NextResponse.json(
      { error: "Failed to publish listing" },
      { status: 500 }
    );
  }
}
