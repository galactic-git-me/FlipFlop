from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.source_search_term import SourceSearchTerm
from app.schemas.source_search_term import (
    SourceSearchTermCreate,
    SourceSearchTermUpdate,
    SourceSearchTermOut,
)


class ListTermsResponse(BaseModel):
    items: list[SourceSearchTermOut]
    groups: list[str]
    scopes: list[str]

router = APIRouter(prefix="/source-search-terms", tags=["source-search-terms"])


@router.get("")
async def list_terms(scope: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(SourceSearchTerm).order_by(SourceSearchTerm.group_name, SourceSearchTerm.term)
    if scope:
        q = q.where(SourceSearchTerm.scope == scope)
    rows = (await db.execute(q)).scalars().all()
    groups = sorted({r.group_name for r in rows if r.group_name})
    scopes = sorted({r.scope for r in rows if r.scope})
    return {
        "items": [SourceSearchTermOut.model_validate(r).model_dump() for r in rows],
        "groups": groups,
        "scopes": scopes,
    }


@router.get("/groups")
async def list_groups(scope: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(distinct(SourceSearchTerm.group_name)).order_by(SourceSearchTerm.group_name)
    if scope:
        q = q.where(SourceSearchTerm.scope == scope)
    rows = (await db.execute(q)).scalars().all()
    return [g for g in rows if g]


@router.post("", response_model=SourceSearchTermOut, status_code=201)
async def create_term(body: SourceSearchTermCreate, db: AsyncSession = Depends(get_db)):
    row = SourceSearchTerm(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


@router.patch("/{term_id}", response_model=SourceSearchTermOut)
async def update_term(term_id: int, body: SourceSearchTermUpdate, db: AsyncSession = Depends(get_db)):
    row = await db.get(SourceSearchTerm, term_id)
    if not row:
        raise HTTPException(404, "Search term not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/{term_id}", status_code=204)
async def delete_term(term_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(SourceSearchTerm, term_id)
    if not row:
        raise HTTPException(404, "Search term not found")
    await db.delete(row)
    return None
