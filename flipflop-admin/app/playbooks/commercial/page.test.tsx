import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import Page from './page';
import CommercialReviewWorkspace from '@/components/playbooks/CommercialReviewWorkspace';
import {EngineeringReview} from './engineering-review';
const proposals=vi.fn();
const automation=vi.fn();
const supplierLicences=vi.fn();
const approveSupplierLicence=vi.fn();
const rebuildProposals=vi.fn();
const refreshStatus=vi.fn();
const engineeringSuggestions=vi.fn();
const productEngineeringSuggestions=vi.fn();
const approveProductEngineeringSuggestion=vi.fn();
const researchEngineeringSuggestions=vi.fn();
const approveEngineeringSuggestion=vi.fn();
const approveSupplierSources=vi.fn();
const approveAllSupplierSources=vi.fn();
vi.mock('@/lib/api',()=>({api:{commercialReadiness:{proposals:(...args:unknown[])=>proposals(...args),automation:(...args:unknown[])=>automation(...args),supplierLicences:(...args:unknown[])=>supplierLicences(...args),approveSupplierLicence:(...args:unknown[])=>approveSupplierLicence(...args),rebuildProposals:(...args:unknown[])=>rebuildProposals(...args),refreshStatus:(...args:unknown[])=>refreshStatus(...args),engineeringSuggestions:(...args:unknown[])=>engineeringSuggestions(...args),productEngineeringSuggestions:(...args:unknown[])=>productEngineeringSuggestions(...args),approveProductEngineeringSuggestion:(...args:unknown[])=>approveProductEngineeringSuggestion(...args),researchEngineeringSuggestions:(...args:unknown[])=>researchEngineeringSuggestions(...args),approveEngineeringSuggestion:(...args:unknown[])=>approveEngineeringSuggestion(...args),approveSupplierSources:(...args:unknown[])=>approveSupplierSources(...args),approveAllSupplierSources:(...args:unknown[])=>approveAllSupplierSources(...args)}}}));
afterEach(cleanup);
it('keeps embedded supplier approvals scoped to the selected cell',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Pending checks'};
  const selected={proposal_id:41,playbook_id:1,cell_id:'SELECTED',revision_sha256:'1'.repeat(64),segment:'Gaming',tier:'Budget',name:'Selected cell build',description:'',required_hardware_count:1,
    components:[{role:'cpu',variant_id:8,listing_id:101,title:'Selected CPU',source_url:'https://www.amazon.co.uk/dp/B000000000',listing_price_gbp:'128.49',supplier_postage_gbp:'0.00',catalogue_approved:true,
      source_observation:{source:'amazon',url:'https://www.amazon.co.uk/dp/B000000000',fresh:true,commercial_capture_verified:true,active_listing:true,condition:'new',listing_type:'buy_it_now',stock_status:'available',stock_evidence:'In stock',postage_verified:true,delivery_gbp:'0.00'}}],
    case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Compatibility pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}};
  proposals.mockResolvedValue({items:[selected,{...selected,proposal_id:42,cell_id:'OTHER',name:'Another cell build'}]});
  approveSupplierSources.mockClear();approveAllSupplierSources.mockClear();
  approveSupplierSources.mockResolvedValue({imported:1,reused:0,pending_roles:[],prices_published:false});
  render(<CommercialReviewWorkspace contextCellId="SELECTED" initialArea="suppliers"/>);
  fireEvent.click(await screen.findByRole('button',{name:'Approve all 1 reviewed supplier products'}));
  expect(await screen.findByRole('status')).toHaveTextContent('Approved 1 current supplier fact');
  expect(approveSupplierSources).toHaveBeenCalledWith(selected);
  expect(approveAllSupplierSources).not.toHaveBeenCalled();
  expect(screen.queryByText('Another cell build')).not.toBeInTheDocument();
});
it('requires explicit confirmation before replacing previously reviewed source values',async()=>{
  const item={listing_id:82,role:'cpu',source_title:'Changed CPU facts',source_url:'https://www.amazon.co.uk/dp/B000000001',
    captured_at:null,properties:{retailer:{TDP:'95 W'},amazon_catalog:{}},suggested_specs:{power_w:95},status:'review_ready',capture_status:'captured',missing_fields:[],
    conflicted_fields:[],reviewed_value_changes:{power_w:{reviewed:65,captured:95}},fingerprint:'c'.repeat(64)};
  productEngineeringSuggestions.mockResolvedValue({items:[item]});
  approveProductEngineeringSuggestion.mockResolvedValue({role:'cpu'});
  const onApproved=vi.fn(async()=>{});
  render(<EngineeringReview onApproved={onApproved}/>);
  const button=await screen.findByRole('button',{name:'Review these source facts'});
  expect(button).toBeDisabled();
  expect(screen.getByText('previously 65; captured 95')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox',{name:'I reviewed these differences and approve replacing the previous values.'}));
  expect(button).not.toBeDisabled();
  fireEvent.click(button);
  expect(await screen.findByRole('status')).toHaveTextContent('cpu source facts reviewed');
  expect(approveProductEngineeringSuggestion).toHaveBeenCalledWith(item,true);
  expect(onApproved).toHaveBeenCalledOnce();
});

it('blocks contradictory source fields even when an operator might otherwise approve',async()=>{
  productEngineeringSuggestions.mockResolvedValue({items:[{listing_id:83,role:'cpu',source_title:'Conflicting CPU facts',
    source_url:'https://www.amazon.co.uk/dp/B000000001',captured_at:null,
    properties:{retailer:{TDP:['65 W','95 W']},amazon_catalog:{}},suggested_specs:{},status:'source_conflict',capture_status:'captured',missing_fields:['power_w'],
    conflicted_fields:['power_w'],reviewed_value_changes:{},fingerprint:'d'.repeat(64)}]});
  render(<EngineeringReview onApproved={async()=>{}}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('contradictory values for power_w');
  expect(screen.getByRole('button',{name:'Review these source facts'})).toBeDisabled();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
});

it('renders structured connector counts and numeric support lists for operator review',async()=>{
  engineeringSuggestions.mockResolvedValue({items:[]});
  productEngineeringSuggestions.mockResolvedValue({items:[{listing_id:90,role:'psu',source_title:'Exact PSU',
    source_url:'https://www.amazon.co.uk/dp/B000000000',captured_at:null,
    properties:{retailer:{'Power connectors':'2 x 8-pin; 1 x 12V-2x6'},amazon_catalog:{}},
    suggested_specs:{psu_connectors:{'8pin':2,'12v2x6':1}},status:'review_ready',capture_status:'captured',missing_fields:[],fingerprint:'a'.repeat(64)},
    {listing_id:91,role:'motherboard',source_title:'Exact motherboard',
    source_url:'https://www.amazon.co.uk/dp/B000000001',captured_at:null,properties:{retailer:{},amazon_catalog:{}},
    suggested_specs:{m2_lengths:[2242,2280]},status:'review_ready',capture_status:'captured',missing_fields:[],fingerprint:'b'.repeat(64)}]});
  render(<EngineeringReview onApproved={async()=>{}}/>);
  expect(await screen.findByText('8pin: 2, 12v2x6: 1')).toBeInTheDocument();
  expect(screen.getByText('2242, 2280')).toBeInTheDocument();
});
beforeEach(()=>{automation.mockResolvedValue({setting_enabled:true,registered:true,enabled:true,next_run_at:null,scheduled_latest:null,scheduled_rebuild_latest:null,manual_latest:null});engineeringSuggestions.mockResolvedValue({items:[]});productEngineeringSuggestions.mockResolvedValue({items:[]});supplierLicences.mockResolvedValue({items:[]});rebuildProposals.mockClear();rebuildProposals.mockResolvedValue({job_id:'rebuild-1',mode:'rebuild',status:'queued',phase:'Queued proposal rebuild',started:true});refreshStatus.mockResolvedValue({job_id:'rebuild-1',mode:'rebuild',status:'succeeded',phase:'Playbook proposals refreshed',error:null,result:{cells:24,complete_hardware:13,ready_for_approval:0,published:false}});});
it('does not ask the operator to set a weekly sales cap and links to the workshop calendar',async()=>{
  proposals.mockResolvedValue({items:[]});
  render(<Page/>);
  await screen.findByText('No generated proposals awaiting review');
  fireEvent.click(screen.getByRole('button',{name:'Workshop planning'}));
  expect(await screen.findByText(/There is no concurrent-build sales cap/)).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Open Workshop Calendar'})).toHaveAttribute('href','/orders');
  expect(screen.queryByLabelText('Available builds')).not.toBeInTheDocument();
});
it('shows generated source-linked proposals without manual price or component forms',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Source research pending',
    supplier_arrival_working_days:7,workshop_wait_working_days:null,workshop_working_days:1,
    courier_working_days:1,estimated_delivery_working_days:9,maximum_delivery_working_days:7,
    timing_basis:'proposed_from_delivery_target'};
  proposals.mockResolvedValue({items:[{proposal_id:1,cell_id:'TEST',revision_sha256:'a'.repeat(64),segment:'Gaming',tier:'Budget',name:'Generated gaming build',description:'Catalogue proposal',required_hardware_count:8,
    components:[{media_ready:false,not_live_reason:'Product photos need approval',role:'cpu',variant_id:1,title:'Exact source CPU',source_url:'https://www.amazon.co.uk/dp/TESTCPU123',listing_price_gbp:'128.49',supplier_postage_gbp:null,catalogue_approved:false}],
    case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Automatic source research is incomplete'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}}]});
  render(<Page/>);
  expect(await screen.findByText('Exact source CPU')).toBeInTheDocument();
  expect(screen.getByText(/Not live: Product photos need approval/)).toBeInTheDocument();
  expect(screen.getByText('£128.49')).toBeInTheDocument();
  expect(screen.getAllByRole('region',{name:'Delivery timing breakdown'})).toHaveLength(3);
  expect(screen.getAllByText('Build and QA allowance')).toHaveLength(3);
  expect(screen.getAllByText(/Proposed allowance from the delivery target/)).toHaveLength(3);
  expect(screen.queryByLabelText('Available builds')).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/component price/i)).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Approve & publish this build'})).toBeDisabled();
  expect(screen.getByRole('link',{name:'Exact source CPU'})).toHaveAttribute('href','https://www.amazon.co.uk/dp/TESTCPU123');
});

it('lets the operator approve only captured stock, price and postage facts',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Source research pending'};
  const offer={proposal_id:22,cell_id:'TEST',revision_sha256:'b'.repeat(64),segment:'Gaming',tier:'Budget',name:'Generated gaming build',description:'Catalogue proposal',required_hardware_count:8,
    components:[{role:'cpu',variant_id:4,listing_id:8,title:'Exact source CPU',source_url:'https://www.amazon.co.uk/dp/B000000000',listing_price_gbp:'128.49',supplier_postage_gbp:'0.00',catalogue_approved:true,
      source_observation:{source:'amazon',url:'https://www.amazon.co.uk/dp/B000000000',fresh:true,commercial_capture_verified:true,active_listing:true,condition:'new',listing_type:'buy_it_now',stock_status:'available',stock_evidence:'Only 2 left in stock',postage_verified:true,delivery_gbp:'0.00',delivery_working_days:1,delivery_estimate_source:'listing_estimate'}}],
    case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Compatibility evidence pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}};
  proposals.mockResolvedValue({items:[offer]});
  approveSupplierSources.mockResolvedValue({imported:1,reused:0,pending_roles:[],checkout_changed:false,prices_published:false});
  approveAllSupplierSources.mockResolvedValue({proposals:1,imported:1,reused:0,pending_roles:[],prices_published:false});
  render(<Page/>);
  expect((await screen.findAllByText('Only 2 left in stock')).length).toBe(2);
  fireEvent.click(screen.getByRole('button',{name:'Approve 1 verified supplier fact'}));
  expect(await screen.findByRole('status')).toHaveTextContent('Approved 1 current supplier fact for Playbook costing.');
  expect(approveSupplierSources).toHaveBeenCalledWith(offer);
  expect(rebuildProposals).toHaveBeenCalledOnce();
});

