from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "RAG Website Chatbot"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ragchatbot"

    # Vector DB - ChromaDB (local) or Qdrant
    VECTOR_DB: str = "chromadb"  # "chromadb" or "qdrant"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # Fast, accurate
    EMBEDDING_DIMENSION: int = 384

    # LLM
    LLM_PROVIDER: str = "openai"  # "openai", "ollama"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Crawling
    MAX_PAGES_PER_SITE: int = 200
    CRAWL_DELAY: float = 0.5
    CRAWL_TIMEOUT: int = 30
    MAX_CONCURRENT_CRAWLERS: int = 5
    USE_PLAYWRIGHT: bool = False

    # RAG
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K_RESULTS: int = 6
    MAX_CONTEXT_LENGTH: int = 4000

    # Auth
    JWT_SECRET: str = "jwt-secret-change-in-production"
    JWT_EXPIRE_HOURS: int = 168  # 7 days

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
