import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type UsageResult = { data?: Array<Record<string, unknown>>; has_more?: boolean; next_page?: string | null };

async function fetchReport(kind: "messages" | "web_search", start: string, end: string) {
  const key = process.env.ANTHROPIC_ADMIN_API_KEY;
  if (!key) throw new Error("ANTHROPIC_ADMIN_API_KEY is not configured on the admin server");
  const endpoint = kind === "messages" ? "messages" : "web_search";
  const rows: Array<Record<string, unknown>> = [];
  let page: string | null = null;
  for (let i = 0; i < 100; i++) {
    const query = new URLSearchParams({ starting_at: start, ending_at: end, bucket_width: "1d", limit: "31" });
    if (page) query.set("page", page);
    const response = await fetch(`https://api.anthropic.com/v1/organizations/${endpoint}/usage_report?${query}`, {
      headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "anthropic-beta": "organizations-usage-2025-04-22" },
      cache: "no-store",
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Anthropic usage API returned ${response.status}: ${body.slice(0, 240)}`);
    }
    const result = await response.json() as UsageResult;
    rows.push(...(result.data ?? []));
    if (!result.has_more || !result.next_page) break;
    page = result.next_page;
  }
  return rows;
}

export async function GET(request: NextRequest) {
  const now = new Date();
  const defaultStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const start = request.nextUrl.searchParams.get("start") ?? defaultStart.toISOString();
  const end = request.nextUrl.searchParams.get("end") ?? now.toISOString();
  if (!Number.isFinite(Date.parse(start)) || !Number.isFinite(Date.parse(end)) || Date.parse(start) >= Date.parse(end)) {
    return NextResponse.json({ error: "Invalid date range" }, { status: 400 });
  }
  try {
    const [messages, webSearch] = await Promise.all([
      fetchReport("messages", start, end),
      fetchReport("web_search", start, end).catch((error: unknown) => {
        // Older organizations may not have web-search reporting enabled.
        if (error instanceof Error && error.message.includes("returned 404")) return [];
        throw error;
      }),
    ]);
    return NextResponse.json({ messages, web_search: webSearch, start, end, fetched_at: new Date().toISOString() }, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load Anthropic usage";
    return NextResponse.json({ error: message }, { status: message.includes("not configured") ? 503 : 502 });
  }
}
