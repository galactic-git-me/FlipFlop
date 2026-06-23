# Customer Storefront Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pc-flipper-customer/` — a public Next.js 14 storefront where customers browse FlipFlop playbooks, configure a made-to-order PC build, and proceed to checkout.

**Architecture:** New Next.js 14 App Router project at `pc-flipper-customer/` in the same monorepo. Server Components fetch catalogue data from the existing `/api/public/*` endpoints (proxied to FlipFlop backend). Interactive configurator state (tier selection, slot swaps, case pick, fast-track toggle) lives in a single Client Component. Checkout is stubbed — wired to `/api/orders/checkout` which Subsystem 2 delivers.

**Tech Stack:** Next.js 14 / TypeScript / Tailwind CSS. No component library — plain Tailwind with design tokens from Google Stitch (Task 1). Fonts from Google Fonts. No auth.

**Depends on:** Public catalogue API (`/api/public/playbooks`, `/api/public/playbooks/{id}/slots`, `/api/public/cases`) — already built in the Catalogue Layer. Also fetches `/api/public/checkout-config` (stub in this plan, real endpoint in Subsystem 2).

**Note on checkout:** `POST /api/orders/checkout` is built in Subsystem 2. In this plan the "Order Now" button is present in the UI but disabled with a "Launching soon" message. The order confirmation page is a stub. Remove the stub and wire live in Subsystem 2.

**No build week picker:** customers do not select a build week. The build scheduler (Subsystem 2) assigns dates automatically. The customer only sees a static delivery estimate ("3–5 working days" or "2–3 working days" for fast-track).

---

## File Map

| File | Responsibility |
|------|---------------|
| `pc-flipper-customer/app/layout.tsx` | Root layout — nav bar, footer, fonts, CSS vars |
| `pc-flipper-customer/app/globals.css` | CSS custom properties from Stitch design tokens |
| `pc-flipper-customer/app/page.tsx` | Landing page (Server Component) |
| `pc-flipper-customer/app/configure/[slug]/page.tsx` | Configurator shell (Server Component — fetches data) |
| `pc-flipper-customer/app/configure/[slug]/ConfiguratorClient.tsx` | Full configurator UI (Client Component) |
| `pc-flipper-customer/app/order/[reference]/page.tsx` | Order confirmation stub (Server Component) |
| `pc-flipper-customer/components/PlaybookCard.tsx` | Card on landing page |
| `pc-flipper-customer/components/SlotRow.tsx` | One component slot row in configurator |
| `pc-flipper-customer/components/SwapModal.tsx` | Component comparison modal |
| `pc-flipper-customer/components/CasePicker.tsx` | Case selection grid |
| `pc-flipper-customer/components/BuildSummary.tsx` | Sticky build summary + total + fast-track toggle + delivery estimate |
| `pc-flipper-customer/lib/types.ts` | All TypeScript interfaces |
| `pc-flipper-customer/lib/api.ts` | Fetch helpers for public API + stubs |
| `pc-flipper-customer/lib/playbook-config.ts` | Static descriptions + slug→name mapping |
| `pc-flipper-customer/lib/utils.ts` | `formatPrice`, `computeBudgetTotal`, `slugify` |
| `pc-flipper-customer/next.config.ts` | API rewrites to FlipFlop backend |

---

## Task 1: Google Stitch Design Session

**Files:**
- Create: `pc-flipper-customer/design-tokens.md` (output of this task)

This is a manual design task. Run Google Stitch to generate the visual design for the storefront, then record the output here so subsequent tasks can use it.

- [ ] **Step 1: Open Google Stitch**

