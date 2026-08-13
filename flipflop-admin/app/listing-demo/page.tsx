"use client";

import { BuildListingTemplate } from "@/components/build-listing-template";

const DEMO_BUILD = {
  buildName: "Gaming Beast Pro - RTX 4070 Super",
  totalCost: 1250.50,
  components: [
    { slot: "cpu", name: "Intel Core i7-14700K", price_paid: 350, market_price_avg: 420 },
    { slot: "motherboard", name: "ASUS ROG STRIX Z790-E Gaming WiFi", price_paid: 280, market_price_avg: 350 },
    { slot: "ram", name: "G.SKILL Trident Z5 RGB 32GB DDR5-6000", price_paid: 180, market_price_avg: 220 },
    { slot: "ssd", name: "Samsung 990 Pro 2TB NVMe SSD", price_paid: 150, market_price_avg: 180 },
    { slot: "gpu", name: "NVIDIA RTX 4070 Super 12GB", price_paid: 500, market_price_avg: 580 },
    { slot: "psu", name: "Corsair RM1000x 1000W Gold Modular", price_paid: 180, market_price_avg: 210 },
    { slot: "cooler", name: "Noctua NH-D15S Dual Tower Air Cooler", price_paid: 90, market_price_avg: 110 },
    { slot: "case", name: "Lian Li LANCOOL 205M Mesh Mid-Tower", price_paid: 65, market_price_avg: 85 },
  ],
  totalMarketValue: 2155,
  profitPotential: 904.50,
  dealScore: 8.7,
  description: "High-end gaming PC featuring a powerhouse i7-14700K paired with an RTX 4070 Super. Built for 1440p ultra gaming, streaming, and 3D rendering. All components tested and working perfectly."
};

export default function ListingDemoPage() {
  return (
    <div style={{ background: "white" }}>
      <BuildListingTemplate
        buildName={DEMO_BUILD.buildName}
        totalCost={DEMO_BUILD.totalCost}
        components={DEMO_BUILD.components}
        totalMarketValue={DEMO_BUILD.totalMarketValue}
        profitPotential={DEMO_BUILD.profitPotential}
        dealScore={DEMO_BUILD.dealScore}
        description={DEMO_BUILD.description}
      />
    </div>
  );
}
