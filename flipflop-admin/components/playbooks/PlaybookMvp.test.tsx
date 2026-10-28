import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen,within} from "@testing-library/react";
import PlaybookBook from "./PlaybookBook";
import {cell,offer,part} from "./mvp-test-fixtures";
const {book,automation}=vi.hoisted(()=>({book:vi.fn(),automation:vi.fn()}));
vi.mock("@/lib/api",()=>({api:{commercialReadiness:{book,automation}}}));
vi.mock("./PlaybookOperatingRules",()=>({default:()=> <p>Operating rules</p>}));
vi.mock("next/dynamic",()=>({default:()=>()=>null}));
afterEach(cleanup);
it("shows one matrix and keeps proposed prices separate from published customer prices",async()=>{
  const build=cell({is_live:true,checkout_enabled:true,availability_status:"in_stock",approved_price_gbp:899,mvp_autonomy:true,offer:offer({components:[{...part(1),photo_ready:true,media_ready:false,model_generation_status:"DRAFT_CREATED"}],delivery_products:{standard:{available:false,reason:"",recommended_price_gbp:"999",estimated_profit_gbp:"200"}}}),approved_offer:offer({components:[{...part(1),title:"Published CPU"}],delivery_products:{standard:{available:true,reason:"",recommended_price_gbp:"899",estimated_profit_gbp:"100",delivery_working_days:5}}})});
  book.mockResolvedValue({cells:[build]}); automation.mockResolvedValue({enabled:true});
  render(<PlaybookBook onEdit={vi.fn()}/>);
  const matrix=await screen.findByRole("table",{name:"Playbook build matrix"});
  expect(within(matrix).getByText("£899.00")).toBeInTheDocument();
  expect(within(matrix).queryByText("£999.00")).not.toBeInTheDocument();
  expect(within(matrix).getByRole("button",{name:"Approve models"})).toBeInTheDocument();
  expect(screen.queryByRole("navigation",{name:"Playbook pages"})).not.toBeInTheDocument();
});
