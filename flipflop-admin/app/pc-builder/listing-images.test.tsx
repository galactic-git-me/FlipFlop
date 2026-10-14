import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import CuratedBuildsPage from './page';

vi.mock('@/components/catalogue/Shared3DAssetGrid', () => ({ default: () => null }));
vi.mock('@/lib/api', () => ({ api: { dispatch: { softwareCatalogue: async () => ({ items: [] }) } } }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('keeps distinct listings for one product without duplicate React keys', async () => {
  const common = {
    category: 'case', cpk: '9bc00f3573dd170d', rank: 9,
    title: 'Same case model', url: 'https://www.amazon.co.uk/dp/example',
    image_url: 'https://images.example.test/reference.jpg', price: 80,
    marketplace_source: 'Vendor', marketplace_title: 'Same case model',
    marketplace_url: 'https://vendor.example.test/case',
    marketplace_image_url: 'https://images.example.test/vendor.jpg',
    marketplace_image_is_reference: false, marketplace_is_self_capture: false,
    marketplace_price: 75, marketplace_condition: 'new', marketplace_seen_at: '2026-10-14',
    review_status: 'pending',
  };
  const items = [
    { ...common, asin: 'ASIN-A', marketplace_listing_id: 'vendor-a' },
    { ...common, asin: 'ASIN-B', marketplace_listing_id: 'vendor-b' },
  ];
  vi.stubGlobal('fetch', vi.fn(async (input: string) => ({ ok: true, json: async () =>
    input.includes('bestseller-catalogue') ? { items } :
    input.includes('assets-3d') ? [] : input.includes('draft-playbook') ? { playbooks: [] } : { segments: [], components: [] },
  })));
  const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
  const { container } = render(<CuratedBuildsPage />);
  fireEvent.click(screen.getByRole('button', { name: /^Listing Images$/ }));
  await screen.findByText('2 image matches');
  expect(container.querySelectorAll('article')).toHaveLength(2);
  expect(errors.mock.calls.some(args => args.some(value => String(value).includes('Encountered two children with the same key')))).toBe(false);
  // Approval is product-scoped, even though the visible listing cards are distinct.
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select all (2)' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Approve selected (1)' })).toBeEnabled());
});
