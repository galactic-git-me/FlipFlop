import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PlaybookMarketReview, { type MarketReview } from "./PlaybookMarketReview";
import type { BookCell } from "@/lib/playbook-book";
const { market, collectMarket, reviewMarket } = vi.hoisted(() => ({market:vi.fn(),collectMarket:vi.fn(),reviewMarket:vi.fn()}));
vi.mock("@/lib/api", () => ({api:{commercialReadiness:{market,collectMarket,reviewMarket}}}));
const cell = {playbook_id:1,cell_id:"C"} as BookCell;
function fixture(): MarketReview {
  return {batch_id:5,stale:false,decision:null,approved:null,components:{cpu:"Exact CPU"},batch:{observed_at:"2026-10-15T12:00:00Z",errors:[],candidates:[1,2,3].map(i => ({id:`sold:${i}`,kind:"sold",title:`Complete PC ${i}`,url:`https://www.ebay.co.uk/itm/${123456789000+i}`,condition:"new",total_gbp:"500.00",sold_at:null,blockers:[]}))}};
}
afterEach(() => {cleanup();vi.clearAllMocks();});
it("requires three captured sold listings and full specification confirmation before approval", async () => {
  market.mockResolvedValue(fixture());
  reviewMarket.mockResolvedValue({...fixture(),decision:"market_approved"});
  const updated=vi.fn();
  render(<PlaybookMarketReview cell={cell} onUpdated={updated}/>);
  const approve=await screen.findByRole("button",{name:"Approve selected market evidence"});
  expect(approve).toBeDisabled();
  for(const checkbox of screen.getAllByRole("checkbox",{name:/Confirm comparable/}))fireEvent.click(checkbox);
  expect(approve).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox",{name:/I checked the source listings/}));
  fireEvent.click(approve);
  await waitFor(() => expect(reviewMarket).toHaveBeenCalledWith(1,"C",{batch_id:5,decision:"approve",candidate_ids:["sold:1","sold:2","sold:3"],exact_build_confirmed:true}));
  await waitFor(() => expect(updated).toHaveBeenCalledOnce());
});
it("blocks stale and incomplete source observations", async () => {
  const data=fixture();data.stale=true;data.batch!.candidates[0].blockers=["Unknown delivery"];
  market.mockResolvedValue(data);
  render(<PlaybookMarketReview cell={cell} onUpdated={vi.fn()}/>);
  expect(await screen.findByRole("button",{name:"Approve selected market evidence"})).toBeDisabled();
  expect(screen.getByRole("checkbox",{name:"Confirm comparable: Complete PC 1"})).toBeDisabled();
  expect(screen.getByText(/build changed or these observations expired/)).toBeInTheDocument();
  expect(reviewMarket).not.toHaveBeenCalled();
});
it("shows a provider failure without inventing market prices",async()=>{
  market.mockResolvedValue({...fixture(),batch:null,batch_id:null});
  collectMarket.mockRejectedValue(new Error("Provider unavailable"));
  render(<PlaybookMarketReview cell={cell} onUpdated={vi.fn()}/>);
  await screen.findByText(/No comparisons collected/);
  fireEvent.click(screen.getByRole("button",{name:"Collect market comparisons"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Provider unavailable");
  expect(reviewMarket).not.toHaveBeenCalled();
});
