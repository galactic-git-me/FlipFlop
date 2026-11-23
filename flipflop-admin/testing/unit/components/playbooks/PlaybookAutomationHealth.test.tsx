import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PlaybookAutomationHealth from "../../../../components/playbooks/PlaybookAutomationHealth.tsx";

const { automation } = vi.hoisted(() => ({ automation: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { commercialReadiness: { automation } } }));

const status = {
  setting_enabled: true,
  registered: true,
  enabled: true,
  next_run_at: null,
  scheduled_latest: {
    job_id: "job-1",
    mode: "refresh",
    status: "succeeded",
    phase: "Playbook proposals refreshed",
    started_at: "2026-11-23T10:00:00Z",
    error: null,
  },
  scheduled_rebuild_latest: null,
  manual_latest: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("shows progress and a fresh timestamp when status is manually checked", async () => {
  let finishCheck!: (value: typeof status) => void;
  automation
    .mockResolvedValueOnce(status)
    .mockImplementationOnce(() => new Promise((resolve) => { finishCheck = resolve; }));

  render(<PlaybookAutomationHealth />);
  await screen.findByText(/Last scheduled run: succeeded/);
  fireEvent.click(screen.getByRole("button", { name: "Check status now" }));

  expect(await screen.findByRole("button", { name: "Checking status…" })).toBeDisabled();
  expect(screen.getByText("Refreshing scheduler status…")).toBeInTheDocument();
  finishCheck(status);

  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Status checked at"));
  expect(screen.getByRole("button", { name: "Check status now" })).toBeEnabled();
});

it("shows a visible error if the status check fails", async () => {
  automation
    .mockResolvedValueOnce(status)
    .mockRejectedValueOnce(new Error("API timed out"));

  render(<PlaybookAutomationHealth />);
  await screen.findByText(/Last scheduled run: succeeded/);
  fireEvent.click(screen.getByRole("button", { name: "Check status now" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("API timed out");
  expect(screen.getByRole("button", { name: "Check status now" })).toBeEnabled();
});
