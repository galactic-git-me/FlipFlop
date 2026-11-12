import type { BookCell } from "./playbook-book";

export type HeatmapMetric = "profit" | "price" | "sales";

function finite(value: string | number | null | undefined) {
  if (value == null || value === "") return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

export function heatmapValue(cell: BookCell, metric: HeatmapMetric) {
  if (metric === "sales") {
    // Only exact-build sold comparisons; component counts are not PC sales.
    const urls = new Set(cell.pricing_guidance?.market_advice.comparisons
      ?.filter(row => row.kind === "sold" && row.url).map(row => row.url));
    return urls.size ? urls.size : null;
  }
  const isLive = cell.is_live && cell.checkout_enabled && cell.availability_status === "in_stock";
  const standard = (isLive ? cell.approved_offer : cell.offer)?.delivery_products.standard;
  return finite(metric === "price"
    ? isLive ? cell.approved_price_gbp : cell.pricing_guidance?.estimated_price_gbp ?? standard?.recommended_price_gbp
    : isLive ? standard?.estimated_profit_gbp : cell.pricing_guidance?.estimated_profit_gbp ?? standard?.estimated_profit_gbp);
}

export type HeatmapScale = { low: number; middle: number; high: number; comparative: boolean };

function percentile(sorted: number[], fraction: number) {
  const position = (sorted.length - 1) * fraction;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}

export function heatmapScale(values: number[], metric: HeatmapMetric): HeatmapScale {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (metric === "profit") {
    return { low: Math.min(0, sorted[0] ?? 0), middle: 0, high: Math.max(0, sorted[sorted.length - 1] ?? 0), comparative: true };
  }
  if (!sorted.length) return { low: 0, middle: 0, high: 0, comparative: false };
  return {
    low: percentile(sorted, 0.25),
    middle: percentile(sorted, 0.5),
    high: percentile(sorted, 0.75),
    comparative: false,
  };
}

function blend(start: number[], end: number[], position: number) {
  return start.map((channel, index) => Math.round(channel + (end[index] - channel) * position));
}

export function heatmapColor(value: number, scale: HeatmapScale) {
  const green = [52, 211, 153];
  const amber = [251, 191, 36];
  const red = [248, 113, 113];
  if (scale.comparative) {
    if (value === 0) return amber;
    if (value < 0) {
      const span = Math.abs(scale.low);
      return span === 0 ? amber : blend(green, amber, Math.max(0, Math.min(1, (value - scale.low) / span)));
    }
    return scale.high === 0 ? amber : blend(amber, red, Math.max(0, Math.min(1, value / scale.high)));
  }
  if (scale.low === scale.high) return amber;
  if (value <= scale.low) return green;
  if (value >= scale.high) return red;
  if (value <= scale.middle) {
    const span = scale.middle - scale.low;
    return span === 0 ? amber : blend(green, amber, (value - scale.low) / span);
  }
  const span = scale.high - scale.middle;
  return span === 0 ? amber : blend(amber, red, (value - scale.middle) / span);
}

export function heatmapCssColor(color: number[]) {
  return `rgb(${color.join(", ")})`;
}

export function profitHeatmap(value: number | null, scale: HeatmapScale) {
  if (value === null || !Number.isFinite(value)) return null;
  const color = heatmapColor(value, scale);
  return {
    backgroundColor: `rgba(${color.join(", ")}, 0.14)`,
    boxShadow: `inset 0 3px 0 ${heatmapCssColor(color)}`,
  };
}