it('explains that routine proposal updates run automatically, with no refresh buttons',async()=>{
  proposals.mockResolvedValue({items:[]});
  render(<Page/>);
  await screen.findByText('No generated proposals awaiting review');
  expect(screen.getByRole('heading',{name:'Automatic Playbook updates'})).toBeInTheDocument();
  expect(screen.getByText(/There is nothing to click for routine updates/)).toBeInTheDocument();
  expect(screen.getByText(/queues a Playbook recalculation automatically/)).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/rebuild from captured facts/i})).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/refresh catalogues now/i})).not.toBeInTheDocument();
  expect(rebuildProposals).not.toHaveBeenCalled();
});

it('does not present an Overclockers search page as an approvable supplier product',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Source research pending'};
  proposals.mockResolvedValue({items:[{proposal_id:23,cell_id:'SEARCH',revision_sha256:'c'.repeat(64),segment:'Gaming',tier:'Budget',name:'Search result proposal',description:'',required_hardware_count:8,
    components:[{role:'cpu',variant_id:5,listing_id:9,title:'Search result',source_url:'https://www.overclockers.co.uk/search?sSearch=cpu',listing_price_gbp:'20.00',supplier_postage_gbp:'0.00',catalogue_approved:true,
      source_observation:{source:'overclockers',url:'https://www.overclockers.co.uk/search?sSearch=cpu',fresh:true,commercial_capture_verified:true,active_listing:true,condition:'new',listing_type:'buy_it_now',stock_status:'available',stock_evidence:'In stock',postage_verified:true,delivery_gbp:'0.00'}}],
    case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Compatibility pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}}]});
  render(<Page/>);
  expect(await screen.findByRole('button',{name:'Approve 0 verified supplier facts'})).toBeDisabled();
});

