import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ConfigurationCommercialReview from "./ConfigurationCommercialReview";

const { calls } = vi.hoisted(() => ({
  calls: {
    configurations: vi.fn(),
    configuration: vi.fn(),
    approveConfiguration: vi.fn(),
    importConfiguration: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({ api: { commercialReadiness: calls } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const detail = {
  request_id: 7,
  playbook_id: 1,
  name: "Gaming",
  curated_build_id: "FF-GVG-01",
  budget_tier: "Budget",
  base_policy_version: 0,
  draft_id: null,
  definition_sha256: "a".repeat(64),
  draft: { version: 1, checkout_enabled: false },
  draft_errors: [],
  policy_blockers: [],
  parts: [],
  checkout_enabled: false,
  price_review_sha256: "b".repeat(64),
  assessment: {
    modes: {
      fast_track: { offerable: true, price_gbp: "1200", contribution_gbp: "160", delivery_working_days: 3, reason: "Current evidence supports this mode." },
      standard: { offerable: true, price_gbp: "1100", contribution_gbp: "140", delivery_working_days: 5, reason: "Current evidence supports this mode." },
      flexible: { offerable: true, price_gbp: "1000", contribution_gbp: "120", delivery_working_days: 10, reason: "Current evidence supports this mode." },
    },
  },
};

function setup(value = detail) {
  calls.configurations.mockResolvedValue({
    items: [{ request_id: 7, playbook_name: "Gaming", curated_build_id: "FF-GVG-01", budget_tier: "Budget", component_count: 7, checkout_enabled: false }],
  });
  calls.configuration.mockResolvedValue(value);
  render(<ConfigurationCommercialReview />);
}

it("shows generated prices without manual cost fields and requires explicit exact-build approval", async () => {
  setup();
  fireEvent.click(await screen.findByRole("button", { name: /Gaming · FF-GVG-01/ }));

  expect(await screen.findByText(/there are no price or cost fields to enter/i)).toBeInTheDocument();
  expect(screen.getByText("£1,200.00")).toBeInTheDocument();
  expect(screen.queryByLabelText(/outbound delivery/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Save and assess/i })).not.toBeInTheDocument();

  const approve = await screen.findByRole("button", { name: "Approve the calculated prices for this exact build" });
  expect(approve).toBeEnabled();
  calls.approveConfiguration.mockResolvedValue({ checkout_enabled: true, policy_version: 1, assessment: detail.assessment });
  fireEvent.click(approve);
  await waitFor(() => expect(calls.approveConfiguration).toHaveBeenCalledWith(7, "b".repeat(64)));
});

it("does not enable approval when any delivery mode lacks current evidence", async () => {
  setup({
    ...detail,
    assessment: { modes: { ...detail.assessment.modes, flexible: { offerable: false, price_gbp: "1000", contribution_gbp: "0", delivery_working_days: 10, reason: "Current stock is unavailable." } } },
  });
  fireEvent.click(await screen.findByRole("button", { name: /Gaming · FF-GVG-01/ }));
  expect(await screen.findByRole("button", { name: "Approve the calculated prices for this exact build" })).toBeDisabled();
  expect(calls.approveConfiguration).not.toHaveBeenCalled();
});
