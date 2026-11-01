import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { lazy, Suspense } from "react";
import PlaybookMediaDialog from "./PlaybookMediaDialog";
import {cell,offer,part} from "./mvp-test-fixtures";
vi.mock("next/dynamic", () => ({ default: (loader: () => Promise<{ default: React.ComponentType }>) => {
  const Component = lazy(loader);
  return (props: object) => <Suspense fallback={<p>Loading</p>}><Component {...props} /></Suspense>;
} }));
vi.mock("./PlaybookPhotos", () => ({ default: ({ variantIds }: {variantIds:number[]}) => <p>Exact products {variantIds.join(",")}</p> }));
afterEach(cleanup);
it("scopes the MVP overlay to deduplicated base hardware, excluding software and unselected options", async () => {
  const build = cell({offer:offer({components:[part(12),part(13,"case"),part(13,"case"),part(14,"os")],case_choices:[part(15,"case")]})});
  const onClose=vi.fn(); render(<PlaybookMediaDialog cell={build} onClose={onClose} />);
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(await screen.findByText("Exact products 12,13")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Close"}));
  expect(onClose).toHaveBeenCalledOnce();
});
