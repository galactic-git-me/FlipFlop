import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def clear_db():
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE gem_radar_scored_listings CASCADE"))
        await session.commit()
        print("Cleared gem_radar_scored_listings")

asyncio.run(clear_db())
