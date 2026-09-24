# RAG Website Chatbot

A production-ready chatbot that crawls any website and answers questions using Retrieval-Augmented Generation (RAG) with hybrid vector + keyword search.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  URL Input → Progress Monitor → Chat UI → Source Citations  │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  Crawler    │  │   Chunker    │  │   Embedding Model  │ │
│  │ (aiohttp +  │→ │ (Semantic,   │→ │ (BGE-small via     │ │
│  │  BS4)       │  │  512 tokens) │  │  SentenceXformers) │ │
│  └─────────────┘  └──────────────┘  └─────────┬──────────┘ │
│                                               │             │
│  ┌────────────────────────────────────────────▼──────────┐  │
│  │            Vector Store (ChromaDB)                    │  │
│  │   + BM25 Index (in-memory, rebuilt per site)          │  │
│  │   → Hybrid RRF Fusion (60% vector + 40% BM25)         │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │ Top-K chunks                   │
│  ┌──────────────────────────▼────────────────────────────┐  │
│  │               LLM (OpenAI / Ollama)                   │  │
│  │   System prompt + context + conversation history      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  PostgreSQL                                  │
│  websites | web_pages | chat_sessions | chat_messages       │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY

# 2. Start everything
docker compose up --build

# 3. Open http://localhost
```

### Option 2: Local Development

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Set env vars
export OPENAI_API_KEY=sk-...
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ragchatbot

# Run (auto-creates DB tables)
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

## API Reference

### Websites

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/websites` | Register a new website |
| GET | `/api/websites` | List all websites |
| GET | `/api/websites/{id}` | Get website details |
| DELETE | `/api/websites/{id}` | Delete website + its index |

### Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/start` | Start crawling + indexing |
| GET | `/api/ingest/status/{id}` | Get ingestion progress |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/message` | Send a message, get RAG answer |
| GET | `/api/chat/sessions/{website_id}` | List conversations |
| GET | `/api/chat/session/{session_id}` | Get conversation history |

**Example — chat request:**
```json
POST /api/chat/message
{
  "website_id": "abc-123",
  "message": "What authentication methods are supported?",
  "session_id": "optional-for-follow-ups"
}
```

**Response:**
```json
{
  "session_id": "sess-456",
  "message_id": "msg-789",
  "answer": "The platform supports OAuth 2.0, API keys, and JWT tokens...",
  "sources": [
    {
      "url": "https://docs.example.com/auth",
      "title": "Authentication Guide",
      "snippet": "OAuth 2.0 is the recommended...",
      "score": 0.847
    }
  ],
  "latency_ms": 1230
}
```

## Configuration

All settings via environment variables (or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required for OpenAI LLM |
| `LLM_PROVIDER` | `openai` | `openai` or `ollama` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any OpenAI chat model |
| `OLLAMA_MODEL` | `llama3.2` | Any Ollama model |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Any sentence-transformers model |
| `MAX_PAGES_PER_SITE` | `200` | Crawl limit |
| `CHUNK_SIZE` | `512` | Characters per chunk |
| `TOP_K_RESULTS` | `6` | Chunks to retrieve per query |

## Using Ollama (free, local LLM)

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2

# In .env or docker-compose.yml:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2
```

## Feature Details

### Crawler
- Async concurrent crawling with `aiohttp` (5 workers by default)
- Respects domain boundaries — never leaves the target domain
- Skips: images, PDFs, JS/CSS files, login pages, duplicate content
- Configurable `allowed_path_prefix` to restrict to a subdirectory
- Optional Playwright support for JavaScript-rendered sites

### RAG Pipeline
- **Semantic chunking**: splits at heading boundaries, preserves context
- **BGE embeddings**: BAAI/bge-small-en-v1.5, 384-dim, excellent performance
- **ChromaDB**: persistent vector store with cosine similarity
- **BM25**: in-memory keyword index rebuilt per site
- **Hybrid fusion**: 60% vector + 40% BM25 with Reciprocal Rank Fusion
- **Conversation memory**: last 6 turns included in each LLM call

### Source Attribution
Every response includes ranked sources with:
- Page URL and title
- Relevance score (vector + BM25 combined)
- Content snippet preview

## Performance

Typical numbers on a MacBook M2:
- Embedding: ~500 chunks/second (bge-small)  
- Crawling: ~5-10 pages/second (varies by site)
- Query latency: 800ms–2s (depends on LLM)

## Extending

**Add Qdrant** (production vector DB):
```python
# Set VECTOR_DB=qdrant in config
# pip install qdrant-client
# See app/services/vector_store.py for the interface
```

**Add authentication**:
- `python-jose` and `passlib` are already in requirements
- Add `/api/auth/login` and `/api/auth/register` endpoints
- Use `Depends(get_current_user)` on protected routes

**Support PDF ingestion**:
- Add `pypdf2` or `pdfplumber` to requirements
- Create a `pdf_extractor.py` service
- Add a file upload endpoint in `ingest.py`
