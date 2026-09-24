from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.models.db_models import Website, IndexStatus
from app.models.schemas import ChatRequest, ChatResponse, SessionResponse
from app.services.chat import chat_service

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Verify website is ready
    result = await db.execute(select(Website).where(Website.id == payload.website_id))
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    if website.status != IndexStatus.READY:
        raise HTTPException(
            status_code=400,
            detail=f"Website is not ready for chat (status: {website.status.value}). Please wait for indexing to complete."
        )

    try:
        response = await chat_service.chat(
            db=db,
            website_id=payload.website_id,
            question=payload.message,
            session_id=payload.session_id,
            user_id=None,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{website_id}", response_model=List[SessionResponse])
async def get_sessions(website_id: str, db: AsyncSession = Depends(get_db)):
    sessions = await chat_service.get_sessions(db, website_id)
    return sessions


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await chat_service.get_session_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