Go to [stitch.withgoogle.com](https://stitch.withgoogle.com) and start a new project named "FlipFlop Storefront".

- [ ] **Step 2: Generate the landing page design**

Prompt Stitch with:

```
Design a landing page for "FlipFlop" — a UK company that builds made-to-order PCs from curated second-hand components. Dark theme. Cards showing PC build types (Gaming Rig, AI Machine, Home Office, etc). Modern, technical feel. Each card shows the build name, a short description, tier options (e.g. Starter / Battle-Ready / Beast Mode), and a "from £X" price. CTA button "Configure your build →".
```

Iterate until the design looks right. Note the following from the output:

- Primary background colour (e.g. `#0f0f11`)
- Secondary/card background (e.g. `#18181b`)
- Border colour (e.g. `#27272a`)
- Primary text colour (e.g. `#fafafa`)
- Secondary text colour (e.g. `#71717a`)
- Accent colour (e.g. `#22c55e`)
- Font family for headings (e.g. `Space Grotesk`)
- Font family for body (e.g. `Inter`)
- Border radius style (sharp / medium / rounded)

- [ ] **Step 3: Generate the configurator page design**

Prompt Stitch with:

```
Design a PC configurator page for FlipFlop. Left panel: tier picker (3 buttons), then a list of component slots (CPU, GPU, RAM, Storage, Case) each with a "swap" button. Right panel: sticky build summary with line items, total price, build slot week picker, and "Order Now" green button. Same dark theme as landing page.
```

Note any additional design tokens that differ from the landing page.

- [ ] **Step 4: Record design tokens**

Create `pc-flipper-customer/design-tokens.md` with the values from Stitch:

```markdown
# FlipFlop Storefront Design Tokens

## Colours
- `--color-bg`: #0f0f11
- `--color-bg-card`: #18181b
- `--color-border`: #27272a
- `--color-text`: #fafafa
- `--color-text-muted`: #71717a
- `--color-accent`: #22c55e
- `--color-accent-hover`: #16a34a
- `--color-danger`: #ef4444

## Typography
- Heading font: Space Grotesk (weights: 500, 600, 700)
- Body font: Inter (weights: 400, 500)

## Spacing / Radius
- Card border radius: 12px
- Button border radius: 8px

## Stitch export URL: [paste Stitch share link here]
```

Replace placeholder values with actual Stitch output.

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/design-tokens.md
git commit -m "design: FlipFlop storefront design tokens from Google Stitch"
```

---

## Task 2: Scaffold `pc-flipper-customer/`

**Files:**
- Create: `pc-flipper-customer/` (entire project)
- Create: `pc-flipper-customer/next.config.ts`
- Create: `pc-flipper-customer/.env.local`

- [ ] **Step 1: Create the Next.js project**

```bash
cd /home/mac/CODING/FlipFlop
npx create-next-app@latest pc-flipper-customer \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --no-eslint \
  --import-alias "@/*"
```

When prompted for "Would you like to use Turbopack?" — choose **No** (keep webpack for stability).

- [ ] **Step 2: Replace `next.config.ts`**

```typescript
// pc-flipper-customer/next.config.ts
import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:4311";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 3: Create `.env.local`**

```bash
# pc-flipper-customer/.env.local
BACKEND_URL=http://andromeda-ts:8000
```

- [ ] **Step 4: Install Lucide icons**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npm install lucide-react
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npm run dev -- --port 3001
```

Expected: server starts on http://andromeda-ts:3001, default Next.js page loads. Stop with Ctrl+C.

- [ ] **Step 6: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/
git commit -m "feat(storefront): scaffold pc-flipper-customer Next.js app"
```

---

## Task 3: Types and API Client

**Files:**
- Create: `pc-flipper-customer/lib/types.ts`
- Create: `pc-flipper-customer/lib/api.ts`
- Create: `pc-flipper-customer/lib/utils.ts`

- [ ] **Step 1: Create `lib/types.ts`**

```typescript
// pc-flipper-customer/lib/types.ts

export interface PublicPlaybook {
  id: number;
  name: string;
  slots: PublicSlotSummary[];
}

export interface PublicSlotSummary {
  id: number;
  slot_type: SlotType;
  is_customer_visible: boolean;
  tier_names: TierNames;
}

export type SlotType = "cpu" | "gpu" | "ram" | "storage" | "cooling" | "os";
export type Tier = "budget" | "mid" | "high";

export interface TierNames {
  budget: string;
  mid: string;
  high: string;
}

export interface PublicSlotWithVariants {
  slot_id: number;
  slot_type: SlotType;
  tier_names: TierNames;
  variants_by_tier: Record<Tier, PublicVariant[]>;
}

export interface PublicVariant {
  id: number;
  title: string;
  display_price: number;
  gem_score: number;
}

export interface PublicCase {
  id: number;
  name: string;
  brand: string;
  form_factor: string;
  images: string[];
  rrp_gbp: number;
  is_transparent_panel: boolean;
  notes: string | null;
}

// The customer's current build state
export interface BuildState {
  slots: Record<SlotType, PublicVariant | null>;
  case: PublicCase | null;
  isFastTrack: boolean;
}

// Checkout config from /api/public/checkout-config (Subsystem 2 endpoint; stubbed in Subsystem 1)
export interface CheckoutConfig {
  postage_gbp: number;
  insurance_rate_pct: number;   // e.g. 1.5 = 1.5%
  fast_track_fee_gbp: number;
  standard_days_min: number;
  standard_days_max: number;
  fast_track_days_min: number;
  fast_track_days_max: number;
}
```

- [ ] **Step 2: Create `lib/api.ts`**

```typescript
// pc-flipper-customer/lib/api.ts
import type { PublicCase, PublicPlaybook, PublicSlotWithVariants, CheckoutConfig } from "./types";

// All fetches in this file run inside Server Components — relative paths don't work
// from the server process, so we use BACKEND_URL directly to hit the backend.
const API = process.env.BACKEND_URL ?? "http://localhost:4311";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export async function getPlaybooks(): Promise<PublicPlaybook[]> {
  return get<PublicPlaybook[]>("/api/public/playbooks");
}

export async function getPlaybookSlots(playbookId: number): Promise<PublicSlotWithVariants[]> {
  return get<PublicSlotWithVariants[]>(`/api/public/playbooks/${playbookId}/slots`);
}

export async function getCases(): Promise<PublicCase[]> {
  return get<PublicCase[]>("/api/public/cases");
}

// STUB — replaced by real /api/public/checkout-config endpoint in Subsystem 2
export async function getCheckoutConfig(): Promise<CheckoutConfig> {
  return {
    postage_gbp: 12.00,
    insurance_rate_pct: 1.5,
    fast_track_fee_gbp: 49.00,
    standard_days_min: 3,
    standard_days_max: 5,
    fast_track_days_min: 2,
    fast_track_days_max: 3,
  };
}
```

- [ ] **Step 3: Create `lib/utils.ts`**

```typescript
// pc-flipper-customer/lib/utils.ts
import type { PublicSlotWithVariants, PublicCase, Tier } from "./types";

export function formatPrice(p: number): string {
  return `£${Math.round(p)}`;
}

export function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

/** Sum of cheapest budget variant per customer-visible slot + lowest case RRP */
export function computeBudgetTotal(
  slots: PublicSlotWithVariants[],
  cases: PublicCase[]
): number {
  const slotTotal = slots.reduce((sum, s) => {
    const budgetVariants = s.variants_by_tier.budget;
    if (!budgetVariants.length) return sum;
    const cheapest = budgetVariants.reduce((a, b) => a.display_price < b.display_price ? a : b);
    return sum + cheapest.display_price;
  }, 0);

  const caseRrp = cases.length
    ? Math.min(...cases.map(c => c.rrp_gbp))
    : 0;

  return slotTotal + caseRrp;
}

/** Pick highest gem-score variant for a given tier. Falls back to mid, then budget. */
export function bestVariantForTier(
  variants_by_tier: Record<Tier, { id: number; title: string; display_price: number; gem_score: number }[]>,
  tier: Tier
): { id: number; title: string; display_price: number; gem_score: number } | null {
  const candidates = variants_by_tier[tier];
  if (candidates.length) {
    return candidates.reduce((a, b) => a.gem_score > b.gem_score ? a : b);
  }
  // Fallback to adjacent tiers
  const fallbackOrder: Tier[] = tier === "high" ? ["mid", "budget"] : tier === "budget" ? ["mid", "high"] : ["budget", "high"];
  for (const t of fallbackOrder) {
    const fb = variants_by_tier[t];
    if (fb.length) return fb.reduce((a, b) => a.gem_score > b.gem_score ? a : b);
  }
  return null;
}

export function formatWeek(weekStart: string): string {
  const d = new Date(weekStart);
  return `w/c ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}
