import time
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.db_models import ChatSession, ChatMessage, Website
from app.models.schemas import ChatResponse, Source
from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store, RetrievalResult
from app.services.llm import llm_service

logger = logging.getLogger(__name__)


class ChatService:
    async def get_or_create_session(
        self, db: AsyncSession, website_id: str, session_id: Optional[str], user_id: Optional[str]
    ) -> ChatSession:
        if session_id:
            result = await db.execute(
                select(ChatSession)
                .where(ChatSession.id == session_id)
                .options(selectinload(ChatSession.messages))
            )
            session = result.scalar_one_or_none()
            if session:
                return session

        # Create new session
        session = ChatSession(website_id=website_id, user_id=user_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def chat(
        self,
        db: AsyncSession,
        website_id: str,
        question: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ChatResponse:
        start = time.monotonic()

        # Verify website is ready
        result = await db.execute(select(Website).where(Website.id == website_id))
        website = result.scalar_one_or_none()
        if not website:
            raise ValueError("Website not found")

        # Get/create session with history
        session = await self.get_or_create_session(db, website_id, session_id, user_id)
        await db.refresh(session, ["messages"])

        # Build conversation history
        history = [
            {"role": m.role, "content": m.content}
            for m in sorted(session.messages, key=lambda x: x.created_at)
        ]

        # Semantic retrieval
        query_embedding = await embedding_service.async_embed_query(question)
        retrieval_results = vector_store.search(
            website_id, query_embedding, question
        )

        # Generate answer
        answer = await llm_service.generate(question, retrieval_results, history)

        # Deduplicate sources by URL
        seen_urls = set()
        sources = []
        for r in retrieval_results[:5]:
            if r.url not in seen_urls and r.score > 0.1:
                seen_urls.add(r.url)
                sources.append(Source(
                    url=r.url,
                    title=r.title or r.url,
                    snippet=r.text[:200] + "..." if len(r.text) > 200 else r.text,
                    score=round(r.score, 3),
                ))

        latency_ms = int((time.monotonic() - start) * 1000)

        # Persist messages
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=question,
        )
        db.add(user_msg)

        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            sources=[s.model_dump() for s in sources],
            latency_ms=latency_ms,
        )
        db.add(assistant_msg)

        # Update session title from first question
        if not session.messages:
            session.title = question[:60] + ("..." if len(question) > 60 else "")

        await db.commit()
        await db.refresh(assistant_msg)

        return ChatResponse(
            session_id=session.id,
            message_id=assistant_msg.id,
            answer=answer,
            sources=sources,
            latency_ms=latency_ms,
        )

    async def get_sessions(self, db: AsyncSession, website_id: str) -> List[ChatSession]:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.website_id == website_id)
            .order_by(ChatSession.created_at.desc())
        )
        return result.scalars().all()

    async def get_session_messages(self, db: AsyncSession, session_id: str) -> ChatSession:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == session_id)
            .options(selectinload(ChatSession.messages))
        )
        return result.scalar_one_or_none()


chat_service = ChatService()
