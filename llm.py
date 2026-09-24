import logging
from typing import List, Optional, AsyncGenerator
from app.core.config import settings
from app.services.vector_store import RetrievalResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based exclusively on the provided website content.

Rules:
1. Answer ONLY using the provided context passages.
2. If the information is not in the context, say: "I couldn't find information about that in the indexed website content."
3. Be concise, accurate, and helpful.
4. When referencing information, naturally mention where it came from when relevant.
5. Do not make up facts or speculate beyond what's in the context.
6. For follow-up questions, use the conversation history to maintain context.
"""


def _build_context(results: List[RetrievalResult], max_length: int = settings.MAX_CONTEXT_LENGTH) -> str:
    """Build context string from retrieval results, respecting length limit."""
    context_parts = []
    total_len = 0

    for i, r in enumerate(results):
        header = f"[Source {i+1}: {r.title or r.url}]\n"
        body = r.text.strip()
        part = f"{header}{body}\n\n"
        if total_len + len(part) > max_length:
            # Include partial if there's space
            remaining = max_length - total_len - len(header) - 4
            if remaining > 100:
                context_parts.append(f"{header}{body[:remaining]}...\n\n")
            break
        context_parts.append(part)
        total_len += len(part)

    return "".join(context_parts)


class LLMService:
    def __init__(self):
        self._openai_client = None
        self._ollama_client = None

    def _get_openai(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    async def generate(
        self,
        question: str,
        context_results: List[RetrievalResult],
        conversation_history: Optional[List[dict]] = None,
    ) -> str:
        context = _build_context(context_results)

        user_message = f"""Context from website:
---
{context}
---

Question: {question}"""

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history (last 6 turns for memory)
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        if settings.LLM_PROVIDER == "openai":
            return await self._generate_openai(messages)
        elif settings.LLM_PROVIDER == "ollama":
            return await self._generate_ollama(messages)
        else:
            raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")

    async def _generate_openai(self, messages: List[dict]) -> str:
        client = self._get_openai()
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
        )
        return response.choices[0].message.content

    async def _generate_ollama(self, messages: List[dict]) -> str:
        import aiohttp
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                return data["message"]["content"]

    async def stream_generate(
        self,
        question: str,
        context_results: List[RetrievalResult],
        conversation_history: Optional[List[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        context = _build_context(context_results)
        user_message = f"Context:\n---\n{context}\n---\n\nQuestion: {question}"
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        if settings.LLM_PROVIDER == "openai":
            client = self._get_openai()
            async with client.chat.completions.stream(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            ) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta


# Singleton
llm_service = LLMService()
