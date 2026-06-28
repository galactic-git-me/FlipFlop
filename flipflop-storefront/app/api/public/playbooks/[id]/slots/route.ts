export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const params = await context.params;
  
  return Response.json([
    {
      slot_id: 1,
      slot_type: "gpu",
      tier_names: { budget: "Budget", mid: "Mid", high: "High" },
      variants_by_tier: {
        high: [
          { id: 1, title: "RTX 4090", display_price: 1500, gem_score: 100 },
        ],
        mid: [
          { id: 2, title: "RTX 4080", display_price: 1200, gem_score: 85 },
        ],
        budget: [
          { id: 3, title: "RTX 3090 Ti", display_price: 900, gem_score: 70 },
        ],
      },
    },
    {
      slot_id: 2,
      slot_type: "cpu",
      tier_names: { budget: "Budget", mid: "Mid", high: "High" },
      variants_by_tier: {
        high: [
          { id: 4, title: "Intel i9-14900K", display_price: 700, gem_score: 95 },
        ],
        mid: [
          { id: 5, title: "AMD Ryzen 9 7950X3D", display_price: 600, gem_score: 90 },
        ],
        budget: [
          { id: 6, title: "Intel i7-14700K", display_price: 400, gem_score: 75 },
        ],
      },
    },
    {
      slot_id: 3,
      slot_type: "ram",
      tier_names: { budget: "Budget", mid: "Mid", high: "High" },
      variants_by_tier: {
        high: [
          { id: 7, title: "DDR5 64GB RGB", display_price: 400, gem_score: 90 },
        ],
        mid: [
          { id: 8, title: "DDR5 32GB RGB", display_price: 250, gem_score: 80 },
        ],
        budget: [
          { id: 9, title: "DDR5 32GB", display_price: 200, gem_score: 70 },
        ],
      },
    },
    {
      slot_id: 4,
      slot_type: "storage",
      tier_names: { budget: "Budget", mid: "Mid", high: "High" },
      variants_by_tier: {
        high: [
          { id: 10, title: "Samsung 990 Pro 4TB", display_price: 500, gem_score: 95 },
        ],
        mid: [
          { id: 11, title: "Corsair MP600 2TB", display_price: 300, gem_score: 85 },
        ],
        budget: [
          { id: 12, title: "WD Blue 1TB", display_price: 100, gem_score: 60 },
        ],
      },
    },
  ]);
}
