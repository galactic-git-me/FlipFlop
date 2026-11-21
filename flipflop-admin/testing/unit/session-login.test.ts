import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "../../app/api/session/login/route";

describe("admin session cookie handling", () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it("stores the backend token only in the httpOnly session cookie", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ access_token: "test-admin-token" }),
      { status: 200, headers: { "content-type": "application/json" } },
    )));

    const request = new NextRequest("https://admin.example.test/api/session/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: "admin@example.test", password: "test-password" }),
    });
    const response = await POST(request);
    const cookies = response.cookies.getAll();

    const sessionCookie = cookies.find((cookie) => cookie.name === "admin_session");
    const legacyCookie = cookies.find((cookie) => cookie.name === "admin_token");
    expect(sessionCookie?.httpOnly).toBe(true);
    expect(legacyCookie?.value).toBe("");
  });
});
