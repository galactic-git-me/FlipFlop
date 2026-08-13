import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def clear_queue():
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE submission_queue CASCADE"))
        await session.commit()
        print("Cleared submission_queue")

asyncio.run(clear_queue())
