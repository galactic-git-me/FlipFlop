import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import CuratedPhotoPicker from "./CuratedPhotoPicker";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const images = ["one", "two", "three"].map(name => ({ url: `https://example.com/${name}.jpg`, source: "Amazon", href: null }));
const props = { category: "case", cpk: "case-key", title: "Example case" };

it("shows captured photos as automatically included in the Playbook listing", async () => {
  const video = { url: "https://example.com/clip.mp4", source: "Amazon", href: null };
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ images, videos: [video] })));
  vi.stubGlobal("fetch", fetcher);
  render(<CuratedPhotoPicker {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: "View captured listing media" }));
  expect(await screen.findByText("3 photos · 1 videos auto-included")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Example case · photo 1" })).toHaveAttribute("src", images[0].url);
  expect(screen.getByText("Video 1 auto-included")).toBeInTheDocument();
  expect(screen.getByText(/Choose four model reference photos in the 3D assets queue/)).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("category=case"), expect.anything());
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it("explains when only one captured photo is available", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ images: images.slice(0, 1), videos: [] }))));
  render(<CuratedPhotoPicker {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: "View captured listing media" }));
  await screen.findByText(/Only one photo has been captured/);
  expect(screen.getByText("Included in listing")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Save selected/ })).not.toBeInTheDocument();
});

it("includes captured photos and clips from all sources", async () => {
  const ownImage = { url: "/api/builds/12/Media/own.jpg", source: "Our photos", href: null };
  const clip = { url: "/api/builds/12/Media/clip.mp4", source: "Our clips", href: null };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ images: [...images, ownImage], videos: [clip] }))));
  render(<CuratedPhotoPicker {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: "View captured listing media" }));
  await screen.findByText("4 photos · 1 videos auto-included");
  expect(screen.getByRole("img", { name: "Example case · photo 4" })).toHaveAttribute("src", ownImage.url);
  expect(screen.getByText("Video 1 auto-included")).toBeInTheDocument();
});

it("shows load errors and allows a retry without claiming an empty gallery", async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Gallery unavailable" }), { status: 503 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ images: [], videos: [] })));
  vi.stubGlobal("fetch", fetcher);
  render(<CuratedPhotoPicker {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: "View captured listing media" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Gallery unavailable");
  expect(screen.queryByText(/photos · .*auto-included/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Close captured media" }));
  fireEvent.click(screen.getByRole("button", { name: "View captured listing media" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("No product photos have been captured yet.")).toBeInTheDocument();
});
