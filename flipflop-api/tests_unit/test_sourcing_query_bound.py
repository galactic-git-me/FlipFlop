"""Exercise the actual endpoint query construction without a database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from types import SimpleNamespace
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.dialects import postgresql
from app.api.gem_radar import get_scored_listings_latest_run

class CapturedQuery(Exception): pass

class SourcingQueryBound(unittest.IsolatedAsyncioTestCase):
    async def test_active_ids_are_not_expanded_into_driver_arguments(self):
        class Database:
            statement=None
            async def execute(self,statement,*args,**kwargs):
                if isinstance(statement,TextClause) and 'SELECT DISTINCT listing_id' in str(statement):
                    return [SimpleNamespace(listing_id=f'listing-{n}') for n in range(40000)]
                self.statement=statement
                raise CapturedQuery()
        db=Database()
        with self.assertRaises(CapturedQuery):
            await get_scored_listings_latest_run(environment='DEV',offset=0,paged=True,
                category='cpu',classification='all',stock_lane='all',title_query='',
                sort_key='deal_score',sort_dir='desc',limit=100,db=db,_=None)
        compiled=db.statement.compile(dialect=postgresql.dialect(),compile_kwargs={'render_postcompile':True})
        self.assertLess(len(compiled.params),100,'Active IDs must stay in a database subquery, not one argument per listing')

if __name__=='__main__':unittest.main()
