import logging
import re
import math
from collections import defaultdict
from typing import List, Tuple, Optional
from dataclasses import dataclass

from app.core.config import settings
from app.services.chunker import TextChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    text: str
    url: str
    title: str
    score: float
    vector_score: float
    bm25_score: float
    metadata: dict


class BM25Index:
    """Simple in-memory BM25 for hybrid retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: List[str] = []
        self.doc_ids: List[str] = []
        self.idf: dict = {}
        self._tf: List[dict] = []
        self._avgdl: float = 0.0

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-z]+\b", text.lower())

    def add_documents(self, texts: List[str], ids: List[str]):
        self.docs = texts
        self.doc_ids = ids
        tokenized = [self._tokenize(t) for t in texts]
        n = len(texts)
        dl = [len(t) for t in tokenized]
        self._avgdl = sum(dl) / n if n else 1

        # TF per doc
        self._tf = []
        for tokens in tokenized:
            freq = defaultdict(int)
            for tok in tokens:
                freq[tok] += 1
            self._tf.append(dict(freq))

        # IDF
        df = defaultdict(int)
        for tokens in tokenized:
            for tok in set(tokens):
                df[tok] += 1
        self.idf = {}
        for tok, count in df.items():
            self.idf[tok] = math.log((n - count + 0.5) / (count + 0.5) + 1)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        if not self.docs:
            return []
        query_tokens = self._tokenize(query)
        scores = []
        n = len(self.docs)
        for i in range(n):
            score = 0.0
            dl = sum(self._tf[i].values())
            for tok in query_tokens:
                if tok not in self._tf[i]:
                    continue
                tf = self._tf[i][tok]
                idf = self.idf.get(tok, 0)
                num = tf * (self.k1 + 1)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                score += idf * (num / denom)
            scores.append((self.doc_ids[i], score))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


class VectorStore:
    """ChromaDB vector store with BM25 hybrid retrieval."""

    def __init__(self):
        self._client = None
        self._bm25_indexes: dict[str, BM25Index] = {}

    def _get_client(self):
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        return self._client

    def _collection_name(self, website_id: str) -> str:
        # ChromaDB collection names must be alphanumeric + hyphens
        return f"site_{website_id.replace('-', '_')}"

    def _get_or_create_collection(self, website_id: str):
        client = self._get_client()
        return client.get_or_create_collection(
            name=self._collection_name(website_id),
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, website_id: str, chunks: List[TextChunk], embeddings: List[List[float]]):
        collection = self._get_or_create_collection(website_id)
        ids = [f"{website_id}_{chunk.page_url}_{chunk.chunk_index}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "url": chunk.page_url,
                "title": chunk.page_title,
                "chunk_index": chunk.chunk_index,
                **chunk.metadata,
            }
            for chunk in chunks
        ]
        # ChromaDB batches of 5000
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            collection.add(
                ids=ids[i:i+batch_size],
                documents=documents[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
            )

        # Rebuild BM25 index
        self._rebuild_bm25(website_id)

    def _rebuild_bm25(self, website_id: str):
        collection = self._get_or_create_collection(website_id)
        result = collection.get(include=["documents"])
        if result and result["documents"]:
            idx = BM25Index()
            idx.add_documents(result["documents"], result["ids"])
            self._bm25_indexes[website_id] = idx

    def search(
        self,
        website_id: str,
        query_embedding: List[float],
        query_text: str,
        top_k: int = settings.TOP_K_RESULTS,
    ) -> List[RetrievalResult]:
        collection = self._get_or_create_collection(website_id)

        # Vector search
        vector_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k * 2, collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        vector_scores: dict[str, float] = {}
        doc_texts: dict[str, str] = {}
        doc_meta: dict[str, dict] = {}

        if vector_results["ids"]:
            for doc_id, doc, meta, dist in zip(
                vector_results["ids"][0],
                vector_results["documents"][0],
                vector_results["metadatas"][0],
                vector_results["distances"][0],
            ):
                score = 1.0 - dist  # cosine similarity
                vector_scores[doc_id] = score
                doc_texts[doc_id] = doc
                doc_meta[doc_id] = meta

        # BM25 search
        bm25_scores: dict[str, float] = {}
        if website_id in self._bm25_indexes:
            bm25_results = self._bm25_indexes[website_id].search(query_text, top_k=top_k * 2)
            if bm25_results:
                max_score = bm25_results[0][1] or 1.0
                for doc_id, score in bm25_results:
                    bm25_scores[doc_id] = score / max_score  # normalize to [0, 1]

        # Hybrid RRF fusion
        all_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
        fused: List[Tuple[str, float]] = []
        for doc_id in all_ids:
            v = vector_scores.get(doc_id, 0.0)
            b = bm25_scores.get(doc_id, 0.0)
            # Weighted combination: 60% vector, 40% BM25
            combined = 0.6 * v + 0.4 * b
            fused.append((doc_id, combined))

        fused.sort(key=lambda x: -x[1])

        results = []
        for doc_id, combined_score in fused[:top_k]:
            if doc_id not in doc_texts:
                # Need to fetch from collection
                try:
                    item = collection.get(ids=[doc_id], include=["documents", "metadatas"])
                    if item["documents"]:
                        doc_texts[doc_id] = item["documents"][0]
                        doc_meta[doc_id] = item["metadatas"][0]
                except Exception:
                    continue

            meta = doc_meta.get(doc_id, {})
            results.append(RetrievalResult(
                text=doc_texts.get(doc_id, ""),
                url=meta.get("url", ""),
                title=meta.get("title", ""),
                score=combined_score,
                vector_score=vector_scores.get(doc_id, 0.0),
                bm25_score=bm25_scores.get(doc_id, 0.0),
                metadata=meta,
            ))

        return results

    def delete_website(self, website_id: str):
        client = self._get_client()
        try:
            client.delete_collection(self._collection_name(website_id))
        except Exception as e:
            logger.warning(f"Could not delete collection for {website_id}: {e}")
        self._bm25_indexes.pop(website_id, None)

    def count(self, website_id: str) -> int:
        try:
            collection = self._get_or_create_collection(website_id)
            return collection.count()
        except Exception:
            return 0


# Singleton
vector_store = VectorStore()
