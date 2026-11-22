import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { verifyAdminToken } = vi.hoisted(() => ({
  verifyAdminToken: vi.fn(),
}));

vi.mock("@/lib/admin-session", () => ({
  ADMIN_SESSION_COOKIE: "admin_session",
  verifyAdminToken,
}));

import { proxy } from "../../proxy.ts";

describe("admin session proxy", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    delete process.env.PLAYWRIGHT_TEST;
    verifyAdminToken.mockReset();
  });

  it("explains when the browser did not send the session cookie", async () => {
    const response = await proxy(new NextRequest("https://admin.example.test/"));

    expect(response.headers.get("location")).toBe(
      "https://admin.example.test/login?reason=session_missing",
    );
  });

  it("explains when a present session cookie is invalid", async () => {
    verifyAdminToken.mockResolvedValue(null);
    const request = new NextRequest("https://admin.example.test/", {
      headers: { cookie: "admin_session=expired-token" },
    });

    const response = await proxy(request);

    expect(verifyAdminToken).toHaveBeenCalledWith("expired-token");
    expect(response.headers.get("location")).toBe(
      "https://admin.example.test/login?reason=session_invalid",
    );
  });

  it("allows a page only after the backend-issued token validates", async () => {
    verifyAdminToken.mockResolvedValue({ adminId: 7 });
    const request = new NextRequest("https://admin.example.test/", {
      headers: { cookie: "admin_session=valid-token" },
    });

    const response = await proxy(request);

    expect(verifyAdminToken).toHaveBeenCalledWith("valid-token");
    expect(response.headers.get("location")).toBeNull();
  });

  it("rejects unauthenticated admin API requests", async () => {
    const response = await proxy(new NextRequest("https://admin.example.test/api/assets-3d"));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Authentication required" });
  });

  it("rejects invalid sessions on admin API requests", async () => {
    verifyAdminToken.mockResolvedValue(null);
    const request = new NextRequest("https://admin.example.test/api/assets-3d", {
      headers: { cookie: "admin_session=expired-token" },
    });

    const response = await proxy(request);

    expect(response.status).toBe(401);
  });

  it("attaches the verified admin token to authenticated API requests", async () => {
    verifyAdminToken.mockResolvedValue({ adminId: 7 });
    const request = new NextRequest("https://admin.example.test/api/assets-3d", {
      headers: { cookie: "admin_session=valid-token" },
    });

    const response = await proxy(request);

    expect(response.headers.get("x-middleware-request-authorization")).toBe("Bearer valid-token");
  });

  it("rejects state-changing API requests without a same-origin Origin", async () => {
    verifyAdminToken.mockResolvedValue({ adminId: 7 });
    const request = new NextRequest("https://admin.example.test/api/assets-3d", {
      method: "POST",
      headers: { cookie: "admin_session=valid-token", origin: "https://evil.example.test" },
    });

    const response = await proxy(request);

    expect(response.status).toBe(403);
  });

  it("allows same-origin state-changing API requests with a valid session", async () => {
    verifyAdminToken.mockResolvedValue({ adminId: 7 });
    const request = new NextRequest("https://admin.example.test/api/assets-3d", {
      method: "POST",
      headers: { cookie: "admin_session=valid-token", origin: "https://admin.example.test" },
    });

    const response = await proxy(request);

    expect(response.headers.get("x-middleware-request-authorization")).toBe("Bearer valid-token");
  });

  it("does not allow the Playwright bypass to disable production API authentication", async () => {
    process.env.PLAYWRIGHT_TEST = "1";
    vi.stubEnv("NODE_ENV", "production");

    const response = await proxy(new NextRequest("https://admin.example.test/api/assets-3d"));

    expect(response.status).toBe(401);
  });

  it("does not allow the Playwright bypass to render production pages without a session", async () => {
    process.env.PLAYWRIGHT_TEST = "1";
    vi.stubEnv("NODE_ENV", "production");

    const response = await proxy(new NextRequest("https://admin.example.test/"));

    expect(response.headers.get("location")).toBe(
      "https://admin.example.test/login?reason=session_missing",
    );
  });

  it("preserves the Playwright bypass outside production", async () => {
    process.env.PLAYWRIGHT_TEST = "1";

    const response = await proxy(new NextRequest("https://admin.example.test/api/assets-3d"));

    expect(response.status).not.toBe(401);
  });
});
