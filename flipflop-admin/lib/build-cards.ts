import { ManualBuild } from "./api";

const W = 1536;
const H = 1024;
const NASA_FONT = "FlipFlopNASA";

let nasaFontLoaded: Promise<void> | null = null;
function loadNasaFont(): Promise<void> {
  if (!nasaFontLoaded) {
    nasaFontLoaded = (async () => {
      const face = new FontFace(NASA_FONT, "url(/fonts/Nasa.ttf)");
      await face.load();
      document.fonts.add(face);
    })();
  }
  return nasaFontLoaded;
}

// ─── Real Lucide icon path data (extracted from node_modules/lucide-react),
// rasterized onto canvas via an offscreen SVG image rather than hand-drawn
// approximations, so spec rows show actual recognizable icons. ────────────
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

function iconSvgDataUrl(name: keyof typeof ICONS, color: string): string {
  const nodes = ICONS[name];
  const body = nodes
    .map(([tag, attrs]) => {
      const attrStr = Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(" ");
      return `<${tag} ${attrStr} />`;
    })
    .join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const iconCache = new Map<string, Promise<HTMLImageElement>>();
function loadIcon(name: keyof typeof ICONS, color: string): Promise<HTMLImageElement> {
  const key = `${name}:${color}`;
  if (!iconCache.has(key)) {
    iconCache.set(
      key,
      new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = iconSvgDataUrl(name, color);
      })
    );
  }
  return iconCache.get(key)!;
}

// ─── Spec rows shared by both cards ────────────────────────────────────────

function componentBySlot(build: ManualBuild, slots: string[]): { name: string } | null {
  for (const slot of slots) {
    const c = build.components.find((c) => c.slot === slot);
    if (c) return { name: c.name };
  }
  return null;
}

