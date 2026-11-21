import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "../../app/proxy-api/[...path]/route";

const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("same-origin API proxy redirects", () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it("does not forward the admin bearer token to another origin", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, {
      status: 302,
      headers: { location: "https://attacker.example/collect" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new NextRequest("https://admin.example.test/proxy-api/orders", {
      headers: { authorization: "Bearer test-admin-token" },
    }), context(["orders"]));

    expect(response.status).toBe(502);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("follows a same-origin redirect that remains under the backend API", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, {
        status: 307,
        headers: { location: "/api/orders/" },
      }))
      .mockResolvedValueOnce(new Response("{}", {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new NextRequest("https://admin.example.test/proxy-api/orders", {
      headers: { authorization: "Bearer test-admin-token" },
    }), context(["orders"]));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toMatch(/^http:\/\/localhost:4311\/api\/orders\/$/);
    expect(fetchMock.mock.calls[1][1].headers.get("authorization")).toBe("Bearer test-admin-token");
  });
});