```

- [ ] **Step 4: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/lib/
git commit -m "feat(storefront): types, API client, and utility functions"
```

---

## Task 4: Playbook Config

**Files:**
- Create: `pc-flipper-customer/lib/playbook-config.ts`

Static descriptions and emoji for each playbook. Descriptions are marketing copy — not in the DB.

- [ ] **Step 1: Create `lib/playbook-config.ts`**

```typescript
// pc-flipper-customer/lib/playbook-config.ts

interface PlaybookMeta {
  slug: string;
  emoji: string;
  tagline: string;
  description: string;
}

// Keys are lowercase substrings matched against playbook.name
const PLAYBOOK_META: Record<string, PlaybookMeta> = {
  gaming: {
    slug: "gaming-rig",
    emoji: "🎮",
    tagline: "Built to dominate",
    description: "High-refresh gaming with curated GPUs and CPUs scored for frame-rate performance.",
  },
  ai: {
    slug: "ai-machine",
    emoji: "🤖",
    tagline: "Train, infer, iterate",
    description: "VRAM-heavy builds optimised for local AI inference and model training.",
  },
  creative: {
    slug: "creative-studio",
    emoji: "🎨",
    tagline: "Render at full speed",
    description: "Multi-core CPU and GPU builds for video editing, 3D, and creative workloads.",
  },
  build: {
    slug: "build-your-own",
    emoji: "⚙️",
    tagline: "Full control",
    description: "Pick every component yourself from our curated catalogue of verified gems.",
  },
  home: {
    slug: "home-office",
    emoji: "🏠",
    tagline: "Quiet, fast, reliable",
    description: "Balanced everyday computing — fast enough for anything, quiet enough for any room.",
  },
  business: {
    slug: "business-workstation",
    emoji: "💼",
    tagline: "Professional grade",
    description: "Reliable, maintainable workstations for business productivity and remote work.",
  },
  student: {
    slug: "student-pc",
    emoji: "📚",
    tagline: "More power, less spend",
    description: "Capable builds at student budget — great for coursework, coding, and light gaming.",
  },
};

const DEFAULT_META: Omit<PlaybookMeta, "slug"> = {
  emoji: "💻",
  tagline: "Quality components, expert assembly",
  description: "Curated PC builds from verified second-hand components — tested before delivery.",
};

export function getPlaybookMeta(name: string): PlaybookMeta {
  const lower = name.toLowerCase();
  for (const [key, meta] of Object.entries(PLAYBOOK_META)) {
    if (lower.includes(key)) return meta;
  }
  return { slug: slugifyFallback(name), ...DEFAULT_META };
}

function slugifyFallback(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// Used on the landing page to build hrefs
export function playbookSlug(name: string): string {
  return getPlaybookMeta(name).slug;
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/lib/playbook-config.ts
git commit -m "feat(storefront): static playbook descriptions and slug config"
```

---

## Task 5: Root Layout and Global CSS

**Files:**
- Modify: `pc-flipper-customer/app/layout.tsx`
- Modify: `pc-flipper-customer/app/globals.css`

Use the design tokens from `design-tokens.md` (Task 1). The values below are defaults — replace with actual Stitch output.

- [ ] **Step 1: Update `app/globals.css`**

```css
/* pc-flipper-customer/app/globals.css */
@import "tailwindcss";

:root {
  /* Replace these with values from design-tokens.md */
  --color-bg: #0f0f11;
  --color-bg-card: #18181b;
  --color-border: #27272a;
  --color-text: #fafafa;
  --color-text-muted: #71717a;
  --color-accent: #22c55e;
  --color-accent-hover: #16a34a;
  --color-danger: #ef4444;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-body, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}

/* Utility classes using design tokens */
.card {
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
}

.btn-accent {
  background-color: var(--color-accent);
  color: #000;
  font-weight: 700;
  border-radius: 8px;
  padding: 10px 20px;
  transition: background-color 0.15s;
}

.btn-accent:hover {
  background-color: var(--color-accent-hover);
}

.btn-accent:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.text-muted {
  color: var(--color-text-muted);
}
```

- [ ] **Step 2: Update `app/layout.tsx`**

Replace the default layout with fonts from design-tokens.md. The example below uses Space Grotesk + Inter — replace with actual Stitch fonts.

```tsx
// pc-flipper-customer/app/layout.tsx
import type { Metadata } from "next";
import { Space_Grotesk, Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

// Replace with fonts from design-tokens.md
const heading = Space_Grotesk({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const body = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "FlipFlop — Made-to-Order PCs",
  description: "Curated second-hand components. Expert assembly. Delivered to your door.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${heading.variable} ${body.variable}`}>
      <body>
        <header style={{ borderBottom: "1px solid var(--color-border)" }}
          className="sticky top-0 z-50 backdrop-blur-sm"
          style={{ background: "color-mix(in srgb, var(--color-bg) 80%, transparent)" }}>
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
            <Link href="/" className="font-bold text-lg tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}>
              FlipFlop
            </Link>
            <nav className="flex items-center gap-6 text-sm text-muted">
              <Link href="/#how-it-works" className="hover:text-white transition-colors">How it works</Link>
              <Link href="mailto:hello@flipflop.co.uk" className="hover:text-white transition-colors">Contact</Link>
            </nav>
          </div>
        </header>

        <main>{children}</main>

        <footer style={{ borderTop: "1px solid var(--color-border)" }}
          className="mt-24 py-12 text-center text-muted text-sm">
          <p>© {new Date().getFullYear()} FlipFlop. All components are tested before dispatch.</p>
          <p className="mt-1">Questions? <a href="mailto:hello@flipflop.co.uk" className="underline hover:text-white">hello@flipflop.co.uk</a></p>
        </footer>
      </body>
    </html>
  );
}
```

Note: the duplicate `style` on `<header>` is intentional JSX — fix if TypeScript flags it by merging into one style prop.

- [ ] **Step 3: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/app/layout.tsx pc-flipper-customer/app/globals.css
git commit -m "feat(storefront): root layout and global CSS with design tokens"
```

