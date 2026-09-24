import asyncio
import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from app.core.config import settings
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded")
    return _model


class EmbeddingService:
    """Generates vector embeddings using BGE / sentence-transformers."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            self._model = _load_model()
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Synchronous embed — for use outside async context."""
        model = self._get_model()
        # BGE models benefit from query prefix during retrieval; for indexing no prefix needed
        embeddings = model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query with BGE instruction prefix."""
        model = self._get_model()
        # BGE instruction prefix improves retrieval quality
        prefixed = f"Represent this sentence for searching relevant passages: {query}"
        embedding = model.encode([prefixed], normalize_embeddings=True)
        return embedding[0].tolist()

    async def async_embed(self, texts: List[str]) -> List[List[float]]:
        """Run embedding in thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed, texts)

    async def async_embed_query(self, query: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_query, query)


# Singleton
embedding_service = EmbeddingService()
