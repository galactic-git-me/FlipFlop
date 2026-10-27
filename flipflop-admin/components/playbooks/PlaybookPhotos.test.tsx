import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PlaybookPhotos from "./PlaybookPhotos";
vi.mock("next/dynamic", () => ({ default: () => () => <p>Model review</p> }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const product = { variant_id: 11, variant_ids: [11], title: "Exact CPU", category: "cpu", listing_image_urls: ["https://images.example/front.jpg", "https://images.example/back.jpg"], asset: null, asset_media_review: null };
it("requires a human photo choice and sends that exact choice without filtering or replacing it", async () => {
  const fetcher = vi.fn().mockImplementation(async (_url: string, options?: RequestInit) => new Response(JSON.stringify(options?.method ? {} : [product]), { status: options?.method === "POST" ? 202 : 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<PlaybookPhotos variantIds={[11]} />);
  const approve = await screen.findByRole("button", { name: "Approve photos & generate model" });
  expect(approve).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: "Use photo 2 of Exact CPU" }));
  fireEvent.click(approve);
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith("/generate"))).toBe(true));
  const saved = fetcher.mock.calls.find(([url]) => url.endsWith("/media-approval"));
  expect(JSON.parse(saved![1].body)).toEqual({ model_image_urls: ["https://images.example/back.jpg"] });
});
it("exposes missing exact component records rather than silently dropping them", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify([product]))));
  render(<PlaybookPhotos variantIds={[11, 12]} />);
  expect(await screen.findByText(/Component 12 is missing from the asset inventory/)).toBeInTheDocument();
});

it("regenerates an unpublished draft from the already approved photo set without auto-approving its model", async () => {
  const draft = {...product,asset:{id:82,status:"meshy_draft",is_active:false,glb_ref:"/model.glb",review_batch_id:"batch"},asset_media_review:{model_references_selected_by:"owner",model_image_urls:[product.listing_image_urls[1]]}};
  const fetcher=vi.fn().mockImplementation(async (_url:string,options?:RequestInit)=>new Response(JSON.stringify(options?.method ? {} : [draft]),{status:options?.method==="POST"?202:200}));
  vi.stubGlobal("fetch",fetcher);
  render(<PlaybookPhotos variantIds={[11]}/>);
  fireEvent.click(await screen.findByRole("button",{name:"Regenerate from approved photos"}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>url.endsWith("/generate"))).toBe(true));
  const generated=fetcher.mock.calls.find(([url])=>url.endsWith("/generate"));
  expect(JSON.parse(generated![1].body)).toEqual({comparison_draft:true});
  expect(fetcher.mock.calls.some(([url])=>url.endsWith("/publish")||url.endsWith("/decision"))).toBe(false);
});

it("reuses a component's existing photo approval instead of asking for approval again", async () => {
  const shared = {...product, asset_media_review:{status:"approved",model_references_selected_by:"owner",model_image_urls:[product.listing_image_urls[0]]}};
  const fetcher=vi.fn().mockImplementation(async (_url:string,options?:RequestInit)=>new Response(JSON.stringify(options?.method ? {} : [shared]),{status:options?.method==="POST"?202:200}));
  vi.stubGlobal("fetch",fetcher);
  render(<PlaybookPhotos variantIds={[11]}/>);
  expect(await screen.findByText(/Photos approved for this component · shared across all segments that use it/)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button",{name:"Generate 3D model from approved photos"}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>url.endsWith("/generate"))).toBe(true));
  expect(fetcher.mock.calls.some(([url])=>url.endsWith("/media-approval"))).toBe(false);
});