it('requires an explicit acknowledgement before approving a Windows source into OS catalogues',async()=>{
  const candidate={listing_id:61,title:'Windows 11 Home OEM Key',url:'https://royalcdkeys.com/en-gb/products/windows-11-home-oem-key',price_gbp:'4.12',image_url:null,seller_product_claims:'One PC, non-transferable.',supplier_handle:'windows-11-home-oem-key',digital_product:true,category:'os',customer_offering_enabled:false,licence_review_fingerprint:'e'.repeat(64),licence_source_reviewed:false,fresh:true,stock_status:'available',stock_evidence:'Royal product feed reports available=true',product_properties:{'License type (supplier listing)':'OEM','Device scope (supplier claim)':'One device'},catalogue_statuses:[{playbook_id:1,status:'pending_review'}],terms_url:'https://royalcdkeys.com/pages/terms-conditions'};
  proposals.mockResolvedValue({items:[]});
  supplierLicences.mockResolvedValue({items:[candidate]});
  approveSupplierLicence.mockResolvedValue({listing_id:61,reviewed:true,reused:false,activated_catalogue_links:8,published:false,prices_published:false,checkout_changed:false});
  render(<Page/>);
  fireEvent.click(await screen.findByRole('button',{name:/^Software licences/}));
  expect(await screen.findByRole('heading',{name:'Windows, Office and Google AI offers to review'})).toBeInTheDocument();
  const button=screen.getByRole('button',{name:'Review this source for Playbook consideration'});
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  expect(button).toBeEnabled();
  fireEvent.click(button);
  expect(await screen.findByRole('status')).toHaveTextContent('Reviewed this exact Windows offer and added 8 internal OS catalogue candidates.');
  expect(approveSupplierLicence).toHaveBeenCalledWith(candidate);
});