const SPEC_ROWS: { label: string; slots: string[]; icon: keyof typeof ICONS }[] = [
  { label: "Processor", slots: ["cpu"], icon: "cpu" },
  { label: "Graphics", slots: ["gpu"], icon: "gpu" },
  { label: "Memory", slots: ["ram"], icon: "memory" },
  { label: "Storage", slots: ["ssd", "storage"], icon: "storage" },
  { label: "Motherboard", slots: ["motherboard"], icon: "motherboard" },
  { label: "Cooling", slots: ["cpu_cooler", "cooler"], icon: "cooling" },
  { label: "Airflow", slots: ["case_fans", "fans"], icon: "airflow" },
  { label: "Power Supply", slots: ["psu"], icon: "power" },
  { label: "Operating System", slots: ["operating_system"], icon: "os" },
];

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function brushedMetalTexture(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number) {
  ctx.save();
  roundRect(ctx, x, y, w, h, 40);
  ctx.clip();
  for (let i = 0; i < 260; i++) {
    const ly = y + Math.random() * h;
    ctx.strokeStyle = `rgba(255,255,255,${Math.random() * 0.035})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, ly);
    ctx.lineTo(x + w, ly + (Math.random() - 0.5) * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function diamondMarker(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(Math.PI / 4);
  ctx.fillStyle = "#5b6672";
  ctx.fillRect(-size / 2, -size / 2, size, size);
  ctx.restore();
}

export async function drawRegistrationPlate(canvas: HTMLCanvasElement, build: ManualBuild, logo: HTMLImageElement | null) {
  await loadNasaFont();
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;

  // Brushed dark metal ground
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#20252c");
  bg.addColorStop(0.5, "#171b22");
  bg.addColorStop(1, "#20252c");
  ctx.fillStyle = bg;
  roundRect(ctx, 0, 0, W, H, 40);
  ctx.fill();
  brushedMetalTexture(ctx, 0, 0, W, H);

  // Glowing corner-to-corner border (orange → blue)
  ctx.save();
  const border = ctx.createLinearGradient(0, 0, W, H);
  border.addColorStop(0, "#ff9500");
  border.addColorStop(1, "#00b8ff");
  ctx.strokeStyle = border;
  ctx.lineWidth = 5;
  ctx.shadowColor = "#00b8ff";
  ctx.shadowBlur = 22;
  roundRect(ctx, 16, 16, W - 32, H - 32, 34);
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = "rgba(255,255,255,0.5)";
  roundRect(ctx, 16, 16, W - 32, H - 32, 34);
  ctx.stroke();
  ctx.restore();

  // Top-center decorative slot
  ctx.fillStyle = "rgba(0,0,0,0.35)";
  roundRect(ctx, W / 2 - 130, 62, 260, 14, 7);
  ctx.fill();

  // Corner screws
  for (const [cx, cy] of [[74, 74], [W - 74, 74], [74, H - 74], [W - 74, H - 74]] as const) {
    const screwGrad = ctx.createRadialGradient(cx - 5, cy - 5, 2, cx, cy, 18);
    screwGrad.addColorStop(0, "#4a5361");
    screwGrad.addColorStop(1, "#0d1015");
    ctx.fillStyle = screwGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, 17, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,0.6)";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(cx - 10, cy);
    ctx.lineTo(cx + 10, cy);
    ctx.moveTo(cx, cy - 10);
    ctx.lineTo(cx, cy + 10);
    ctx.stroke();
  }

  // Logo cube
  if (logo) {
    const logoH = 210;
    const logoW = logo.width * (logoH / logo.height);
    ctx.drawImage(logo, 96, 96, logoW, logoH);
    ctx.font = `700 34px ${NASA_FONT}, ui-sans-serif`;
    const grad = ctx.createLinearGradient(96, 0, 96 + 300, 0);
    grad.addColorStop(0, "#ff9500");
    grad.addColorStop(1, "#00b8ff");
    ctx.fillStyle = grad;
    ctx.fillText("FLIPFLOP", 96, 96 + logoH + 44);
    ctx.font = "500 19px ui-monospace, monospace";
    ctx.fillStyle = "#8a95a3";
    ctx.fillText("BEAUTIFUL MACHINES.", 96, 96 + logoH + 76);
    ctx.fillText("BUILT TO BE ADMIRED.", 96, 96 + logoH + 100);
  }

  const leftCol = logo ? 490 : 96;
  const rightEdge = W - 100;

  // Header eyebrow with orange rules either side
  ctx.textAlign = "left";
  ctx.font = "600 26px ui-monospace, monospace";
  const headerText = "FLIPFLOP BUILD REGISTRY";
  const headerW = ctx.measureText(headerText).width;
  const headerCx = leftCol + (rightEdge - leftCol) / 2;
  ctx.fillStyle = "#9aa5b1";
  ctx.textAlign = "center";
  ctx.fillText(headerText, headerCx, 120);
  ctx.strokeStyle = "#ff9500";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(leftCol, 112);
  ctx.lineTo(headerCx - headerW / 2 - 24, 112);
  ctx.stroke();
  ctx.strokeStyle = "#00b8ff";
  ctx.beginPath();
  ctx.moveTo(headerCx + headerW / 2 + 24, 112);
  ctx.lineTo(rightEdge, 112);
  ctx.stroke();
  ctx.textAlign = "left";

  const dividerGrad = ctx.createLinearGradient(leftCol, 0, rightEdge, 0);
  dividerGrad.addColorStop(0, "#ff9500");
  dividerGrad.addColorStop(1, "#00b8ff");

  // Divider sits directly under the header — the gap below it is the
  // placeholder for the big NASA-font build name, kept clear of the
  // eyebrow/header row above and the spec rows below.
  const headerDividerY = 172;
  ctx.strokeStyle = dividerGrad;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(leftCol, headerDividerY);
  ctx.lineTo(rightEdge, headerDividerY);
  ctx.stroke();
  diamondMarker(ctx, (leftCol + rightEdge) / 2, headerDividerY, 12);

  // Build name — big embossed metal title, filling the gap below the divider
  const title = build.name.toUpperCase();
  const titleBaseline = 300;
  ctx.font = `800 100px ${NASA_FONT}, ui-sans-serif`;
  ctx.fillStyle = "rgba(0,0,0,0.55)";
  ctx.fillText(title, leftCol + 2, titleBaseline + 3);
  const nameGrad = ctx.createLinearGradient(0, titleBaseline - 76, 0, titleBaseline + 4);
  nameGrad.addColorStop(0, "#f2f4f6");
  nameGrad.addColorStop(0.55, "#c3ccd6");
  nameGrad.addColorStop(1, "#9aa5b1");
  ctx.fillStyle = nameGrad;
  ctx.fillText(title, leftCol, titleBaseline);

  // Spec rows — the printed plate's fixed field list: Commissioned,
  // Processor, Graphics, Memory, Storage, Motherboard, Power. Cooling and
  // Airflow/OS stay off the plate (they're on the spec card instead).
  const PLATE_LABEL_OVERRIDES: Record<string, string> = { "Power Supply": "Power" };
  const rows: [string, string][] = [
    ["Commissioned", new Date(build.created_at).toLocaleDateString("en-GB", { month: "long", year: "numeric" })],
  ];
  for (const row of SPEC_ROWS) {
    if (row.label === "Airflow" || row.label === "Operating System" || row.label === "Cooling") continue;
    const comp = componentBySlot(build, row.slots);
    if (comp) rows.push([PLATE_LABEL_OVERRIDES[row.label] ?? row.label, comp.name]);
  }

  let y = 400;
  const rowH = 60;
  for (const [label, value] of rows) {
    ctx.font = "700 25px ui-monospace, monospace";
    ctx.fillStyle = "#ff9500";
    ctx.fillText(`${label.toUpperCase()}:`, leftCol, y);
    ctx.font = "500 25px ui-monospace, monospace";
    ctx.fillStyle = "#dfe4e9";
    ctx.fillText(value, leftCol + 330, y);
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.beginPath();
    ctx.moveTo(leftCol, y + 17);
    ctx.lineTo(rightEdge - 24, y + 17);
    ctx.stroke();
    ctx.fillStyle = "#4a5361";
    ctx.beginPath();
    ctx.arc(rightEdge - 8, y + 12, 4, 0, Math.PI * 2);
    ctx.fill();
    y += rowH;
  }

  ctx.font = "700 25px ui-monospace, monospace";
  ctx.fillStyle = "#ff9500";
  ctx.fillText("BUILDER:", leftCol, y + 22);
  ctx.strokeStyle = "rgba(255,255,255,0.3)";
  ctx.beginPath();
  ctx.moveTo(leftCol + 200, y + 14);
  ctx.lineTo(rightEdge, y + 14);
  ctx.stroke();

  y += 60;
  ctx.strokeStyle = dividerGrad;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(leftCol, y);
  ctx.lineTo(rightEdge, y);
  ctx.stroke();
  diamondMarker(ctx, (leftCol + rightEdge) / 2, y, 12);

  // Footer
  ctx.textAlign = "center";
  ctx.font = "600 25px ui-monospace, monospace";
  ctx.fillStyle = "#ff9500";
  const a = "BEAUTIFUL ";
  const b = "MACHINES. BUILT TO ";
  const c = "BE ADMIRED.";
  const totalW = ctx.measureText(a + b + c).width;
  let fx = W / 2 - totalW / 2;
  const footerY = H - 56;
  ctx.textAlign = "left";
  ctx.fillStyle = "#ff9500";
  ctx.fillText(a, fx, footerY);
  fx += ctx.measureText(a).width;
  ctx.fillStyle = "#c3ccd6";
  ctx.fillText(b, fx, footerY);
  fx += ctx.measureText(b).width;
  ctx.fillStyle = "#00b8ff";
  ctx.fillText(c, fx, footerY);
  ctx.textAlign = "left";
}

export async function drawSpecCard(canvas: HTMLCanvasElement, build: ManualBuild, logo: HTMLImageElement | null) {
  await loadNasaFont();
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;

  ctx.fillStyle = "#060608";
  ctx.fillRect(0, 0, W, H);

  const vg = ctx.createRadialGradient(W / 2, H / 2, H / 4, W / 2, H / 2, W / 1.1);
  vg.addColorStop(0, "rgba(0,184,255,0.05)");
  vg.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, W, H);

  // Decorative circuit-trace accents, top-right and bottom-left
  drawCircuitTraces(ctx, W - 420, -40, 460, 320, "#ff9500");
  drawCircuitTraces(ctx, -40, H - 280, 460, 320, "#00b8ff");

  const leftColW = 360;

  if (logo) {
    const logoH = 170;
    const logoW = logo.width * (logoH / logo.height);
    ctx.drawImage(logo, 60, 60, logoW, logoH);
    ctx.font = `700 30px ${NASA_FONT}, ui-sans-serif`;
    const grad = ctx.createLinearGradient(60, 0, 60 + 260, 0);
    grad.addColorStop(0, "#ff9500");
    grad.addColorStop(1, "#00b8ff");
    ctx.fillStyle = grad;
    ctx.fillText("FLIPFLOP", 60, 60 + logoH + 40);
    ctx.font = "500 18px ui-monospace, monospace";
    ctx.fillStyle = "#8a95a3";
    ctx.fillText("BEAUTIFUL MACHINES.", 60, 60 + logoH + 70);
    ctx.fillText("BUILT TO BE ADMIRED.", 60, 60 + logoH + 92);
  }

  const vgrad = ctx.createLinearGradient(0, 60, 0, H - 60);
  vgrad.addColorStop(0, "#ff9500");
  vgrad.addColorStop(1, "#00b8ff");
  ctx.strokeStyle = vgrad;
  ctx.globalAlpha = 0.4;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(leftColW, 60);
  ctx.lineTo(leftColW, H - 60);
  ctx.stroke();
  ctx.globalAlpha = 1;

  const rx = leftColW + 60;

  ctx.font = "600 22px ui-monospace, monospace";
  ctx.fillStyle = "#c3ccd6";
  ctx.fillText("FLIPFLOP  //  SYSTEM SPECIFICATION", rx, 100);

  ctx.font = `800 88px ${NASA_FONT}, ui-sans-serif`;
  const nameGrad = ctx.createLinearGradient(rx, 0, W - 60, 0);
  nameGrad.addColorStop(0, "#ff9500");
  nameGrad.addColorStop(1, "#00b8ff");
  ctx.fillStyle = nameGrad;
  ctx.fillText(build.name.toUpperCase(), rx, 190);

  const rows = SPEC_ROWS.map((row) => ({ ...row, comp: componentBySlot(build, row.slots) })).filter((r) => r.comp);
  const icons = await Promise.all(rows.map((r) => loadIcon(r.icon, "#ff9500")));

  let y = 250;
  const rowH = (H - 250 - 50) / Math.max(rows.length, 1);
  rows.forEach((row, i) => {
    ctx.strokeStyle = "rgba(255,140,0,0.5)";
    ctx.lineWidth = 2;
    roundRect(ctx, rx, y, 56, 56, 10);
    ctx.stroke();
    ctx.drawImage(icons[i], rx + 12, y + 12, 32, 32);

    ctx.font = "600 21px ui-monospace, monospace";
    ctx.fillStyle = "#c3ccd6";
    ctx.fillText(row.label.toUpperCase(), rx + 80, y + 24);

    ctx.font = "500 26px ui-monospace, monospace";
    ctx.fillStyle = "#eef1f4";
    ctx.fillText(row.comp!.name, rx + 340, y + 26);

    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.beginPath();
    ctx.moveTo(rx, y + rowH - 16);
    ctx.lineTo(W - 76, y + rowH - 16);
    ctx.stroke();
    const dotGrad = ctx.createLinearGradient(W - 76, 0, W - 60, 0);
    dotGrad.addColorStop(0, "#ff9500");
    dotGrad.addColorStop(1, "#00b8ff");
    ctx.fillStyle = dotGrad;
    ctx.beginPath();
    ctx.arc(W - 66, y + rowH - 16, 5, 0, Math.PI * 2);
    ctx.fill();

    y += rowH;
  });
}

function drawCircuitTraces(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, color: string) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.22;
  ctx.lineWidth = 1.5;
  const cols = 5;
  const rows = 4;
  for (let i = 0; i < cols; i++) {
    const lx = x + (w / cols) * i + Math.random() * 20;
    const ly1 = y + Math.random() * h * 0.4;
    const ly2 = ly1 + h * 0.3 + Math.random() * h * 0.2;
    ctx.beginPath();
    ctx.moveTo(lx, ly1);
    ctx.lineTo(lx, ly2);
    ctx.lineTo(lx + (Math.random() > 0.5 ? 40 : -40), ly2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(lx, ly1, 3, 0, Math.PI * 2);
    ctx.fill();
  }
  for (let i = 0; i < rows; i++) {
    const ly = y + (h / rows) * i + Math.random() * 20;
    ctx.beginPath();
    ctx.moveTo(x, ly);
    ctx.lineTo(x + w * 0.5 + Math.random() * w * 0.3, ly);
    ctx.stroke();
  }
  ctx.restore();
}

export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))), "image/png");
  });
}

export function loadLogo(): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = "/pics/flipflop-glow-transparent.png";
  });
}
