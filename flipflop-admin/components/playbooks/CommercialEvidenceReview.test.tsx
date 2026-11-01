import { fireEvent, render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import CommercialEvidenceReview from './CommercialEvidenceReview';
import type { ReadinessPart } from '@/lib/commercial-readiness';

afterEach(cleanup);
const part:ReadinessPart={role:'cpu',slot_id:1,variant_id:101,title:'Exact CPU',part_key:'cpu',source:{
  listing_db_id:1,listing_id:'exact',observation_id:12,observed_at:new Date().toISOString(),
  url:'https://www.amazon.co.uk/dp/EXACT',source:'amazon',condition:'new',item_gbp:'100.12',
  delivery_gbp:'0',delivery_working_days:2,delivery_estimate_source:'scraped',
  active_listing:true,fingerprint:'a'.repeat(64),fresh:true,
}};
it('requires explicit cost and stock review and imports only observation identity',()=>{
  const onImport=vi.fn();render(<CommercialEvidenceReview parts={[part]} busy={false} onImport={onImport}/>);
  fireEvent.click(screen.getByLabelText('Import cpu'));
  expect(screen.getByRole('button')).toBeDisabled();
  for(const [field,value] of [['fees','0'],['risk','0'],['confidence','0.9']])
    fireEvent.change(screen.getByLabelText(`cpu ${field}`),{target:{value}});
  expect(screen.getByRole('button')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('cpu stock review'),{target:{value:'yes'}});
  fireEvent.click(screen.getByRole('button'));
  expect(onImport).toHaveBeenCalledWith([{part_key:'cpu',observation_id:12,source_fingerprint:'a'.repeat(64),
    fees_gbp:'0',risk_gbp:'0',supplier_confidence:'0.9',stock_confirmed:true}]);
});
it('discards approval when the underlying observation changes',()=>{
  const onImport=vi.fn();const view=render(<CommercialEvidenceReview parts={[part]} busy={false} onImport={onImport}/>);
  fireEvent.click(screen.getByLabelText('Import cpu'));
  view.rerender(<CommercialEvidenceReview parts={[{...part,source:{...part.source!,fingerprint:'b'.repeat(64)}}]} busy={false} onImport={onImport}/>);
  expect(screen.getByLabelText('Import cpu')).not.toBeChecked();
  expect(screen.getByRole('button')).toBeDisabled();
});
it('prevents confirming stale source stock',()=>{
  render(<CommercialEvidenceReview parts={[{...part,source:{...part.source!,fresh:false}}]} busy={false} onImport={vi.fn()}/>);
  expect(screen.getByRole('option',{name:'Confirmed available'})).toBeDisabled();
});
it('shows the marketplace separately from its named seller',()=>{
  render(<CommercialEvidenceReview parts={[{...part,source:{...part.source!,source:'Storage Kit'}}]} busy={false} onImport={vi.fn()}/>);
  expect(screen.getByText(/Amazon · seller Storage Kit/)).toBeInTheDocument();
});
it('imports the verified zero-cost Ubuntu source without asking the operator to approve physical stock',()=>{
  const ubuntu:ReadinessPart={...part,role:'os_secondary',title:'Ubuntu 24.04 LTS',part_key:'ubuntu',source:{
    ...part.source!,source:'Ubuntu',url:'https://releases.ubuntu.com/24.04/',item_gbp:'0.00',delivery_gbp:'0.00',
    evidence_kind:'official_free_software',stock_evidence:'Official download available; no physical stock.',
  }};
  const onImport=vi.fn();render(<CommercialEvidenceReview parts={[ubuntu]} busy={false} onImport={onImport}/>);

  expect(screen.getByText(/Official download availability; not physical stock/)).toBeInTheDocument();
  expect(screen.queryByLabelText('os_secondary stock review')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Import os_secondary')).toBeChecked();
  expect(screen.getByLabelText('os_secondary fees')).toBeDisabled();
  fireEvent.click(screen.getByRole('button'));
  expect(onImport).toHaveBeenCalledWith([{part_key:'ubuntu',observation_id:12,
    source_fingerprint:'a'.repeat(64),fees_gbp:'0',risk_gbp:'0',supplier_confidence:'1',stock_confirmed:true}]);
});