it('shows unique supplier facts across all builds and offers one explicit batch approval',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Source research pending'};
  const offer={proposal_id:32,cell_id:'BATCH',revision_sha256:'d'.repeat(64),segment:'Gaming',tier:'Budget',name:'Generated gaming build',description:'',required_hardware_count:1,
    components:[{role:'cpu',variant_id:8,listing_id:101,title:'Verified CPU',source_url:'https://www.amazon.co.uk/dp/B000000000',listing_price_gbp:'128.49',supplier_postage_gbp:'0.00',catalogue_approved:true,
      source_observation:{source:'amazon',url:'https://www.amazon.co.uk/dp/B000000000',fresh:true,commercial_capture_verified:true,active_listing:true,condition:'new',listing_type:'buy_it_now',stock_status:'available',stock_evidence:'In stock',postage_verified:true,delivery_gbp:'0.00',delivery_working_days:1,delivery_estimate_source:'listing_estimate'}}],
    case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Compatibility evidence pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}};
  proposals.mockResolvedValue({items:[offer]});
  approveAllSupplierSources.mockResolvedValue({proposals:1,imported:1,reused:0,pending_roles:[],prices_published:false});
  render(<Page/>);
  fireEvent.click(await screen.findByRole('button',{name:/^Supplier listings/}));
  expect((await screen.findAllByRole('link',{name:'Verified CPU'})).length).toBe(1);
  fireEvent.click(screen.getByRole('button',{name:'Approve all 1 reviewed supplier products'}));
  expect(await screen.findByRole('status')).toHaveTextContent('Reviewed 1 current build proposals: 1 supplier facts saved');
  expect(approveAllSupplierSources).toHaveBeenCalledWith([offer]);
});

it('keeps motherboard research automatic and leaves its facts unapproved',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Pending'};
  proposals.mockResolvedValue({items:[{proposal_id:1,cell_id:'BOARD',revision_sha256:'e'.repeat(64),segment:'Gaming',tier:'Budget',name:'Gaming build',description:'',required_hardware_count:1,
    components:[],case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Research pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}}]});
  engineeringSuggestions.mockResolvedValue({items:[]});
  render(<Page/>);
  fireEvent.click(await screen.findByRole('button',{name:/^Compatibility /}));
  expect(await screen.findByText(/scheduled Playbook refresh captures exact catalogue and official manufacturer facts automatically/i)).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/research missing motherboard specs/i})).not.toBeInTheDocument();
  expect(researchEngineeringSuggestions).not.toHaveBeenCalled();
});

