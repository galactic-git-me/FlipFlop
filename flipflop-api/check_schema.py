from app.database import engine
import asyncio
from sqlalchemy import text

async def check_schema():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name='gem_radar_scored_listings' ORDER BY ordinal_position"))
        for row in result:
            max_len = row[2] or ""
            print(f"{row[0]:30} {row[1]:15} {max_len}")

asyncio.run(check_schema())
