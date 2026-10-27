"""Queue monitoring must not materialize queued scraped payloads."""
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock,MagicMock
from sqlalchemy.dialects import postgresql
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.submission_queue_service import SubmissionQueueService

class ProjectionChecks(unittest.IsolatedAsyncioTestCase):
 async def test_only_metadata_and_listing_count_are_selected(self):
  db=AsyncMock();result=MagicMock();result.all.return_value=[];db.execute.return_value=result
  await SubmissionQueueService.get_live_items(db,500)
  query=str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
  projection=query.split('FROM')[0]
  self.assertIn('json_array_length',projection)
  self.assertNotIn('submission_queue.listings_json,',projection)
  for field in ['first_attempt_at','ingested_new_count','listings_count','search_run_id']:
   self.assertIn(field,projection)
  result.scalars.assert_not_called()

if __name__=='__main__':unittest.main()
