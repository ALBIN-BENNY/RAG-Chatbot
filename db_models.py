from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum
import uuid


def gen_uuid():
    return str(uuid.uuid4())


class IndexStatus(str, enum.Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class Website(Base):
    __tablename__ = "websites"

    id = Column(String, primary_key=True, default=gen_uuid)
    url = Column(String, nullable=False, unique=True, index=True)
    title = Column(String)
    description = Column(Text)
    status = Column(Enum(IndexStatus), default=IndexStatus.PENDING)
    pages_crawled = Column(Integer, default=0)
    pages_indexed = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    error_message = Column(Text)
    crawl_config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pages = relationship("WebPage", back_populates="website", cascade="all, delete-orphan")
    sessions = relationship("ChatSession", back_populates="website", cascade="all, delete-orphan")


class WebPage(Base):
    __tablename__ = "web_pages"

    id = Column(String, primary_key=True, default=gen_uuid)
    website_id = Column(String, ForeignKey("websites.id"), nullable=False, index=True)
    url = Column(String, nullable=False)
    title = Column(String)
    content_hash = Column(String)
    chunk_count = Column(Integer, default=0)
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())

    website = relationship("Website", back_populates="pages")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    website_id = Column(String, ForeignKey("websites.id"), nullable=False, index=True)
    user_id = Column(String, index=True)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    website = relationship("Website", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=[])
    retrieval_scores = Column(JSON, default=[])
    latency_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")
