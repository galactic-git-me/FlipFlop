import { describe, it, expect } from 'vitest';
import { changePart, defaults, options, assetURL, type Slot } from '@/lib/studio';
const slot: Slot = {slot_id:1,slot_type:'cpu',variants_by_tier:{budget:[{id:11,title:'A',display_price:100,specifications:{}}],mid:[{id:12,title:'B',display_price:200,specifications:{}}],high:[]}};
describe('Studio configuration invariants',()=>{
  it('replaces one component without erasing the rest',()=>{
    const before={caseId:4,selections:{1:11,2:21,3:31}};
    expect(changePart(before,1,12)).toEqual({caseId:4,selections:{1:12,2:21,3:31}});
    expect(before.selections[1]).toBe(11);
  });
  it('removes only the requested component',()=>expect(changePart({caseId:4,selections:{1:11,2:21}},1,null)).toEqual({caseId:4,selections:{2:21}}));
  it('uses actual balanced catalogue IDs and tolerates empty categories',()=>expect(defaults([slot,{slot_id:2,slot_type:'gpu',variants_by_tier:{mid:[]}}],[])).toEqual({caseId:null,selections:{1:12}}));
  it('deduplicates tier products',()=>expect(options({...slot,variants_by_tier:{...slot.variants_by_tier,high:slot.variants_by_tier.mid}})).toHaveLength(2));
  it('proxies backend media without exposing internal hostnames',()=>{
    expect(assetURL('http://internal:4311/media/case.glb')).toBe('/studio-assets/case.glb');
    expect(assetURL('/media/case.glb')).toBe('/studio-assets/case.glb');
    expect(assetURL('javascript:alert(1)')).toBeNull();
    expect(assetURL('http://internal/private.glb')).toBeNull();
  });
});
