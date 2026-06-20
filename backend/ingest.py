"""
MediScan AI — RAG Ingest Script
Runs on server startup. Reads documents/ folder → builds ChromaDB.
chroma_db/ is gitignored — always rebuilt fresh on deployment.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


def ingest_documents():
    """
    Loads all .txt files from documents/ and stores chunks in ChromaDB.
    Uses sentence-transformers (all-MiniLM-L6-v2) for embeddings — local, free, ~80MB.
    """
    import chromadb
    from chromadb.utils import embedding_functions

    print("[RAG] Starting ingestion...")

    # Local embedding model (no API call, runs on CPU)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Delete existing collection to rebuild fresh
    try:
        client.delete_collection("mediscan_knowledge")
    except Exception:
        pass

    collection = client.create_collection(
        name="mediscan_knowledge",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    documents = []
    metadatas = []
    ids = []
    chunk_id = 0

    for doc_file in DOCUMENTS_DIR.glob("*.txt"):
        print(f"  [DOC] Processing: {doc_file.name}")
        text = doc_file.read_text(encoding="utf-8")

        # Split by blank lines (paragraph-level chunks — good for medical text)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 30]

        for para in paragraphs:
            documents.append(para)
            metadatas.append({"source": doc_file.name, "type": "medical_knowledge"})
            ids.append(f"chunk_{chunk_id}")
            chunk_id += 1

    if documents:
        # Batch upsert (ChromaDB handles batching internally)
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"[OK] Ingested {chunk_id} chunks from {len(list(DOCUMENTS_DIR.glob('*.txt')))} files.")
    else:
        print("[WARN] No documents found in documents/ folder.")

    return collection


def get_collection():
    """Returns existing ChromaDB collection (used by RAG node at runtime)."""
    import chromadb
    from chromadb.utils import embedding_functions

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(
        name="mediscan_knowledge",
        embedding_function=embedding_fn
    )


if __name__ == "__main__":
    ingest_documents()
    print("[OK] Ingest complete. ChromaDB ready.")
