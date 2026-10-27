import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import Cases3DPriorityPage from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/three-d-workflow-nav", () => ({ ThreeDWorkflowNav: () => null }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("shows the API failure instead of calling slice on an error object", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ error: "Backend returned 500" }), { status: 500 },
  )));
  render(<Cases3DPriorityPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Backend returned 500");
});

it("rejects a non-array success response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ cases: [] }))));
  render(<Cases3DPriorityPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("expected a case list");
});

it("loads empty case arrays successfully", async () => {
  const fetchMock = vi.fn().mockImplementation(async () => new Response("[]"));
  vi.stubGlobal("fetch", fetchMock);
  render(<Cases3DPriorityPage />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  await screen.findByText("All popular cases have 3D models!");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("shows failures when loading completed models", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(new Response("[]"))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Models unavailable" }), { status: 503 })));
  render(<Cases3DPriorityPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Models unavailable");
});
