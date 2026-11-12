import { api, apiUrl } from "@/lib/api";

export type ApprovalTab = "images" | "models" | "pricing" | "playbook" | "marketing" | "operations";
export type ApprovalQueue = {
  id: string;
  title: string;
  description: string;
  count: number;
  href: string;
  tab: ApprovalTab;
};
export type ApprovalSnapshot = { queues: ApprovalQueue[]; unavailable: string[]; observedAt: string };

type QueueSpec = Omit<ApprovalQueue, "count"> & { loadCount: () => Promise<number> };
const specs: QueueSpec[] = [
  {
    id: "product-matches", tab: "images", title: "Bestseller product matches",
    description: "Captured Amazon bestseller identities awaiting a product match decision.",
    href: "/pc-builder?tab=images", loadCount: async () => {
      const response = await fetch("/api/curated-builds/bestseller-catalogue", { cache: "no-store" });
      if (!response.ok) throw new Error(`Bestseller queue returned ${response.status}`);
      const data = await response.json();
      return (Array.isArray(data.items) ? data.items : []).filter((item: { review_status?: string }) => item.review_status === "pending").length;
    },
  },
  {
    id: "catalogue-photos", tab: "images", title: "Catalogue photos",
    description: "Usable captured product photos whose main image has not been approved.",
    href: "/catalogue/3d-assets", loadCount: async () => {
      const response = await fetch("/api/assets-3d/catalogue/photo-queue", { cache: "no-store" });
      if (!response.ok) throw new Error(`Photo queue returned ${response.status}`);
      const rows: Array<{ listing_id: number; category: string; main_photo_approved?: boolean; main_photo_url?: string | null; listing_image_urls?: string[] }> = await response.json();
      const unique = new Map<string, typeof rows[number]>();
      for (const row of rows) {
        const key = `${row.listing_id}:${row.category}`;
        if (!unique.has(key)) unique.set(key, row);
      }
      return [...unique.values()].filter(row => !row.main_photo_approved && Boolean(row.main_photo_url || row.listing_image_urls?.length)).length;
    },
  },
  {
    id: "3d-models", tab: "models", title: "3D model candidates",
    description: "Uploaded models without a review decision, including variants and cases.",
    href: "/components-3d-review", loadCount: async () => {
      const response = await fetch("/api/assets-3d", { cache: "no-store" });
      if (!response.ok) throw new Error(`3D model queue returned ${response.status}`);
      const rows = await response.json();
      return (Array.isArray(rows) ? rows : []).filter((asset: { glb_ref?: string | null; review_decision?: string | null; is_active?: boolean }) => Boolean(asset.glb_ref) && !asset.review_decision && !asset.is_active).length;
    },
  },
  {
    id: "curated-builds", tab: "pricing", title: "Curated build proposals",
    description: "Current Playbook build proposals awaiting review, with price and delivery-mode evidence.",
    href: "/playbooks/commercial?area=builds", loadCount: async () => (await api.commercialReadiness.proposals()).items.length,
  },
  {
    id: "legacy-playbook", tab: "pricing", title: "Playbook proposals",
    description: "Older Playbook proposals awaiting an explicit approve or reject decision.",
    href: "/playbooks?tab=proposals", loadCount: async () => (await api.playbooks.proposals.list("pending")).length,
  },
  {
    id: "market-pricing", tab: "pricing", title: "Market price evidence",
    description: "Collected build-market comparisons that have not been accepted or rejected, or have gone stale.",
    href: "/pc-builder?tab=playbook&slice=pricing", loadCount: async () => {
      const book = await api.commercialReadiness.book();
      return book.cells.filter(cell => cell.market_review_status === "pending" || cell.market_review_status === "stale").length;
    },
  },
  {
    id: "configurations", tab: "pricing", title: "Customer build configurations",
    description: "Exact customer configurations still awaiting policy and price review.",
    href: "/playbooks/commercial?area=configurations", loadCount: async () => {
      const rows = (await api.commercialReadiness.configurations()).items;
      return rows.filter(row => !row.checkout_enabled).length;
    },
  },
  {
    id: "supplier-licences", tab: "playbook", title: "Software licence sources",
    description: "Supplier licence claims awaiting source and terms review.",
    href: "/playbooks/commercial?area=software", loadCount: async () => {
      const rows = (await api.commercialReadiness.supplierLicences()).items;
      return rows.filter(row => !row.licence_source_reviewed).length;
    },
  },
  {
    id: "engineering", tab: "playbook", title: "Motherboard engineering evidence",
    description: "Captured motherboard specifications awaiting engineering review.",
    href: "/playbooks/commercial?area=compatibility", loadCount: async () => (await api.commercialReadiness.engineeringSuggestions()).items.length,
  },
  {
    id: "product-engineering", tab: "playbook", title: "Product engineering evidence",
    description: "Captured product specifications ready for an explicit approval decision.",
    href: "/playbooks/commercial?area=compatibility", loadCount: async () => {
      const rows = (await api.commercialReadiness.productEngineeringSuggestions()).items;
      return rows.filter(row => row.status === "review_ready").length;
    },
  },
  {
    id: "catalogue-products", tab: "playbook", title: "Catalogue products",
    description: "Catalogue variants waiting for approval before they can be used in builds.",
    href: "/catalogue?scope=curated&status=pending_review", loadCount: async () => (await api.catalogue.reviewQueue()).length,
  },
  {
    id: "linked-suppliers", tab: "playbook", title: "Linked supplier listings",
    description: "Active listings assigned to build cells that still need to be added to the Curated Catalogue.",
    href: "/pc-builder?tab=playbook&tool=inventory", loadCount: async () => {
      const response = await fetch("/api/curated-builds", { cache: "no-store" });
      if (!response.ok) throw new Error(`Curated build queue returned ${response.status}`);
      const data = await response.json();
      const seen = new Set<number>();
      for (const segment of Array.isArray(data.segments) ? data.segments : []) {
        for (const component of Object.values(segment.component_details ?? {}) as Array<{ id: number; curated_for_builds?: boolean; status?: string } | null>) {
          if (component && !component.curated_for_builds && component.status === "active") seen.add(component.id);
        }
      }
      return seen.size;
    },
  },
  {
    id: "social-posts", tab: "marketing", title: "Social posts",
    description: "Validated social posts awaiting approval before publishing.",
    href: "/advertising-growth", loadCount: async () => {
      const response = await fetch(apiUrl("/growth/social/posts"), { cache: "no-store" });
      if (!response.ok) throw new Error(`Social approval queue returned ${response.status}`);
      const data = await response.json();
      return (Array.isArray(data.items) ? data.items : []).filter((post: { status?: string }) => post.status === "review").length;
    },
  },
  {
    id: "getting-ready-packages", tab: "operations", title: "Getting-ready packages",
    description: "Generated customer setup packages marked ready for admin review.",
    href: "/dispatch-zone?tab=getting-ready", loadCount: async () => {
      const rows = await api.dispatch.list();
      return rows.filter(row => row.getting_started?.status === "awaiting_admin_review"
        || (row.getting_started?.manifest as Record<string, unknown> | null | undefined)?.status === "ready_for_admin_review").length;
    },
  },
  {
    id: "dispatch-evidence", tab: "operations", title: "Dispatch evidence",
    description: "Uploaded build and packaging photos awaiting operator approval before handover.",
    href: "/dispatch-zone?tab=evidence", loadCount: async () => {
      const rows = await api.dispatch.list();
      return rows.reduce((count, row) => count + (row.getting_started?.shipment_evidence ?? []).filter(item => !item.review_status || item.review_status === "needs_review").length, 0);
    },
  },
];

let cached: { value: ApprovalSnapshot; at: number } | null = null;
let inFlight: Promise<ApprovalSnapshot> | null = null;

export function getApprovalSnapshot(force = false): Promise<ApprovalSnapshot> {
  if (!force && cached && Date.now() - cached.at < 20_000) return Promise.resolve(cached.value);
  if (!force && inFlight) return inFlight;
  inFlight = Promise.all(specs.map(async ({ loadCount, ...queue }) => ({ queue, result: await loadCount().then(count => ({ count })).catch(error => ({ error: error instanceof Error ? error.message : "Unable to load queue" })) })))
    .then(results => {
      const unavailable: string[] = [];
      const queues = results.map(({ queue, result }) => {
        if ("error" in result) { unavailable.push(queue.title); return { ...queue, count: 0 }; }
        return { ...queue, count: result.count };
      });
      const value = { queues, unavailable, observedAt: new Date().toISOString() };
      cached = { value, at: Date.now() };
      return value;
    })
    .finally(() => { inFlight = null; });
  return inFlight;
}
