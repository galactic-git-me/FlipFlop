# FlipFlop.shop - Curated PC Builds Storefront

Customer-facing storefront for browsing and configuring curated PC builds from approved playbooks.

## Features

- **Browse Builds**: 24 approved curated playbooks across 8 customer segments (Gaming, Student, Business, Content Creation, AI, Development, Family)
- **Budget Tiers**: Each segment has 3 tiers (Budget, Mid-range, High-end) with transparent pricing
- **FF-AIW-03 Bespoke Handling**: AI Workstation High (Threadripper PRO + RTX 6000 Ada) is flagged as bespoke/consult-only, not in default ladder
- **Prometheus Pre-built**: Dedicated page for the Prometheus ChromaFlair showcase build (£1,449 / £944.74 production cost)
- **3D Configurator**: Scaffold for MeshyBot `.glb` integration with extension points for:
  - 3D model loading (`/api/3d-assets/{case_id}`)
  - ARGB binding via WebGL uniforms
  - AR view via WebXR API
- **Analytics Events**: Client-side event tracking for AnalyticsBot:
  - `playbook_entered`
  - `case_chosen`
  - `upsell_chosen`
  - `rgb_tweaked`
  - `ar_opened`
  - `drop_off`

## Local Development

### Prerequisites

1. **FlipFlop API** must be running on port 18000:
   ```bash
   cd /workspace/flipflop-api
   # Start via pm2 or uvicorn
   pm2 start gemradar-api-18000
   # OR
   uvicorn app.main:app --host 0.0.0.0 --port 18000
   ```

2. **Node.js 18+** installed

### Setup

```bash
cd /workspace/FlipFlop.shop.new

# Install dependencies
npm install

# Start development server (port 3001)
npm run dev
```

Visit http://localhost:3001

### Build for Production

```bash
npm run build
npm start
```

## Architecture

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Data Source**: FlipFlop API `/api/public/*` endpoints

### Key Files

- `app/page.tsx` - Main catalogue browsing by segment
- `app/configure/[id]/ConfiguratorClient.tsx` - 3D configurator (client component)
- `app/prometheus/page.tsx` - Prometheus pre-built detail page
- `lib/api.ts` - API client for curated builds & cases
- `lib/analytics.ts` - Event tracking stub for AnalyticsBot
- `lib/utils.ts` - Formatting, DDR gen detection, bespoke checks

## API Endpoints Used

- `GET /api/public/curated-builds` - All 24 approved playbooks with pricing
- `GET /api/public/cases` - Active case catalogue (ranked, preferred)
- `GET /api/public/playbooks` - Playbook metadata

## Memory Generation Tags

The storefront automatically detects and displays memory generation:

- **DDR5**: GVG-02, GVG-03, HPG-01, HPG-02, HPG-03, STU-02, STU-03, BOF-02, CCR-01, CCR-02, CCR-03, AIW-01, AIW-02, AIW-03, SWD-01, SWD-02, SWD-03, FAM-02, FAM-03
- **DDR4**: GVG-01, BOF-01, FAM-01
- **LPDDR5X**: STU-01, BOF-03

## Missing Features (To Be Added)

- [ ] MeshyBot `.glb` 3D models (waiting on photo pack approvals)
- [ ] ARGB control binding
- [ ] AR view implementation (WebXR)
- [ ] Checkout flow (Stripe integration)
- [ ] AnalyticsBot backend ingestion

## Environment Variables

Create `.env.local`:

```env
FLIPFLOP_API_BASE=http://localhost:18000
```

## PM2 Integration

To add FlipFlop.shop to the ecosystem:

```javascript
// ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: 'flipflop-shop-3001',
      cwd: './FlipFlop.shop.new',
      script: 'npm',
      args: 'start',
      instances: 1,
      autorestart: true,
      watch: false,
    },
    // ... other apps
  ],
}
```

```bash
pm2 start ecosystem.config.cjs
pm2 save
```

## Data Flow

1. User visits `/` → SSR fetches `/api/public/curated-builds`
2. Builds grouped by segment, displayed with tier badges
3. User clicks build → `/configure/ff-gvg-01` (example)
4. Configurator loads case catalogue, tracks analytics events
5. 3D viewer placeholder ready for `.glb` extension
6. Checkout button (disabled until Stripe integration)

## Special Handling

### FF-AIW-03 (Bespoke)

```typescript
// lib/utils.ts
export function isBespokeOnly(buildId: string): boolean {
  return buildId === 'FF-AIW-03'
}
```

On catalogue page:
- Displayed with "Bespoke / Consult Only" badge
- Link disabled, shows "Contact for pricing"
- Not in default High tier ladder

### Prometheus Pre-built

- Separate route `/prometheus`
- Fixed pricing: £1,449 (production cost £944.74)
- Highlighted banner on homepage
- "Ready to Ship" badge

## Analytics Event Schema

```typescript
interface AnalyticsEvent {
  event_type: 'playbook_entered' | 'case_chosen' | 'upsell_chosen' | 'rgb_tweaked' | 'ar_opened' | 'drop_off'
  curated_build_id: string
  metadata?: Record<string, any>
  timestamp: string
}
```

Events stored in `sessionStorage` until AnalyticsBot backend is wired.
