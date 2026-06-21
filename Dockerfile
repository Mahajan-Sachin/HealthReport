# ─── Base Image ───────────────────────────────────────────────────────────────
# Python 3.11-slim — matches our local conda env, minimal image size
FROM python:3.11-slim

# ─── System Dependencies ──────────────────────────────────────────────────────
# build-essential + gcc: needed by chromadb and sentence-transformers C extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Working Directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── Install Python Dependencies ─────────────────────────────────────────────
# Copy requirements first — Docker caches this layer separately
# Avoids reinstalling packages on every code change
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─── Pre-download Embedding Model ────────────────────────────────────────────
# Downloads all-MiniLM-L6-v2 (~80MB) during BUILD, not at runtime
# This avoids a 30-45s cold-start delay on the first request
RUN python -c "\
from langchain_huggingface import HuggingFaceEmbeddings; \
HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2'); \
print('[OK] Embedding model cached')"

# ─── Copy Application Code ────────────────────────────────────────────────────
COPY . .

# ─── Create Runtime Directories ──────────────────────────────────────────────
# chroma_db/ is gitignored — create empty dir, ingest_documents() fills it at startup
RUN mkdir -p chroma_db

# ─── Port ────────────────────────────────────────────────────────────────────
# HF Spaces Docker uses port 7860 by default
# PORT env var supported for flexibility (Render, Railway etc.)
EXPOSE 7860

# ─── Health Check ─────────────────────────────────────────────────────────────
# Docker checks /health every 30s — marks container unhealthy if it fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# ─── Start Server ─────────────────────────────────────────────────────────────
# Startup sequence (handled by main.py lifespan):
#   1. ingest_documents() — reads documents/ → builds chroma_db/
#   2. get_graph()        — compiles LangGraph pipeline
#   3. Server ready
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
