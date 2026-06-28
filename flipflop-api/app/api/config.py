from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.search_config import SearchConfig
from app.schemas.search_config import SearchConfigOut, SearchConfigUpdate

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/search", response_model=SearchConfigOut)
async def get_search_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchConfig).where(SearchConfig.is_active == True).limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        # Seed default config on first request
        config = SearchConfig(name="default")
        db.add(config)
        await db.flush()
        await db.refresh(config)
    return config


@router.put("/search", response_model=SearchConfigOut)
async def update_search_config(body: SearchConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchConfig).where(SearchConfig.is_active == True).limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = SearchConfig(name="default")
        db.add(config)

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(config, k, v)

    await db.flush()
    await db.refresh(config)
    return config
