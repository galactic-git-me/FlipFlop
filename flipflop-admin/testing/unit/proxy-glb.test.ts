import { beforeEach, describe, expect, it, vi } from "vitest";

const { verifyAdminToken } = vi.hoisted(() => ({ verifyAdminToken: vi.fn() }));
vi.mock("@/lib/admin-session", () => ({
  ADMIN_SESSION_COOKIE: "admin_session",
  verifyAdminToken,
}));

import { GET, isAllowedProxyMediaUrl } from "../../app/api/proxy-glb/route.ts";

describe("GLB proxy security", () => {
  beforeEach(() => {
    verifyAdminToken.mockReset();
    vi.unstubAllGlobals();
  });

  it("allows only production media and the local development media endpoint", () => {
    expect(isAllowedProxyMediaUrl("https://theflipflop.shop/media/model.glb")).toBe(true);
    expect(isAllowedProxyMediaUrl("https://i.ebayimg.com/images/g/example.jpg")).toBe(true);
    expect(isAllowedProxyMediaUrl("http://127.0.0.1:4311/api/3d-media/model.glb")).toBe(true);
    expect(isAllowedProxyMediaUrl("http://127.0.0.1:8000/private.glb")).toBe(false);
    expect(isAllowedProxyMediaUrl("https://attacker.example/model.glb")).toBe(false);
    expect(isAllowedProxyMediaUrl("http://169.254.169.254/latest/meta-data.glb")).toBe(false);
    expect(isAllowedProxyMediaUrl("https://theflipflop.shop.evil.example/media/model.glb")).toBe(false);
  });

  it("requires a verified admin session before fetching a source", async () => {
    verifyAdminToken.mockResolvedValue(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request(
      "https://admin.example.test/api/proxy-glb?url=https%3A%2F%2Ftheflipflop.shop%2Fmedia%2Fmodel.glb",
    ));

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects arbitrary URL targets before fetching", async () => {
    verifyAdminToken.mockResolvedValue({ adminId: 7 });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request(
      "https://admin.example.test/api/proxy-glb?url=http%3A%2F%2F127.0.0.1%3A4311%2Fadmin.glb",
      { headers: { cookie: "admin_session=valid-token" } },
    ));

    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects redirects to hosts outside the media allowlist", async () => {
    verifyAdminToken.mockResolvedValue({ adminId: 7 });
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, {
      status: 302,
      headers: { location: "http://169.254.169.254/latest/meta-data.glb" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request(
      "https://admin.example.test/api/proxy-glb?url=https%3A%2F%2Ftheflipflop.shop%2Fmedia%2Fmodel.glb",
      { headers: { cookie: "admin_session=valid-token" } },
    ));

    expect(response.status).toBe(502);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
