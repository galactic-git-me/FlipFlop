export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const params = await context.params;
  
  return Response.json([
    {
      id: 1,
      slot_type: "gpu",
      display_name: "Graphics Card",
      tier: "mid",
      variants: [
        { id: 1, name: "RTX 4090", tier: "high", display_price: 1500, gem_score: 100, passmark: 50000 },
        { id: 2, name: "RTX 4080", tier: "mid", display_price: 1200, gem_score: 85, passmark: 45000 },
        { id: 3, name: "RTX 3090 Ti", tier: "budget", display_price: 900, gem_score: 70, passmark: 40000 },
      ],
    },
    {
      id: 2,
      slot_type: "cpu",
      display_name: "Processor",
      tier: "mid",
      variants: [
        { id: 1, name: "Intel i9-14900K", tier: "high", display_price: 700, gem_score: 95, passmark: 60000 },
        { id: 2, name: "AMD Ryzen 9 7950X3D", tier: "mid", display_price: 600, gem_score: 90, passmark: 58000 },
        { id: 3, name: "Intel i7-14700K", tier: "budget", display_price: 400, gem_score: 75, passmark: 50000 },
      ],
    },
    {
      id: 3,
      slot_type: "ram",
      display_name: "Memory",
      tier: "mid",
      variants: [
        { id: 1, name: "DDR5 64GB RGB", tier: "high", display_price: 400, gem_score: 90, passmark: 0 },
        { id: 2, name: "DDR5 32GB RGB", tier: "mid", display_price: 250, gem_score: 80, passmark: 0 },
        { id: 3, name: "DDR5 32GB", tier: "budget", display_price: 200, gem_score: 70, passmark: 0 },
      ],
    },
    {
      id: 4,
      slot_type: "storage",
      display_name: "Storage",
      tier: "mid",
      variants: [
        { id: 1, name: "Samsung 990 Pro 4TB", tier: "high", display_price: 500, gem_score: 95, passmark: 0 },
        { id: 2, name: "Corsair MP600 2TB", tier: "mid", display_price: 300, gem_score: 85, passmark: 0 },
        { id: 3, name: "WD Blue 1TB", tier: "budget", display_price: 100, gem_score: 60, passmark: 0 },
      ],
    },
  ]);
}
