import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "../../app/api/anthropic-usage/route";

describe("Anthropic usage report route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("uses the documented messages and web search report paths", async () => {
    vi.stubEnv("ANTHROPIC_ADMIN_API_KEY", "test-admin-key");
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ data: [], has_more: false }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new NextRequest("https://admin.example.test/api/anthropic-usage"));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual(expect.arrayContaining([
      expect.stringMatching(/^https:\/\/api\.anthropic\.com\/v1\/organizations\/usage_report\/messages\?/),
      expect.stringMatching(/^https:\/\/api\.anthropic\.com\/v1\/organizations\/usage_report\/web_search\?/),
    ]));
  });
});
