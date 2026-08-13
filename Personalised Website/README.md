# FlipFlop Listing Templates

Two separate JSON-driven HTML templates in this folder:

1. **Performance Card** (`index.html` / `render.js` / `performance-data.json`) —
   the full interactive benchmark report, hosted and linked from listings.
2. **eBay Listing** (`ebay-listing-template.html` / `render-ebay.js` /
   `ebay-listing-data.json`) — the actual listing description HTML pasted into
   eBay. See "eBay Listing Template" section below — it works differently
   because eBay strips `<script>` tags.

## Performance Card Template

A branded, data-driven performance report for a FlipFlop build listing. Pulls all
content from `performance-data.json` at runtime — nothing is hardcoded in the HTML.

## Files

- `index.html` — page shell, styles, loading-video intro. No content lives here.
- `render.js` — fetches `performance-data.json` and builds the DOM.
- `performance-data.json` — **the only file that changes per build.**
- `assets/` — shared brand assets, reused across every build:
  - `logo.png` — FlipFlop cube logo (transparent PNG)
  - `Nasa.ttf` — display font used for headline text
  - `hero-loop.mp4` — loading-intro video (compressed cube animation)
  - `covers/*.jpg` — game cover art for the "Gaming performance" section

## Running it

`fetch()` of a local JSON file is blocked by browsers over `file://`, so this must
be served over HTTP, not double-clicked:

```bash
cd "Personalised Website"
npx serve .
```

Then open the printed localhost URL.

## Workflow: generating a new build's card

**When the admin tool build flow reaches the Performance step, prompt the user for
the benchmark stats before listing the build for sale** — don't invent numbers.
Ask for (or help them run): Novabench overall/CPU/GPU/memory/storage scores,
Cinebench 2026 CPU multi/single and GPU (Redshift), a GPU gaming benchmark
(Unigine Valley or similar), and CrystalDiskInfo drive health.

Once you have real numbers:

1. Copy `performance-data.json` to a new file (or overwrite it) with that build's
   `meta`, `hero`, `benchmarks`, `specs`, and `health` values.
2. Update `cpuRankChart` / `gpuRankChart` only if the CPU or GPU model changed —
   these are typical relative-performance comparisons against common chips/cards,
   not measured on the unit, and are labelled as such in the UI.
3. Update `games` FPS estimates for the new CPU/GPU pairing (e.g. via a tool like
   IObit's FPS Calculator) and swap `cover` paths to existing files in
   `assets/covers/` (add new cover art there if a new title is needed).
4. Leave `assets/` alone — logo, font, and intro video are shared across builds.
5. Copy the whole `Personalised Website` folder (or just swap the JSON if hosting
   from one place) to wherever the listing needs to point.

## JSON schema notes

- `benchmarks[].tier` / `everyday[].tier`: `"excellent" | "great" | "good"` — controls
  the colored pill. `everyday[].tierLabel` optionally overrides the pill text (e.g.
  `"Overkill"`) while keeping the `tier` color.
- `games[].stars`: 0–5, supports halves (e.g. `4.5`) — rendered as a partial gold fill.
- `specs[].icon`: one of `cpu | gpu | ram | storage | board | os` — maps to the icon
  set in `render.js`.
- `cpuRankChart.rows[].isThisBuild` / `gpuRankChart.rows[].isThisBuild`: marks the row
  to highlight; bar widths auto-scale to the highest `index` in the list.
- `cpuDistribution.bars[]`: `{x, y, h}` rectangles for the histogram (SVG viewBox
  `0 0 680 210`); `thisScoreX` positions the "this build" marker line.

## eBay Listing Template

`ebay-listing-template.html` + `ebay-listing-data.json` + `render-ebay.js`.

**This works differently from the performance card.** eBay strips `<script>`
tags (and often `<style>` blocks) from listing descriptions across its various
seller tools, so nothing that needs JS to run in-browser survives being pasted
in. The JSON → HTML step has to happen *before* the HTML reaches eBay:

1. Edit `ebay-listing-data.json` with the build's copy, stats, and asset URLs
   (all image/video URLs must be publicly hosted — e.g. on theflipflop.shop —
   eBay's description box only accepts image *URLs*, not uploads).
2. Run `node render-ebay.js` (defaults to `ebay-listing-data.json` →
   `ebay-listing-output.html`; both args are overridable).
3. Paste the **contents of `ebay-listing-output.html`** into eBay's listing
   description — not the template file, which still has `{{tokens}}` in it.

`ebay-listing-template.html` is entirely inline-styled (no `<style>` block) for
the same cross-tool-compatibility reason — like an HTML email.

**Admin tool integration:** the build-listing flow in `flipflop-admin` should
produce a JSON file matching `ebay-listing-data.json`'s shape (extending
whatever `generateListing()` already returns), then run the same
token-replacement logic — either by shelling out to `render-ebay.js` or a JS
port of it — to generate the final HTML for both the admin preview (`<iframe
srcDoc>`, same pattern already used in `app/selling/page.tsx`) and what gets
copied to eBay. Don't hand-maintain a second copy of this template inside the
admin app's source — keep this folder as the single source of truth and have
the admin tool read/render from it.
