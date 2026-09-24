from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.db_models import IndexStatus


# ── Website ────────────────────────────────────────────────────────────────

class WebsiteCreate(BaseModel):
    url: str
    max_pages: Optional[int] = 100
    use_playwright: Optional[bool] = False
    allowed_path_prefix: Optional[str] = None


class WebsiteResponse(BaseModel):
    id: str
    url: str
    title: Optional[str]
    description: Optional[str]
    status: IndexStatus
    pages_crawled: int
    pages_indexed: int
    total_chunks: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Ingestion ──────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    website_id: str
    force_recrawl: bool = False


class IngestProgress(BaseModel):
    website_id: str
    status: IndexStatus
    pages_crawled: int
    pages_indexed: int
    total_chunks: int
    current_url: Optional[str]
    error_message: Optional[str]


# ── Chat ───────────────────────────────────────────────────────────────────

class Source(BaseModel):
    url: str
    title: Optional[str]
    snippet: str
    score: float


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    website_id: str
    message: str
    stream: bool = False


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: List[Source]
    latency_ms: int


class SessionCreate(BaseModel):
    website_id: str
    user_id: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    id: str
    website_id: str
    title: str
    created_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True
