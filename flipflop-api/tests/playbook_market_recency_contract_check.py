"""Sold transaction freshness must be independent of capture freshness."""
from datetime import datetime,timedelta,timezone
from app.services.playbook_market import candidate

def checks():
 now=datetime.now(timezone.utc)
 base={'title':'Desktop PC','url':'https://www.ebay.co.uk/itm/123456789012','price':500,'postage':0,'condition':'new'}
 for date in (None,(now-timedelta(days=60)).isoformat(),(now+timedelta(days=2)).isoformat()):
  row=candidate({**base,'sold_at':date},'sold','new',0)
  assert row['blockers'], 'Unknown, historical or future transaction accepted as current sold evidence'
 row=candidate({**base,'sold_at':'Sold '+now.strftime('%d %b %Y')},'sold','new',0)
 assert not row['blockers']
 assert not candidate(base,'active','new',0)['blockers']
 print('PASS: sold date missing, historical, future and current; active dates kept separate')
if __name__=='__main__':checks()