it('requires an explicit review click before a board suggestion affects proposals',async()=>{
  rebuildProposals.mockClear();
  const mode={available:false,recommended_price_gbp:null,reason:'Pending'};
  proposals.mockResolvedValue({items:[{proposal_id:1,cell_id:'BOARD',revision_sha256:'f'.repeat(64),segment:'Gaming',tier:'Budget',name:'Gaming build',description:'',required_hardware_count:1,
    components:[],case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Research pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}}]});
  engineeringSuggestions.mockResolvedValue({items:[{id:7,canonical_model:'MSI B550M PRO-VDH WIFI',brand:'MSI',socket:'am4',chipset:'b550',ram_type:'ddr4',ram_slots:4,max_ram_gb:128,form_factor:'matx',m2_slots:2,sata_ports:4,source_title:'Exact board title',source_url:'https://www.amazon.co.uk/dp/B000000000',manufacturer_source_url:'https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI/Specification',manufacturer_source_title:'MSI B550M PRO-VDH WIFI Specification',manufacturer_source_captured_at:'2026-10-15T00:00:00Z',manufacturer_facts_captured:true}]});
  approveEngineeringSuggestion.mockResolvedValue({id:7,canonical_model:'MSI B550M PRO-VDH WIFI',reviewed:true,published:false});
  render(<Page/>);
  fireEvent.click(await screen.findByRole('button',{name:/^Compatibility /}));
  expect(await screen.findByText('MSI B550M PRO-VDH WIFI')).toBeInTheDocument();
  expect(screen.getByText('am4')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Approve reviewed specs'}));
  expect(await screen.findByRole('status')).toHaveTextContent('MSI B550M PRO-VDH WIFI reference reviewed. Proposals were recalculated from captured facts; no build was published.');
  expect(approveEngineeringSuggestion).toHaveBeenCalledWith(7);
  expect(rebuildProposals).toHaveBeenCalledOnce();
});

it('shows exact-product engineering facts and requires explicit source review',async()=>{
  const mode={available:false,recommended_price_gbp:null,reason:'Pending'};
  proposals.mockResolvedValue({items:[{proposal_id:3,cell_id:'SOURCE',revision_sha256:'9'.repeat(64),segment:'Gaming',tier:'Budget',name:'Gaming build',description:'',required_hardware_count:1,
    components:[{role:'cpu',listing_id:81,variant_id:4,slot_id:2,title:'Example CPU product',source_url:'https://www.amazon.co.uk/dp/B000000000',listing_price_gbp:null,supplier_postage_gbp:null,catalogue_approved:true}],case_choices:[],upsells:[],compatibility:{verified:false,checks:[]},blockers:['Compatibility pending'],delivery_products:{fast_track:mode,standard:mode,flexible:mode}}]});
  const item={listing_id:81,role:'cpu',source_title:'Example CPU product',source_url:'https://www.amazon.co.uk/dp/B000000000',captured_at:'2026-10-15T00:00:00Z',properties:{retailer:{Socket:'AM5',TDP:'65 W'},amazon_catalog:{}},suggested_specs:{socket:'am5',power_w:65},status:'review_ready',capture_status:'captured',missing_fields:['cpu_id','integrated_graphics'],fingerprint:'9'.repeat(64)};
  productEngineeringSuggestions.mockResolvedValue({items:[item]});
  approveProductEngineeringSuggestion.mockResolvedValue({listing_id:81,role:'cpu',approved_specs:item.suggested_specs,reviewed:true,published:false});
  render(<Page/>);
  expect(await screen.findByText('Example CPU product')).toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button',{name:/^Compatibility /}));
  expect(await screen.findByRole('button',{name:'Review these source facts'})).toBeInTheDocument();
  expect(screen.getByText('power w')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Review these source facts'}));
  expect(await screen.findByRole('status')).toHaveTextContent('cpu source facts reviewed for Example CPU product. Proposals were recalculated from captured facts; nothing was published.');
  expect(approveProductEngineeringSuggestion).toHaveBeenCalledWith(item);
  expect(rebuildProposals).toHaveBeenCalledOnce();
});
