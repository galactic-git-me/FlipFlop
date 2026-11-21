"""Deterministic regression checks at the real sold-card parser seam; no DB/providers."""
from app.gem_radar.adapters.sold_comps import LiveSoldCompsAdapter

def card(condition="Brand new", offer="Buy It Now", prices="<span class='s-card__price'>£500.00</span>"):
    return f"""<li class="s-card" data-listingid="123456789012">
    <span aria-label="Sold item">Sold 22 Oct 2026</span>
    <a href="https://www.ebay.co.uk/itm/123456789012"><h3 class="s-card__title">Desktop PC Ryzen 5600G 32GB 1TB</h3></a>
    <span class="s-card__subtitle">{condition}</span>{prices}
    <div class="s-card__attribute-row"><span>{offer}</span></div>
    <div class="s-card__attribute-row"><span>Free delivery</span></div></li>"""

def checks():
    adapter=LiveSoldCompsAdapter()
    rows=adapter._extract_comps_from_html(card(), 'new')
    assert len(rows)==1 and rows[0].delivery_cost_known, 'Primary-attribute free delivery is lost'
    assert adapter._extract_comps_from_html(card(condition='Pre-owned'),'new')==[], 'Requested condition overwrites actual condition'
    assert adapter._extract_comps_from_html(card(condition='Opened – never used'),'new')==[], 'Opened condition treated as new'
    assert adapter._extract_comps_from_html(card(offer='Best Offer accepted'),'new')==[], 'Hidden accepted amount treated as sale price'
    assert adapter._extract_comps_from_html(card(offer='or Best Offer'),'new')==[], 'Offer uncertainty discarded'
    assert adapter._extract_comps_from_html(card(prices="<span class='s-card__price'>£500.00</span><span>to</span><span class='s-card__price'>£700.00</span>"),'new')==[], 'Split price range flattened to first amount'
    assert adapter._extract_comps_from_html(card(condition=''),'new')==[], 'Unknown condition treated as verified'
    rows=adapter._extract_comps_from_html(card(condition='Pre-owned'),'used')
    assert len(rows)==1 and rows[0].condition=='used'
    print('PASS: sold parser delivery, actual condition, hidden offers and split ranges')

if __name__=='__main__': checks()