---

## Task 6: Landing Page

**Files:**
- Modify: `pc-flipper-customer/app/page.tsx`
- Create: `pc-flipper-customer/components/PlaybookCard.tsx`

- [ ] **Step 1: Create `components/PlaybookCard.tsx`**

```tsx
// pc-flipper-customer/components/PlaybookCard.tsx
import Link from "next/link";
import type { PublicPlaybook, PublicSlotWithVariants, PublicCase } from "@/lib/types";
import { getPlaybookMeta } from "@/lib/playbook-config";
import { computeBudgetTotal, formatPrice } from "@/lib/utils";

interface Props {
  playbook: PublicPlaybook;
  slots: PublicSlotWithVariants[];
  cases: PublicCase[];
}

export function PlaybookCard({ playbook, slots, cases }: Props) {
  const meta = getPlaybookMeta(playbook.name);
  const budgetTotal = computeBudgetTotal(slots, cases);

  // Tier names from the first slot that has them (all slots share the same tier_names per playbook)
  const tierNames = slots[0]?.tier_names ?? { budget: "Budget", mid: "Mid", high: "High" };

  return (
    <Link href={`/configure/${meta.slug}`} className="card block p-6 hover:border-[var(--color-accent)] transition-colors group">
      <div className="text-3xl mb-3">{meta.emoji}</div>
      <h2 className="font-bold text-lg mb-1" style={{ fontFamily: "var(--font-heading)" }}>
        {playbook.name}
      </h2>
      <p className="text-sm text-muted mb-4 leading-relaxed">{meta.description}</p>

      <div className="flex gap-2 mb-5">
        {(["budget", "mid", "high"] as const).map((tier) => (
          <span key={tier} className="text-xs px-2.5 py-1 rounded-full"
            style={{ background: "var(--color-border)", color: "var(--color-text-muted)" }}>
            {tierNames[tier]}
          </span>
        ))}
      </div>

      {budgetTotal > 0 && (
        <p className="text-sm text-muted">
          from <span className="font-bold text-white">{formatPrice(budgetTotal)}</span>
        </p>
      )}

      <div className="mt-4 text-sm font-semibold text-[var(--color-accent)] group-hover:underline">
        Configure your build →
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Rewrite `app/page.tsx`**

```tsx
// pc-flipper-customer/app/page.tsx
import { getPlaybooks, getPlaybookSlots, getCases } from "@/lib/api";
import { PlaybookCard } from "@/components/PlaybookCard";
import type { PublicSlotWithVariants, PublicCase } from "@/lib/types";

export const revalidate = 60;

