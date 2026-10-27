"""Durable compatibility reviews without holding a database transaction for Qwen."""
import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.playbook import PlaybookProposal
from app.services.compatibility_llm_review import (
    compatibility_evidence_fingerprint, review_compatibility_evidence,
)


def _timestamp(value):
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError,ValueError):
        return None


async def run_pending_playbook_compatibility_reviews(limit=3):
    """Claim a bounded batch, release DB connections, then save each exact result.

    Pending claims recover after a worker restart. Unavailable models back off
    for fifteen minutes. A changed physical BOM discards the obsolete result.
    """
    now=datetime.now(timezone.utc)
    claimed=[]
    async with AsyncSessionLocal() as db:
        rows=(await db.execute(select(PlaybookProposal).where(
            PlaybookProposal.status=='pending', PlaybookProposal.action=='UPDATE',
        ).order_by(PlaybookProposal.updated_at,PlaybookProposal.id)
            .with_for_update(skip_locked=True))).scalars().all()
        for proposal in rows:
            if len(claimed)>=limit:
                break
            if (proposal.demand_signals or {}).get('source')!='catalogue_playbook_service_v1':
                continue
            snapshot=deepcopy(proposal.proposed_data or {})
            review=snapshot.get('compatibility_review') or {}
            if review.get('status') not in {'review_pending','review_unavailable'}:
                continue
            started=_timestamp(review.get('started_at'))
            retry=_timestamp(review.get('next_retry_at'))
            if retry and retry>now or started and now-started<timedelta(minutes=6):
                continue
            claim_id=str(uuid4())
            evidence_hash=compatibility_evidence_fingerprint(snapshot)
            snapshot['compatibility_review']={
                'status':'review_pending','summary':'Local compatibility assessment is queued or running.',
                'checks':[],'authority':'advisory_only','started_at':now.isoformat(),
                'claim_id':claim_id,'input_sha256':evidence_hash,
                'attempts':int(review.get('attempts') or 0)+1,
            }
            proposal.proposed_data=deepcopy(snapshot)
            claimed.append((proposal.id,snapshot,claim_id,evidence_hash))
        await db.commit()

    async def assess(item):
        proposal_id,snapshot,claim_id,evidence_hash=item
        try:
            result=await review_compatibility_evidence(snapshot)
        except Exception as error:
            result={'status':'review_unavailable',
                'summary':f'Local compatibility review unavailable ({type(error).__name__}); automatic retry is scheduled.',
                'checks':[],'authority':'advisory_only',
                'next_retry_at':(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()}
        result.update(input_sha256=evidence_hash,
            attempts=snapshot['compatibility_review']['attempts'],
            completed_at=datetime.now(timezone.utc).isoformat())
        async with AsyncSessionLocal() as db:
            proposal=await db.get(PlaybookProposal,proposal_id,with_for_update=True)
            current=deepcopy(proposal.proposed_data or {}) if proposal else {}
            if (proposal is None or proposal.status!='pending'
                    or compatibility_evidence_fingerprint(current)!=evidence_hash):
                return 'superseded'
            current_review=current.get('compatibility_review') or {}
            if current_review.get('claim_id') not in {None,claim_id}:
                return 'superseded'
            current['compatibility_review']=result
            proposal.proposed_data=current
            await db.commit()
        return result['status']

    statuses=await asyncio.gather(*(assess(item) for item in claimed))
    return {'claimed':len(claimed),'results':dict(Counter(statuses)),
        'published':False}
