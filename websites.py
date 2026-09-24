from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.core.database import get_db
from app.models.db_models import Website, IndexStatus
from app.models.schemas import WebsiteCreate, WebsiteResponse
from app.services.vector_store import vector_store

router = APIRouter()


@router.post("", response_model=WebsiteResponse, status_code=201)
async def create_website(payload: WebsiteCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate
    result = await db.execute(select(Website).where(Website.url == payload.url))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    website = Website(
        url=payload.url,
        status=IndexStatus.PENDING,
        crawl_config={
            "max_pages": payload.max_pages or 100,
            "use_playwright": payload.use_playwright or False,
            "allowed_path_prefix": payload.allowed_path_prefix,
        },
    )
    db.add(website)
    await db.commit()
    await db.refresh(website)
    return website


@router.get("", response_model=List[WebsiteResponse])
async def list_websites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).order_by(Website.created_at.desc()))
    return result.scalars().all()


@router.get("/{website_id}", response_model=WebsiteResponse)
async def get_website(website_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == website_id))
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return website


@router.delete("/{website_id}", status_code=204)
async def delete_website(website_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == website_id))
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    vector_store.delete_website(website_id)
    await db.delete(website)
    await db.commit()
