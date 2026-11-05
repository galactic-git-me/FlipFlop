import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { verifyAdminToken } = vi.hoisted(() => ({
  verifyAdminToken: vi.fn(),
}));

vi.mock("@/lib/admin-session", () => ({
  ADMIN_SESSION_COOKIE: "admin_session",
  verifyAdminToken,
}));

import { proxy } from "./proxy";

describe("admin session proxy", () => {
  beforeEach(() => {
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
});
