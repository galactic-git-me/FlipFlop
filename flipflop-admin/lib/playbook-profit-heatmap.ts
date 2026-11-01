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

/** Profit uses green intensity; price and sales use red through amber to green. */
export function profitHeatmap(profit: number | null, min: number, max: number, metric: HeatmapMetric = "profit") {
  if (profit === null || !Number.isFinite(profit)) return null;
  const position = max > min ? Math.max(0, Math.min(1, (profit - min) / (max - min))) : 0.5;
  if (metric === "profit") {
    return {
      backgroundColor: `rgba(52, 211, 153, ${0.06 + position * 0.34})`,
      boxShadow: `inset 0 3px 0 rgba(52, 211, 153, ${0.3 + position * 0.7})`,
    };
  }
  const stops = [[248, 113, 113], [251, 191, 36], [52, 211, 153]];
  const [start, end] = position <= 0.5 ? [stops[0], stops[1]] : [stops[1], stops[2]];
  const fraction = position <= 0.5 ? position * 2 : (position - 0.5) * 2;
  const rgb = start.map((value, index) => Math.round(value + (end[index] - value) * fraction)).join(", ");
  return { backgroundColor: `rgba(${rgb}, 0.14)`, boxShadow: `inset 0 3px 0 rgb(${rgb})` };
}
