import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import CataloguePriceReview from './CataloguePriceReview';
afterEach(cleanup);
it('shows collected listing costs separately from catalogue selling prices with no price-entry fields',()=>{
  render(<CataloguePriceReview parts={[{role:'cpu',slot_id:1,variant_id:2,title:'Exact selected CPU',
    part_key:'variant:2',source:null,listed_item_gbp:'128.49',supplier_postage_gbp:'4.99',
    catalogue_price_gbp:'180.00',listing_url:'https://supplier.example/CPU',price_observed_at:'2026-10-14T12:00:00Z'}]} total="133.48"/>);
  expect(screen.getByText('£128.49')).toBeInTheDocument();
  expect(screen.getByText('£4.99')).toBeInTheDocument();
  expect(screen.queryByText('£180.00')).not.toBeInTheDocument();
  expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
  expect(screen.getByRole('link',{name:'View supplier listing'})).toHaveAttribute('href','https://supplier.example/CPU');
});
it('explains a missing product or postage instead of implying a complete zero-priced build',()=>{
  render(<CataloguePriceReview parts={[{role:'ram',slot_id:2,variant_id:null,title:'Choose a product from the catalogue',part_key:null,source:null}]} blockers={['Choose catalogue products for: ram']}/>);
  expect(screen.getByText('Before there is a price to approve')).toBeInTheDocument();
  expect(screen.getByText('Choose catalogue products for: ram')).toBeInTheDocument();
  expect(screen.getAllByText('Not recorded')).toHaveLength(2);
  expect(screen.queryByText('£0.00')).not.toBeInTheDocument();
});
