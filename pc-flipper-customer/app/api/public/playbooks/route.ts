export async function GET() {
  return Response.json([
    {
      id: 1,
      name: "Gaming Rig",
      slug: "gaming-rig",
      description: "High-end gaming PC build",
      tier_names: { budget: "Budget", mid: "Mid", high: "High" },
      slots: [
        {
          id: 1,
          slot_type: "gpu",
          tier: "mid",
          selected_variant_id: 1,
          display_name: "Graphics Card",
        },
        {
          id: 2,
          slot_type: "cpu",
          tier: "mid",
          selected_variant_id: 1,
          display_name: "Processor",
        },
        {
          id: 3,
          slot_type: "ram",
          tier: "mid",
          selected_variant_id: 1,
          display_name: "Memory",
        },
        {
          id: 4,
          slot_type: "storage",
          tier: "mid",
          selected_variant_id: 1,
          display_name: "Storage",
        },
      ],
    },
  ]);
}