export default async function HomePage() {
  const [playbooks, cases] = await Promise.all([
    getPlaybooks(),
    getCases(),
  ]);

  // Fetch slots for all playbooks in parallel (needed for budget total)
  const slotsPerPlaybook: Record<number, PublicSlotWithVariants[]> = {};
  await Promise.all(
    playbooks.map(async (pb) => {
      try {
        slotsPerPlaybook[pb.id] = await getPlaybookSlots(pb.id);
      } catch {
        slotsPerPlaybook[pb.id] = [];
      }
    })
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-16">
      {/* Hero */}
      <div className="text-center mb-16">
        <h1 className="text-4xl sm:text-5xl font-bold mb-4 tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}>
          Your PC. <span style={{ color: "var(--color-accent)" }}>Built to order.</span>
        </h1>
        <p className="text-lg text-muted max-w-xl mx-auto">
          Curated second-hand components. Expert assembly. Tested before delivery.
          Choose your build type and configure it exactly how you want.
        </p>
      </div>

      {/* Playbook grid */}
      {playbooks.length === 0 ? (
        <p className="text-center text-muted">No builds available right now — check back soon.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {playbooks.map((pb) => (
            <PlaybookCard
              key={pb.id}
              playbook={pb}
              slots={slotsPerPlaybook[pb.id] ?? []}
              cases={cases}
            />
          ))}
        </div>
      )}

      {/* How it works */}
      <div id="how-it-works" className="mt-24 text-center">
        <h2 className="text-2xl font-bold mb-10" style={{ fontFamily: "var(--font-heading)" }}>
          How it works
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 text-left max-w-3xl mx-auto">
          {[
            { n: "1", title: "Pick your build", body: "Choose from our curated playbooks — each tailored to a specific use case and budget." },
            { n: "2", title: "Configure it", body: "Select your tier, swap any component, and choose a case. See live pricing as you go." },
            { n: "3", title: "We build and deliver", body: "We source, test, and assemble your PC. Delivered to your door within your chosen week." },
          ].map(({ n, title, body }) => (
            <div key={n}>
              <div className="text-2xl font-bold mb-2" style={{ color: "var(--color-accent)", fontFamily: "var(--font-heading)" }}>{n}.</div>
              <h3 className="font-semibold mb-2">{title}</h3>
              <p className="text-sm text-muted leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run dev server and check landing page**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npm run dev -- --port 3001
```

Open http://andromeda-ts:3001. Expected: hero + playbook cards grid (may show "No builds available" if catalogue is empty — that's fine). Check console for errors.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/app/page.tsx pc-flipper-customer/components/PlaybookCard.tsx
git commit -m "feat(storefront): landing page with playbook cards and hero"
```

---

## Task 7: Configurator Page — Server Shell

**Files:**
- Create: `pc-flipper-customer/app/configure/[slug]/page.tsx`

The server component resolves the slug to a playbook ID, fetches all data, and passes it to the client configurator. Returns 404 if slug doesn't match any active playbook.

- [ ] **Step 1: Create `app/configure/[slug]/page.tsx`**

```tsx
// pc-flipper-customer/app/configure/[slug]/page.tsx
import { notFound } from "next/navigation";
import { getPlaybooks, getPlaybookSlots, getCases, getCheckoutConfig } from "@/lib/api";
import { getPlaybookMeta, playbookSlug } from "@/lib/playbook-config";
import { ConfiguratorClient } from "./ConfiguratorClient";

export const revalidate = 30;

interface Props {
  params: { slug: string };
  searchParams: { tier?: string };
}

export default async function ConfiguratorPage({ params, searchParams }: Props) {
  const playbooks = await getPlaybooks();

  // Resolve slug → playbook
  const playbook = playbooks.find(
    (pb) => playbookSlug(pb.name) === params.slug
  );
  if (!playbook) notFound();

  const [slots, cases, config] = await Promise.all([
    getPlaybookSlots(playbook.id),
    getCases(),
    getCheckoutConfig(),
  ]);

  const initialTier = (["budget", "mid", "high"].includes(searchParams.tier ?? ""))
    ? (searchParams.tier as "budget" | "mid" | "high")
    : "mid";

  const meta = getPlaybookMeta(playbook.name);

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="mb-8">
        <p className="text-sm text-muted mb-1">
          <a href="/" className="hover:text-white">FlipFlop</a> / {playbook.name}
        </p>
        <h1 className="text-3xl font-bold" style={{ fontFamily: "var(--font-heading)" }}>
          {meta.emoji} {playbook.name}
        </h1>
        <p className="text-muted mt-1">{meta.tagline}</p>
      </div>

      <ConfiguratorClient
        playbook={playbook}
        slots={slots}
        cases={cases}
        config={config}
        initialTier={initialTier}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create placeholder `ConfiguratorClient.tsx` (so page compiles)**

```tsx
// pc-flipper-customer/app/configure/[slug]/ConfiguratorClient.tsx
"use client";
import type { PublicPlaybook, PublicSlotWithVariants, PublicCase, CheckoutConfig, Tier } from "@/lib/types";

interface Props {
  playbook: PublicPlaybook;
  slots: PublicSlotWithVariants[];
  cases: PublicCase[];
  config: CheckoutConfig;
  initialTier: Tier;
}

export function ConfiguratorClient({ playbook, slots }: Props) {
  return (
    <div className="text-muted text-sm">
      Configurator loading… ({slots.length} slots for {playbook.name})
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 4: Check configure page loads**

With dev server running on port 3001, open http://andromeda-ts:3001/configure/gaming-rig (or any slug). Expected: page loads with playbook name in header and "Configurator loading…" placeholder. If no playbooks exist in DB, it will show Next.js 404.

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/app/configure/
git commit -m "feat(storefront): configurator page server shell with slug resolution"
```

---

## Task 8: Slot List + Tier Picker

**Files:**
- Modify: `pc-flipper-customer/app/configure/[slug]/ConfiguratorClient.tsx`
- Create: `pc-flipper-customer/components/SlotRow.tsx`

- [ ] **Step 1: Create `components/SlotRow.tsx`**

```tsx
// pc-flipper-customer/components/SlotRow.tsx
import type { SlotType, PublicVariant } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

const SLOT_LABELS: Record<SlotType, string> = {
  cpu: "Processor",
  gpu: "Graphics Card",
  ram: "Memory",
  storage: "Storage",
  cooling: "Cooling",
  os: "Operating System",
};

interface Props {
  slotType: SlotType;
  selected: PublicVariant | null;
  onSwap: () => void;
}

export function SlotRow({ slotType, selected, onSwap }: Props) {
  return (
    <div className="flex items-center gap-4 py-3 px-4 rounded-lg"
      style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
      <div className="w-24 shrink-0">
        <span className="text-xs font-bold uppercase tracking-wider text-muted">
          {SLOT_LABELS[slotType]}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        {selected ? (
          <>
            <p className="text-sm font-medium truncate">{selected.title}</p>
            <p className="text-xs text-muted mt-0.5">Gem score {selected.gem_score.toFixed(0)}</p>
          </>
        ) : (
          <p className="text-sm text-muted italic">No variants available</p>
        )}
      </div>
      {selected && (
        <p className="font-semibold text-sm shrink-0">{formatPrice(selected.display_price)}</p>
      )}
      {selected && (
        <button
          onClick={onSwap}
          className="text-xs shrink-0 px-3 py-1.5 rounded-md font-medium transition-colors"
          style={{ background: "var(--color-border)", color: "var(--color-text-muted)" }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--color-text)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--color-text-muted)")}
        >
          Swap
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Replace `ConfiguratorClient.tsx` with full tier picker + slot list**

```tsx
// pc-flipper-customer/app/configure/[slug]/ConfiguratorClient.tsx
"use client";

import { useState, useCallback } from "react";
import type {
  PublicPlaybook, PublicSlotWithVariants, PublicCase,
  AvailableWeek, Tier, SlotType, BuildState, PublicVariant
} from "@/lib/types";
import { bestVariantForTier } from "@/lib/utils";
import { SlotRow } from "@/components/SlotRow";
import { SwapModal } from "@/components/SwapModal";
import { CasePicker } from "@/components/CasePicker";
import { BuildSummary } from "@/components/BuildSummary";

interface Props {
  playbook: PublicPlaybook;
  slots: PublicSlotWithVariants[];
  cases: PublicCase[];
  weeks: AvailableWeek[];
  initialTier: Tier;
}

function buildInitialState(slots: PublicSlotWithVariants[], cases: PublicCase[], tier: Tier): BuildState {
  const slotState: Record<string, PublicVariant | null> = {};
  for (const slot of slots) {
    slotState[slot.slot_type] = bestVariantForTier(slot.variants_by_tier, tier);
  }
  return {
    slots: slotState as BuildState["slots"],
    case: cases[0] ?? null,
    chosenWeek: null,
  };
}

export function ConfiguratorClient({ slots, cases, weeks, initialTier }: Props) {
  const [tier, setTier] = useState<Tier>(initialTier);
  const [build, setBuild] = useState<BuildState>(() => buildInitialState(slots, cases, initialTier));
  const [swapTarget, setSwapTarget] = useState<PublicSlotWithVariants | null>(null);

  const switchTier = useCallback((newTier: Tier) => {
    setTier(newTier);
    const newSlots: Record<string, PublicVariant | null> = {};
    for (const slot of slots) {
      newSlots[slot.slot_type] = bestVariantForTier(slot.variants_by_tier, newTier);
    }
    setBuild(prev => ({ ...prev, slots: newSlots as BuildState["slots"] }));
  }, [slots]);

  const applySwap = useCallback((slotType: SlotType, variant: PublicVariant) => {
    setBuild(prev => ({
      ...prev,
      slots: { ...prev.slots, [slotType]: variant },
    }));
    setSwapTarget(null);
  }, []);

  // Tier names come from the first slot (all slots share the same tier_names per playbook)
  const tierNames = slots[0]?.tier_names ?? { budget: "Budget", mid: "Mid", high: "High" };

  return (
    <div className="flex flex-col lg:flex-row gap-8">
      {/* Left panel */}
      <div className="flex-1 min-w-0">
        {/* Tier picker */}
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-muted mb-3">Starting point</p>
          <div className="flex gap-3">
            {(["budget", "mid", "high"] as Tier[]).map((t) => (
              <button
                key={t}
                onClick={() => switchTier(t)}
                className="flex-1 py-3 px-4 rounded-xl text-sm font-semibold transition-all"
                style={{
                  border: `2px solid ${tier === t ? "var(--color-accent)" : "var(--color-border)"}`,
                  background: tier === t ? "color-mix(in srgb, var(--color-accent) 8%, transparent)" : "var(--color-bg-card)",
                  color: tier === t ? "var(--color-accent)" : "var(--color-text-muted)",
                }}
              >
                {tierNames[t]}
              </button>
            ))}
          </div>
        </div>

        {/* Slot list */}
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-muted mb-3">Components</p>
          <div className="flex flex-col gap-2">
            {slots.map((slot) => (
              <SlotRow
                key={slot.slot_id}
                slotType={slot.slot_type}
                selected={build.slots[slot.slot_type] ?? null}
                onSwap={() => setSwapTarget(slot)}
              />
            ))}
          </div>
        </div>

        {/* Case picker */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-muted mb-3">Case</p>
          <CasePicker
            cases={cases}
            selected={build.case}
            onSelect={(c) => setBuild(prev => ({ ...prev, case: c }))}
          />
        </div>
      </div>

      {/* Right panel — sticky summary */}
      <div className="lg:w-72 shrink-0">
        <div className="sticky top-20">
          <BuildSummary
            build={build}
            slots={slots}
            weeks={weeks}
            onWeekSelect={(w) => setBuild(prev => ({ ...prev, chosenWeek: w }))}
          />
        </div>
      </div>

      {/* Swap modal */}
      {swapTarget && (
        <SwapModal
          slot={swapTarget}
          currentVariant={build.slots[swapTarget.slot_type] ?? null}
          onSelect={(v) => applySwap(swapTarget.slot_type, v)}
          onClose={() => setSwapTarget(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create stub files for components not yet built (so TypeScript compiles)**

```tsx
// pc-flipper-customer/components/SwapModal.tsx
"use client";
export function SwapModal(_p: any) { return null; }
```

```tsx
// pc-flipper-customer/components/CasePicker.tsx
"use client";
export function CasePicker(_p: any) { return null; }
```

```tsx
// pc-flipper-customer/components/BuildSummary.tsx
"use client";
export function BuildSummary(_p: any) { return null; }
```

- [ ] **Step 4: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/app/configure/ pc-flipper-customer/components/
git commit -m "feat(storefront): tier picker and slot list in configurator"
```

---

## Task 9: Swap Modal

**Files:**
- Modify: `pc-flipper-customer/components/SwapModal.tsx`

- [ ] **Step 1: Replace the stub `SwapModal.tsx` with the full component**

```tsx
// pc-flipper-customer/components/SwapModal.tsx
"use client";

import { useEffect } from "react";
import type { PublicSlotWithVariants, PublicVariant } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { X } from "lucide-react";

const SLOT_LABELS: Record<string, string> = {
  cpu: "Processor", gpu: "Graphics Card", ram: "Memory",
  storage: "Storage", cooling: "Cooling", os: "Operating System",
};

interface Props {
  slot: PublicSlotWithVariants;
  currentVariant: PublicVariant | null;
  onSelect: (v: PublicVariant) => void;
  onClose: () => void;
}

const TIER_LABELS: Record<string, string> = {
  budget: "Budget", mid: "Mid-Range", high: "High End",
};
const TIER_COLOURS: Record<string, string> = {
  budget: "#60a5fa", mid: "#fbbf24", high: "#22c55e",
};

export function SwapModal({ slot, currentVariant, onSelect, onClose }: Props) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Flatten all variants sorted by gem_score desc
  const allVariants: (PublicVariant & { tier: string })[] = (
    ["high", "mid", "budget"] as const
  ).flatMap((tier) =>
    slot.variants_by_tier[tier].map((v) => ({ ...v, tier }))
  ).sort((a, b) => b.gem_score - a.gem_score);

  const priceDelta = (v: PublicVariant) =>
    currentVariant ? v.display_price - currentVariant.display_price : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-lg rounded-2xl overflow-hidden"
        style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid var(--color-border)" }}>
          <div>
            <h2 className="font-bold text-base">
              Choose {SLOT_LABELS[slot.slot_type] ?? slot.slot_type}
            </h2>
            <p className="text-xs text-muted mt-0.5">
              {allVariants.length} option{allVariants.length !== 1 ? "s" : ""} available
            </p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-white transition-colors p-1">
            <X size={18} />
          </button>
        </div>

        {/* Variant list */}
        <div className="overflow-y-auto max-h-[60vh] p-4 flex flex-col gap-3">
          {allVariants.length === 0 && (
            <p className="text-center text-muted text-sm py-8">No variants available for this slot.</p>
          )}
          {allVariants.map((v) => {
            const isCurrent = v.id === currentVariant?.id;
            const delta = priceDelta(v);
            return (
              <button
                key={v.id}
                onClick={() => onSelect(v)}
                className="w-full text-left rounded-xl p-4 transition-all"
                style={{
                  border: `2px solid ${isCurrent ? "var(--color-accent)" : "var(--color-border)"}`,
                  background: isCurrent
                    ? "color-mix(in srgb, var(--color-accent) 6%, transparent)"
                    : "transparent",
                }}
                onMouseEnter={e => {
                  if (!isCurrent) (e.currentTarget as HTMLElement).style.borderColor = "#555";
                }}
                onMouseLeave={e => {
                  if (!isCurrent) (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)";
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm truncate">{v.title}</span>
                      {isCurrent && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-bold"
                          style={{ background: "var(--color-accent)", color: "#000" }}>
                          Current
                        </span>
                      )}
                      <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ color: TIER_COLOURS[v.tier], background: `color-mix(in srgb, ${TIER_COLOURS[v.tier]} 12%, transparent)` }}>
                        {TIER_LABELS[v.tier] ?? v.tier}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2">
                      <span className="text-xs text-muted">
                        Gem score <span className="font-bold text-white">{v.gem_score.toFixed(0)}</span>
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-bold text-sm">{formatPrice(v.display_price)}</p>
                    {!isCurrent && delta !== 0 && (
                      <p className="text-xs mt-0.5"
                        style={{ color: delta > 0 ? "#fbbf24" : "var(--color-accent)" }}>
                        {delta > 0 ? `+${formatPrice(delta)}` : formatPrice(delta)}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="px-5 py-3 text-xs text-muted text-center"
          style={{ borderTop: "1px solid var(--color-border)" }}>
          Prices update hourly · availability confirmed at checkout
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 3: Test the modal in browser**

With dev server running, open the configurator for any playbook, click "Swap" on a slot. Expected: modal appears with component options. Escape closes it. Clicking a variant closes the modal and updates the slot row.

- [ ] **Step 4: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/components/SwapModal.tsx
git commit -m "feat(storefront): component swap modal with gem score and price delta"
```

---

## Task 10: Case Picker

**Files:**
- Modify: `pc-flipper-customer/components/CasePicker.tsx`

- [ ] **Step 1: Replace the stub `CasePicker.tsx`**

```tsx
// pc-flipper-customer/components/CasePicker.tsx
"use client";

import type { PublicCase } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

interface Props {
  cases: PublicCase[];
  selected: PublicCase | null;
  onSelect: (c: PublicCase) => void;
}

export function CasePicker({ cases, selected, onSelect }: Props) {
  if (cases.length === 0) {
    return <p className="text-sm text-muted italic">No cases available right now.</p>;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {cases.map((c) => {
        const isSelected = c.id === selected?.id;
        return (
          <button
            key={c.id}
            onClick={() => onSelect(c)}
            className="text-left rounded-xl p-4 transition-all"
            style={{
              border: `2px solid ${isSelected ? "var(--color-accent)" : "var(--color-border)"}`,
              background: isSelected
                ? "color-mix(in srgb, var(--color-accent) 6%, transparent)"
                : "var(--color-bg-card)",
            }}
          >
            {c.images[0] && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={c.images[0]}
                alt={c.name}
                className="w-full h-28 object-contain mb-3 rounded-lg"
                style={{ background: "var(--color-border)" }}
              />
            )}
            <p className="font-semibold text-sm truncate">{c.name}</p>
            <p className="text-xs text-muted mt-0.5">
              {c.brand} · {c.form_factor.toUpperCase()}
              {c.is_transparent_panel ? " · Glass panel" : ""}
            </p>
            <p className="text-sm font-bold mt-2">{formatPrice(c.rrp_gbp)}</p>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/components/CasePicker.tsx
git commit -m "feat(storefront): case picker grid"
```

---

## Task 11: Build Summary, Week Picker, and Checkout Stub

**Files:**
- Create: `pc-flipper-customer/components/WeekPicker.tsx`
- Modify: `pc-flipper-customer/components/BuildSummary.tsx`

- [ ] **Step 1: Create `components/WeekPicker.tsx`**

```tsx
// pc-flipper-customer/components/WeekPicker.tsx
"use client";

import type { AvailableWeek } from "@/lib/types";
import { formatWeek } from "@/lib/utils";

interface Props {
  weeks: AvailableWeek[];
  selected: string | null;
  onSelect: (week: string) => void;
}

export function WeekPicker({ weeks, selected, onSelect }: Props) {
  if (weeks.length === 0) {
    return <p className="text-xs text-muted">No build slots available right now.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {weeks.map((w) => {
        const isSelected = w.week === selected;
        return (
          <button
            key={w.week}
            onClick={() => onSelect(w.week)}
            className="flex items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-all"
            style={{
              border: `1px solid ${isSelected ? "var(--color-accent)" : "var(--color-border)"}`,
              background: isSelected
                ? "color-mix(in srgb, var(--color-accent) 8%, transparent)"
                : "var(--color-bg)",
              color: isSelected ? "var(--color-accent)" : "var(--color-text)",
            }}
          >
            <span className="font-medium">{formatWeek(w.week_start)}</span>
            <span className="text-xs text-muted">{w.available} slot{w.available !== 1 ? "s" : ""}</span>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Replace the stub `BuildSummary.tsx`**

```tsx
// pc-flipper-customer/components/BuildSummary.tsx
"use client";

import type { BuildState, PublicSlotWithVariants, AvailableWeek } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { WeekPicker } from "@/components/WeekPicker";

const SLOT_LABELS: Record<string, string> = {
  cpu: "CPU", gpu: "GPU", ram: "RAM", storage: "Storage",
  cooling: "Cooling", os: "OS",
};

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  weeks: AvailableWeek[];
  onWeekSelect: (week: string) => void;
}

export function BuildSummary({ build, slots, weeks, onWeekSelect }: Props) {
  const lineItems = slots
    .map((s) => ({ label: SLOT_LABELS[s.slot_type] ?? s.slot_type, variant: build.slots[s.slot_type] }))
    .filter((item) => item.variant !== null && item.variant !== undefined);

  const caseItem = build.case;

  const total =
    lineItems.reduce((sum, item) => sum + (item.variant?.display_price ?? 0), 0) +
    (caseItem?.rrp_gbp ?? 0);

  const canOrder = build.chosenWeek !== null && total > 0;

  return (
    <div className="rounded-2xl p-5 flex flex-col gap-5"
      style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}>
      <h3 className="font-bold text-sm uppercase tracking-wider">Your Build</h3>

      {/* Line items */}
      <div className="flex flex-col gap-1.5 text-sm">
        {lineItems.map(({ label, variant }) => (
          <div key={label} className="flex justify-between">
            <span className="text-muted">{label}</span>
            <span>{formatPrice(variant!.display_price)}</span>
          </div>
        ))}
        {caseItem && (
          <div className="flex justify-between">
            <span className="text-muted">Case</span>
            <span>{formatPrice(caseItem.rrp_gbp)}</span>
          </div>
        )}
        {lineItems.length === 0 && !caseItem && (
          <p className="text-muted text-xs italic">Select components above</p>
        )}
      </div>

      {/* Total */}
      {total > 0 && (
        <div className="flex justify-between font-bold text-base"
          style={{ borderTop: "1px solid var(--color-border)", paddingTop: "12px" }}>
          <span>Total</span>
          <span>{formatPrice(total)}</span>
        </div>
      )}

      {/* Week picker */}
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-muted mb-2">Build slot</p>
        <WeekPicker
          weeks={weeks}
          selected={build.chosenWeek}
          onSelect={onWeekSelect}
        />
      </div>

      {/* Checkout button — STUB until Subsystem 2 */}
      <div>
        <button
          disabled
          className="btn-accent w-full text-center py-3 rounded-xl text-sm"
          title="Checkout launching soon"
        >
          Order Now — Coming Soon
        </button>
        <p className="text-xs text-muted text-center mt-2">
          Checkout launching soon ·{" "}
          <a href="mailto:hello@flipflop.co.uk" className="underline hover:text-white">
            email us to order now
          </a>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 4: Test full configurator in browser**

Open http://andromeda-ts:3001/configure/[any-slug]. Verify:
- Tier picker switches all components
- Swap modal opens, selecting a variant updates the slot
- Case picker shows cases, selecting one highlights it
- Build summary updates prices as selections change
- Week picker shows 3 stub weeks, selecting one highlights it
- "Order Now" button is disabled with "Coming Soon" text

- [ ] **Step 5: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/components/WeekPicker.tsx pc-flipper-customer/components/BuildSummary.tsx
git commit -m "feat(storefront): build summary, week picker, and checkout stub"
```

---

## Task 12: Order Confirmation Stub

**Files:**
- Create: `pc-flipper-customer/app/order/[reference]/page.tsx`

This page will be fully wired in Subsystem 2. For now it shows a confirmation holding page — the URL customers land on after Stripe redirects back.

- [ ] **Step 1: Create `app/order/[reference]/page.tsx`**

```tsx
// pc-flipper-customer/app/order/[reference]/page.tsx
import Link from "next/link";
import { CheckCircle } from "lucide-react";

interface Props {
  params: { reference: string };
}

export default function OrderConfirmationPage({ params }: Props) {
  return (
    <div className="max-w-lg mx-auto px-4 py-24 text-center">
      <CheckCircle
        size={48}
        className="mx-auto mb-6"
        style={{ color: "var(--color-accent)" }}
      />
      <h1 className="text-2xl font-bold mb-3" style={{ fontFamily: "var(--font-heading)" }}>
        Order received
      </h1>
      <p className="text-muted mb-2">Reference: <span className="font-mono font-bold text-white">{params.reference}</span></p>
      <p className="text-muted text-sm leading-relaxed mb-8">
        We&apos;ve received your order and will be in touch to confirm your build slot and delivery details.
        Check your email for a confirmation.
      </p>
      <p className="text-sm text-muted mb-6">
        Questions?{" "}
        <a href="mailto:hello@flipflop.co.uk" className="underline hover:text-white">
          hello@flipflop.co.uk
        </a>
      </p>
      <Link href="/" className="text-sm text-muted hover:text-white transition-colors underline">
        ← Back to FlipFlop
      </Link>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/app/order/
git commit -m "feat(storefront): order confirmation stub page"
```

---

## Task 13: End-to-End Smoke Test

**Files:**
- No new files — verification task

- [ ] **Step 1: Full TypeScript check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 2: Production build check**

```bash
cd /home/mac/CODING/FlipFlop/pc-flipper-customer
npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` (or similar). No build errors.

- [ ] **Step 3: Walk the golden path**

Start dev server: `npm run dev -- --port 3001`

1. Open http://andromeda-ts:3001 → landing page loads, playbook cards visible
2. Click a playbook card → configurator opens with correct playbook name
3. Switch tier → all slot rows update
4. Click "Swap" on a slot → modal opens with variants sorted by gem score
5. Select a variant → modal closes, slot row updates, summary updates price
6. Scroll down to case picker → select a case, summary updates
7. Select a build week → week highlights in picker
8. "Order Now" button is disabled → tooltip says "Checkout launching soon"
9. Open http://andromeda-ts:3001/order/FF-TEST → confirmation stub renders

- [ ] **Step 4: Final commit**

```bash
cd /home/mac/CODING/FlipFlop
git add pc-flipper-customer/
git commit -m "feat(storefront): customer storefront complete — checkout stub, ready for Subsystem 2"
```
