import type { ManualBuild, ManualBuildSummary } from "@/lib/api";

export type CrossListingChannel =
  | "ebay_uk"
  | "flipflop_shop"
  | "onbuy"
  | "amazon"
  | "facebook_catalog"
  | "vinted";

export type CrossListingStatus =
  | "draft"
  | "queued"
  | "validating"
  | "ready"
  | "publishing"
  | "published"
  | "updated"
  | "manual_action_required"
  | "failed"
  | "cancelled";

export type SourcePlatform = "ebay_uk" | "flipflop_shop";

export interface CanonicalListing {
  productId: string;
  sku: string;
  title: string;
  description: string;
  bulletPoints: string[];
  faqs: Array<{ question: string; answer: string }>;
  price: number | null;
  currency: "GBP";
  quantity: number;
  condition: string;
  images: Array<{ url: string; alt: string; order: number }>;
  specifications: Record<string, string>;
  warranty: string;
  shipping: string;
  returnPolicy: string;
  sourceBuildId: number;
}

export interface CrossListingSource {
  id: string;
  source: SourcePlatform;
  externalId: string;
  canonicalProductId: string;
  buildId: number;
  title: string;
  imageUrl: string | null;
  price: number | null;
  currency: "GBP";
  quantity: number;
  condition: string;
  status: "live" | "draft" | "sold" | "ended" | "unavailable" | "failed";
  url: string | null;
  updatedAt: string;
  listing: CanonicalListing;
}

export interface ChannelCapability {
  channel: CrossListingChannel;
  label: string;
  mode: "api" | "manual" | "not_connected" | "requires_approval";
  connected: boolean;
  canPublish: boolean;
  canUpdate: boolean;
  canEnd: boolean;
  note: string;
  officialReference: string;
}

export interface CrossListingJobResult {
  channel: CrossListingChannel;
  buildId: number;
  status: CrossListingStatus;
  message: string;
  externalId?: string;
  url?: string;
}

export interface CrossListingSourceResponse {
  items: CrossListingSource[];
  refreshedAt: string;
  warnings: string[];
}

const sourceStatus = (build: ManualBuild, source: SourcePlatform): CrossListingSource["status"] => {
  if (build.status === "sold") return "sold";
  if (source === "ebay_uk") {
    if (build.ebay_listing_status === "active" || build.ebay_live) return "live";
    if (build.ebay_listing_status === "draft") return "draft";
    if (build.ebay_listing_status === "ended") return "ended";
    return "unavailable";
  }
  return build.storefront_product_id ? (build.storefront_live === false ? "ended" : "live") : "unavailable";
};

function specifications(build: ManualBuild): Record<string, string> {
  const result: Record<string, string> = {};
  for (const component of build.components ?? []) {
    if (component.name) result[component.slot] = component.name;
  }
  return result;
}

export function canonicalFromBuild(build: ManualBuild): CanonicalListing {
  const photos = (build.photos ?? []).filter((photo) => photo.kind === "photo").map((photo, index) => ({
    url: photo.url,
    alt: `${build.name} product photo ${index + 1}`,
    order: index,
  }));
  return {
    productId: String(build.id),
    sku: `FF-BUILD-${build.id}`,
    title: build.generated_title || build.name,
    description: build.generated_description || "Listing copy has not been generated yet.",
    bulletPoints: Object.values(build.generated_aspects ?? {}).flat().slice(0, 8),
    faqs: [],
    price: build.ebay_price ?? build.last_evaluation?.mid ?? null,
    currency: "GBP",
    quantity: build.status === "sold" ? 0 : 1,
    condition: build.ebay_condition || "Used",
    images: photos,
    specifications: specifications(build),
    warranty: "See the saved build warranty and returns policy before publishing.",
    shipping: build.shipping_method || "Configure shipping before publishing.",
    returnPolicy: `${build.return_days ?? 30} day returns`,
    sourceBuildId: build.id,
  };
}

export function sourcesFromBuild(build: ManualBuild): CrossListingSource[] {
  const listing = canonicalFromBuild(build);
  const items: CrossListingSource[] = [];
  if (build.ebay_listing_id || build.ebay_listing_status !== "never_listed") {
    items.push({
      id: `ebay_uk:${build.id}`,
      source: "ebay_uk",
      externalId: build.ebay_listing_id || "not-created",
      canonicalProductId: String(build.id),
      buildId: build.id,
      title: listing.title,
      imageUrl: listing.images[0]?.url ?? build.hero_photo_url,
      price: listing.price,
      currency: "GBP",
      quantity: listing.quantity,
      condition: listing.condition,
      status: sourceStatus(build, "ebay_uk"),
      url: build.ebay_listing_url,
      updatedAt: build.updated_at,
      listing,
    });
  }
  if (build.storefront_product_id) {
    items.push({
      id: `flipflop_shop:${build.id}`,
      source: "flipflop_shop",
      externalId: String(build.storefront_product_id),
      canonicalProductId: String(build.id),
      buildId: build.id,
      title: listing.title,
      imageUrl: listing.images[0]?.url ?? build.hero_photo_url,
      price: listing.price,
      currency: "GBP",
      quantity: listing.quantity,
      condition: listing.condition,
      status: sourceStatus(build, "flipflop_shop"),
      url: null,
      updatedAt: build.updated_at,
      listing,
    });
  }
  return items;
}

export function capabilities(ebayConnected: boolean): ChannelCapability[] {
  return [
    { channel: "ebay_uk", label: "eBay UK", mode: ebayConnected ? "api" : "not_connected", connected: ebayConnected, canPublish: ebayConnected, canUpdate: ebayConnected, canEnd: ebayConnected, note: ebayConnected ? "Uses the existing seller OAuth and manual-build eBay operations." : "Connect the existing eBay seller account in Settings.", officialReference: "https://developer.ebay.com/api-docs/sell/inventory/overview.html" },
    { channel: "flipflop_shop", label: "FlipFlop.shop", mode: "api", connected: true, canPublish: true, canUpdate: true, canEnd: false, note: "Reuses the canonical storefront product; duplicate products are not created here.", officialReference: "Internal storefront API" },
    { channel: "onbuy", label: "OnBuy", mode: "manual", connected: false, canPublish: false, canUpdate: false, canEnd: false, note: "Seller API/feed onboarding is not configured in this app. Manual listing pack only.", officialReference: "https://www.onbuy.com/gb/sell/" },
    { channel: "amazon", label: "Amazon", mode: "requires_approval", connected: false, canPublish: false, canUpdate: false, canEnd: false, note: "SP-API requires seller authorization, Product Listing role, marketplace/category requirements and identifiers.", officialReference: "https://developer-docs.amazon.com/sp-api/docs/manage-product-listings-guide" },
    { channel: "facebook_catalog", label: "Facebook catalog", mode: "manual", connected: false, canPublish: false, canUpdate: false, canEnd: false, note: "Catalog/feed route must be configured; personal Marketplace automation is not supported.", officialReference: "https://www.facebook.com/business/help/" },
    { channel: "vinted", label: "Vinted", mode: "manual", connected: false, canPublish: false, canUpdate: false, canEnd: false, note: "No approved seller integration is configured. Manual-assist export only; no consumer-account automation.", officialReference: "https://www.vinted.co.uk/help" },
  ];
}

export function getBuildFromSummary(summary: ManualBuildSummary): ManualBuild {
  return summary as ManualBuild;
}
