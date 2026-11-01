import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ChannelImageReview from "./ChannelImageReview";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const requests = [{ buildId: 2, title: "Test PC", channel: "amazon", urls: ["https://example.com/original.jpg"] }];
const images = [{ id: "a".repeat(64), policy_version: 1, url: "https://www.theflipflop.shop/api/uploads/channel-images/a/amazon.jpg", source_url: requests[0].urls[0], width: 1600, height: 1600, upscaled: false, square_crop_safe: false }];

it("requires photograph and Amazon background review before continuing", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ images }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ images: [images[0].url] }) });
  vi.stubGlobal("fetch", fetchMock);
  const onApproved = vi.fn();
  render(<ChannelImageReview requests={requests} onCancel={vi.fn()} onApproved={onApproved} />);
  const image = await screen.findByRole("img");
  const button = screen.getByRole("button", { name: "Approve photographs & continue" });
  expect(button).toBeDisabled();
  fireEvent.load(image);
  fireEvent.click(screen.getByLabelText(/I reviewed these photographs/));
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/Amazon photographs have a pure-white/));
  fireEvent.click(button);
  await waitFor(() => expect(onApproved).toHaveBeenCalledWith({ "2:amazon": [images[0].url] }));
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ clean_photographs: true, white_background: true });
});

it("shows preview errors and prevents approval of an incomplete batch", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Source photograph unavailable" }) }));
  render(<ChannelImageReview requests={requests} onCancel={vi.fn()} onApproved={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Source photograph unavailable");
  expect(screen.getByRole("button", { name: "Approve photographs & continue" })).toBeDisabled();
});

it("prevents publishing when a preview image fails to load", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ images }) }));
  render(<ChannelImageReview requests={requests} onCancel={vi.fn()} onApproved={vi.fn()} />);
  fireEvent.error(await screen.findByRole("img"));
  fireEvent.click(screen.getByLabelText(/I reviewed these photographs/));
  fireEvent.click(screen.getByLabelText(/Amazon photographs have a pure-white/));
  expect(screen.getByRole("button", { name: "Approve photographs & continue" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("could not load");
});
