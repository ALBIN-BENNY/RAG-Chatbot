from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging

from app.api import ingest, chat, websites, health
from app.core.config import settings
from app.core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RAG Chatbot API...")
    await init_db()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="RAG Website Chatbot API",
    description="Production-ready RAG chatbot with website crawling and semantic search",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(websites.router, prefix="/api/websites", tags=["websites"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingestion"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
