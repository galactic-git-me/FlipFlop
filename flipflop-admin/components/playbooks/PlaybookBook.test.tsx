import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import PlaybookBook from "./AdvancedPlaybookBook";
import type { BookCell, PlaybookBook as BookData } from "@/lib/playbook-book";
const { book } = vi.hoisted(() => ({ book: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { commercialReadiness: { book } } }));
vi.mock("./CommercialReviewWorkspace", () => ({
  default: ({ contextCellId }: { contextCellId: string }) => (
    <p>Review tools for {contextCellId}</p>
  ),
}));
vi.mock("./PlaybookAutomationHealth", () => ({
  default: () => <p>Automation run health</p>,
}));
function cell(id: string, type: string, tier: string): BookCell {
  return {
    cell_id: id,
    segment_id: 1,
    customer_type: type,
    budget_tier: tier,
    name: `${type} ${tier} build`,
    definition: { components: { cpu: "Authored CPU" } },
    offer: null,
    approved_offer: null,
    offer_basis: "no_offer",
    proposal_status: null,
    proposal_observed_at: null,
    approved_price_gbp: null,
    market: null,
    active_build_market_gbp: null,
    walk_away_price_gbp: null,
    pricing_gaps: ["An approved cell minimum selling price matching the current build and policy is not recorded"],
    is_live: false,
    checkout_enabled: false,
    availability_status: "not_configured",
    software_profile: null,
    policy_version: null,
    history: [],
    history_coverage: "Recorded events only",
    distribution: [
      {
        channel: "storefront",
        status: "offline",
        source: "Cell publication record",
        external_id: id,
      },
    ],
    distribution_coverage: "Exact cell links only",
  };
}
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});
it("keeps the same matrix and selected cell while changing pages and density", async () => {
  const data: BookData = {
    observed_at: "2026-10-15T12:00:00Z",
    cells: [
      cell("G-1", "Gaming", "Budget"),
      cell("G-2", "Gaming", "Mid-range"),
      cell("O-1", "Office", "Budget"),
    ],
    unassigned_channel_records: 2,
  };
  book.mockResolvedValue(data);
  render(<PlaybookBook onEdit={vi.fn()} />);
  await screen.findByRole("table", { name: "Recommended build matrix" });
  expect(screen.getByRole("button", { name: "2. Market & target pricing" }))
    .toHaveAttribute("aria-description", "Requires attention");
  fireEvent.click(screen.getByRole("button", { name: "Open Gaming Budget" }));
  fireEvent.click(screen.getByRole("button", { name: "2. Market & target pricing" }));
  expect(screen.getByRole("button", { name: "2. Market & target pricing" })).toHaveAttribute("aria-current", "page");
  expect(
    screen.getByRole("table", { name: "Market & target pricing matrix" })
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Gaming Budget" }))
    .toHaveAttribute("aria-description", "Requires attention");
  expect(
    screen.getByRole("button", { name: "Open Gaming Budget" })
  ).toHaveAttribute("aria-pressed", "true");
  expect(
    screen.getByRole("button", { name: "Open Office Budget" })
  ).toBeInTheDocument();
  expect(
    within(screen.getByLabelText("Selected Playbook cell")).getByText(
      "Walk-away (approved sell floor)"
    )
  ).toBeInTheDocument();
  expect(
    within(screen.getByLabelText("Selected Playbook cell")).getAllByText(
      "Not recorded"
    ).length
  ).toBeGreaterThan(2);
  fireEvent.click(screen.getByRole("button", { name: "detailed" }));
  expect(window.location.search).toContain("cell=G-1");
  expect(window.location.search).toContain("slice=pricing");
  expect(window.location.search).toContain("detail=1");
  fireEvent.click(screen.getByRole("button", { name: "11. Approvals" }));
  expect(screen.getByText("Review tools for G-1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "10. Live status" }));
  expect(screen.getByRole("button", { name: "10. Live status" }))
    .not.toHaveAttribute("aria-description");
  expect(screen.getByRole("button", { name: "Open Gaming Budget" }))
    .not.toHaveAttribute("aria-description");
  fireEvent.click(screen.getByRole("button", { name: "15. Software" }));
  expect(screen.getByRole("button", { name: "15. Software" }))
    .not.toHaveAttribute("aria-description");
});
it("restores the page and cell from a deep link and does not invent history or distribution", async () => {
  window.history.replaceState(null, "", "/?slice=history&cell=G-1");
  book.mockResolvedValue({
    observed_at: "2026-10-15T12:00:00Z",
    cells: [cell("G-1", "Gaming", "Budget")],
    unassigned_channel_records: 3,
  });
  render(<PlaybookBook onEdit={vi.fn()} />);
  await screen.findByRole("table", { name: "History & decisions matrix" });
  expect(screen.getByLabelText("Selected Playbook cell")).toHaveTextContent(
    "No recorded events for this cell."
  );
  fireEvent.click(screen.getByRole("button", { name: "13. Distribution" }));
  expect(screen.getByLabelText("Selected Playbook cell")).toHaveTextContent(
    "storefront · offline"
  );
  expect(
    screen.getByText(/3 channel records have no exact cell identity/)
  ).toBeInTheDocument();
});
it("reports load failure and can recover without showing an empty matrix as fact", async () => {
  book.mockRejectedValueOnce(new Error("API unavailable"));
  render(<PlaybookBook onEdit={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
  book.mockResolvedValue({
    observed_at: "2026-10-15T12:00:00Z",
    cells: [cell("G-1", "Gaming", "Budget")],
    unassigned_channel_records: 0,
  });
  fireEvent.click(screen.getByRole("button", { name: "Refresh Playbook" }));
  expect(
    await screen.findByRole("button", { name: "Open Gaming Budget" })
  ).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("does not flag market-comparison context as a blocking pricing issue", async () => {
  const current = cell("G-1", "Gaming", "Budget");
  current.pricing_gaps = ["Exact-build active-market comparison is not recorded"];
  book.mockResolvedValue({
    observed_at: "2026-10-15T12:00:00Z",
    cells: [current],
    unassigned_channel_records: 0,
  });
  render(<PlaybookBook onEdit={vi.fn()} />);
  await screen.findByRole("table", { name: "Recommended build matrix" });
  fireEvent.click(screen.getByRole("button", { name: "2. Market & target pricing" }));
  expect(screen.getByRole("button", { name: "2. Market & target pricing" }))
    .not.toHaveAttribute("aria-description");
  expect(screen.getByRole("button", { name: "Open Gaming Budget" }))
    .not.toHaveAttribute("aria-description");
});

it("shows net operating cost from the engine and keeps VAT outside it", async () => {
  const current = cell("G-1", "Gaming", "Budget");
  const mode = {
    available: false,
    recommended_price_gbp: "231.84",
    estimated_profit_gbp: "50.00",
    estimated_total_cost_gbp: "143.20",
    net_revenue_gbp: "193.20",
    vat_gbp: "38.64",
    profit_floor_gbp: "231.84",
    reason: "Proposal only",
  };
  current.offer = {
    proposal_id: 1,
    revision_sha256: "a".repeat(64),
    cell_id: "G-1",
    segment: "Gaming",
    tier: "Budget",
    name: "Gaming build",
    description: "",
    components: [],
    case_choices: [],
    upsells: [],
    delivery_products: { fast_track: mode, standard: mode, flexible: mode },
    blockers: [],
    complete_hardware: true,
    required_hardware_count: 7,
    source_available: true,
    compatibility: { verified: true, checks: [] },
  };
  window.history.replaceState(null, "", "/?slice=economics&cell=G-1");
  book.mockResolvedValue({
    observed_at: "2026-10-15T12:00:00Z",
    cells: [current],
    unassigned_channel_records: 0,
  });
  render(<PlaybookBook onEdit={vi.fn()} />);
  const selected = await screen.findByLabelText("Selected Playbook cell");
  expect(
    within(selected).getAllByText(/Estimated operating cost \(net\) £143.20/)
  ).toHaveLength(3);
  expect(within(selected).getAllByText(/VAT £38.64/)).toHaveLength(3);
  expect(within(selected).queryByText(/181.84/)).not.toBeInTheDocument();
});

it("keeps unassigned build market and channel evidence outside the cell prices", async () => {
  const current = cell("G-1", "Gaming", "Budget");
  const data: BookData = {
    observed_at: "2026-10-15T12:00:00Z",
    cells: [current],
    unassigned_channel_records: 1,
    build_market_references: [
      {
        build_id: 12,
        name: "Owned reference build",
        observations: 159,
        last_observed_at: null,
        reason: "Needs exact-spec review",
      },
    ],
    unassigned_distribution: [
      {
        channel: "ebay",
        status: "active",
        source: "Stored eBay build record",
        external_id: "123",
        title: "Unassigned machine",
        manual_build_id: 12,
        assignment_reason: "No valid exact Playbook cell assignment",
      },
    ],
  };
  window.history.replaceState(null, "", "/?slice=pricing&cell=G-1");
  book.mockResolvedValue(data);
  render(<PlaybookBook onEdit={vi.fn()} />);
  await screen.findByLabelText("Selected Playbook cell");
  expect(screen.getAllByText(/159 observations/).length).toBeGreaterThan(0);
  fireEvent.click(
    screen.getByText(/Build-specific sold evidence requiring cell review/)
  );
  expect(
    screen.getByRole("link", { name: "Owned reference build" })
  ).toHaveAttribute("href", "/builds/12");
  expect(screen.getByLabelText("Selected Playbook cell")).not.toHaveTextContent(
    "£159"
  );
  fireEvent.click(screen.getByRole("button", { name: "13. Distribution" }));
  fireEvent.click(
    screen.getByText(/Recorded channel presence requiring a cell assignment/)
  );
  expect(
    screen.getByRole("link", { name: "Review the build’s Playbook assignment" })
  ).toHaveAttribute("href", "/builds/12");
  expect(screen.getByLabelText("Selected Playbook cell")).not.toHaveTextContent(
    "Unassigned machine"
  );
});
