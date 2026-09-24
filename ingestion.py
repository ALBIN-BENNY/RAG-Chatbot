import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.db_models import Website, WebPage, IndexStatus
from app.services.crawler import WebCrawler, CrawlConfig
from app.services.chunker import SemanticChunker
from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Global task registry: website_id -> asyncio.Task
_active_tasks: dict[str, asyncio.Task] = {}


class IngestionService:
    def __init__(self):
        self.chunker = SemanticChunker()

    async def start_ingestion(
        self,
        website_id: str,
        force_recrawl: bool = False,
    ):
        """Start async ingestion task for a website."""
        if website_id in _active_tasks and not _active_tasks[website_id].done():
            logger.info(f"Ingestion already running for {website_id}")
            return

        task = asyncio.create_task(
            self._run_ingestion(website_id, force_recrawl),
            name=f"ingest_{website_id}",
        )
        _active_tasks[website_id] = task
        task.add_done_callback(lambda t: _active_tasks.pop(website_id, None))

    async def _run_ingestion(self, website_id: str, force_recrawl: bool):
        async with AsyncSessionLocal() as db:
            try:
                # Load website record
                result = await db.execute(select(Website).where(Website.id == website_id))
                website = result.scalar_one_or_none()
                if not website:
                    logger.error(f"Website {website_id} not found")
                    return

                # Mark as crawling
                website.status = IndexStatus.CRAWLING
                website.pages_crawled = 0
                website.pages_indexed = 0
                website.total_chunks = 0
                website.error_message = None
                await db.commit()

                config = CrawlConfig(
                    max_pages=website.crawl_config.get("max_pages", 100),
                    use_playwright=website.crawl_config.get("use_playwright", False),
                    allowed_path_prefix=website.crawl_config.get("allowed_path_prefix"),
                )
                crawler = WebCrawler(config)

                if force_recrawl:
                    # Delete old vector data
                    vector_store.delete_website(website_id)
                    await db.execute(
                        WebPage.__table__.delete().where(WebPage.website_id == website_id)
                    )

                pages_crawled = 0
                chunks_buffer = []
                embeddings_buffer = []
                BUFFER_SIZE = 50  # Embed & index in batches

                async for page in crawler.crawl(website.url):
                    pages_crawled += 1
                    logger.info(f"[{website_id}] Crawled #{pages_crawled}: {page.url}")

                    # Record page
                    db_page = WebPage(
                        website_id=website_id,
                        url=page.url,
                        title=page.title,
                        content_hash=page.content_hash,
                    )
                    db.add(db_page)

                    # Chunk
                    chunks = self.chunker.chunk(page.content, page.url, page.title)
                    if chunks:
                        chunks_buffer.extend(chunks)

                    # Update progress
                    website.pages_crawled = pages_crawled
                    await db.commit()

                    # Flush buffer
                    if len(chunks_buffer) >= BUFFER_SIZE:
                        indexed = await self._index_chunks(website_id, chunks_buffer)
                        website.total_chunks += indexed
                        website.pages_indexed = pages_crawled
                        await db.commit()
                        chunks_buffer = []

                # Final flush
                if chunks_buffer:
                    indexed = await self._index_chunks(website_id, chunks_buffer)
                    website.total_chunks += indexed

                # Extract site title from first page
                if not website.title:
                    first = await db.execute(
                        select(WebPage).where(WebPage.website_id == website_id).limit(1)
                    )
                    fp = first.scalar_one_or_none()
                    if fp:
                        website.title = fp.title

                website.status = IndexStatus.READY
                website.pages_indexed = pages_crawled
                await db.commit()
                logger.info(f"[{website_id}] Ingestion complete: {pages_crawled} pages, {website.total_chunks} chunks")

            except Exception as e:
                logger.exception(f"Ingestion failed for {website_id}: {e}")
                async with AsyncSessionLocal() as db2:
                    await db2.execute(
                        update(Website)
                        .where(Website.id == website_id)
                        .values(status=IndexStatus.FAILED, error_message=str(e)[:500])
                    )
                    await db2.commit()

    async def _index_chunks(self, website_id: str, chunks) -> int:
        """Embed and store chunks in vector store."""
        texts = [c.text for c in chunks]
        embeddings = await embedding_service.async_embed(texts)
        vector_store.add_chunks(website_id, chunks, embeddings)
        return len(chunks)

    def is_running(self, website_id: str) -> bool:
        task = _active_tasks.get(website_id)
        return task is not None and not task.done()


ingestion_service = IngestionService()
