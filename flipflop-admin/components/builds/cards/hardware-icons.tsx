// Real Lucide icon path data (same paths used by the old canvas renderer in
// lib/build-cards.ts) — kept inline rather than importing lucide-react icons
// by name, since not every glyph used here (e.g. "gpu") has a matching
// lucide-react export.
type IconNode = readonly [string, Record<string, string>];

const ICONS: Record<string, IconNode[]> = {
  cpu: [
    ["path", { d: "M12 20v2" }], ["path", { d: "M12 2v2" }],
    ["path", { d: "M17 20v2" }], ["path", { d: "M17 2v2" }],
    ["path", { d: "M2 12h2" }], ["path", { d: "M2 17h2" }], ["path", { d: "M2 7h2" }],
    ["path", { d: "M20 12h2" }], ["path", { d: "M20 17h2" }], ["path", { d: "M20 7h2" }],
    ["path", { d: "M7 20v2" }], ["path", { d: "M7 2v2" }],
    ["rect", { x: "4", y: "4", width: "16", height: "16", rx: "2" }],
    ["rect", { x: "8", y: "8", width: "8", height: "8", rx: "1" }],
  ],
  gpu: [
    ["path", { d: "M2 17h18a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H2" }],
    ["path", { d: "M2 21V3" }],
    ["path", { d: "M7 17v3a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1v-3" }],
    ["circle", { cx: "16", cy: "11", r: "2" }],
    ["circle", { cx: "8", cy: "11", r: "2" }],
  ],
  memory: [
    ["path", { d: "M12 12v-2" }], ["path", { d: "M12 18v-2" }],
    ["path", { d: "M16 12v-2" }], ["path", { d: "M16 18v-2" }],
    ["path", { d: "M2 11h1.5" }], ["path", { d: "M20 18v-2" }],
    ["path", { d: "M20.5 11H22" }], ["path", { d: "M4 18v-2" }],
    ["path", { d: "M8 12v-2" }], ["path", { d: "M8 18v-2" }],
    ["rect", { x: "2", y: "6", width: "20", height: "10", rx: "2" }],
  ],
  storage: [
    ["path", { d: "M10 16h.01" }],
    ["path", { d: "M2.212 11.577a2 2 0 0 0-.212.896V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5.527a2 2 0 0 0-.212-.896L18.55 5.11A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" }],
    ["path", { d: "M21.946 12.013H2.054" }],
    ["path", { d: "M6 16h.01" }],
  ],
  motherboard: [
    ["rect", { width: "18", height: "18", x: "3", y: "3", rx: "2" }],
    ["path", { d: "M11 9h4a2 2 0 0 0 2-2V3" }],
    ["circle", { cx: "9", cy: "9", r: "2" }],
    ["path", { d: "M7 21v-4a2 2 0 0 1 2-2h4" }],
    ["circle", { cx: "15", cy: "15", r: "2" }],
  ],
  cooling: [
    ["path", { d: "m10 20-1.25-2.5L6 18" }], ["path", { d: "M10 4 8.75 6.5 6 6" }],
    ["path", { d: "m14 20 1.25-2.5L18 18" }], ["path", { d: "m14 4 1.25 2.5L18 6" }],
    ["path", { d: "m17 21-3-6h-4" }], ["path", { d: "m17 3-3 6 1.5 3" }],
    ["path", { d: "M2 12h6.5L10 9" }], ["path", { d: "m20 10-1.5 2 1.5 2" }],
    ["path", { d: "M22 12h-6.5L14 15" }], ["path", { d: "m4 10 1.5 2L4 14" }],
    ["path", { d: "m7 21 3-6-1.5-3" }], ["path", { d: "m7 3 3 6h4" }],
  ],
  airflow: [
    ["path", { d: "M10.827 16.379a6.082 6.082 0 0 1-8.618-7.002l5.412 1.45a6.082 6.082 0 0 1 7.002-8.618l-1.45 5.412a6.082 6.082 0 0 1 8.618 7.002l-5.412-1.45a6.082 6.082 0 0 1-7.002 8.618l1.45-5.412Z" }],
    ["path", { d: "M12 12v.01" }],
  ],
  power: [
    ["path", { d: "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" }],
  ],
  os: [
    ["rect", { width: "20", height: "14", x: "2", y: "3", rx: "2" }],
    ["line", { x1: "8", x2: "16", y1: "21", y2: "21" }],
    ["line", { x1: "12", x2: "12", y1: "17", y2: "21" }],
  ],
};

export type HardwareIconName = keyof typeof ICONS;

export function HardwareIcon({ name, className }: { name: HardwareIconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {ICONS[name].map(([tag, attrs], i) => {
        const Tag = tag as "path" | "rect" | "circle" | "line";
        return <Tag key={i} {...attrs} />;
      })}
    </svg>
  );
}
