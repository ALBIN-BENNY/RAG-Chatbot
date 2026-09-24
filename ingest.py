from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.db_models import Website
from app.models.schemas import IngestRequest, IngestProgress
from app.services.ingestion import ingestion_service

router = APIRouter()


@router.post("/start", response_model=IngestProgress)
async def start_ingestion(payload: IngestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == payload.website_id))
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    await ingestion_service.start_ingestion(payload.website_id, payload.force_recrawl)

    return IngestProgress(
        website_id=website.id,
        status=website.status,
        pages_crawled=website.pages_crawled,
        pages_indexed=website.pages_indexed,
        total_chunks=website.total_chunks,
        current_url=None,
        error_message=website.error_message,
    )


@router.get("/status/{website_id}", response_model=IngestProgress)
async def get_ingestion_status(website_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == website_id))
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    return IngestProgress(
        website_id=website.id,
        status=website.status,
        pages_crawled=website.pages_crawled,
        pages_indexed=website.pages_indexed,
        total_chunks=website.total_chunks,
        current_url=None,
        error_message=website.error_message,
    )
