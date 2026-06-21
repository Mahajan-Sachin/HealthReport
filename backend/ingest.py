"""
MediScan AI — RAG Ingest Script
Runs on server startup. Reads documents/ folder → builds ChromaDB.
chroma_db/ is gitignored — always rebuilt fresh on deployment.
"""

from pathlib import Path
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

DOCUMENTS_DIR   = Path(__file__).parent.parent / "documents"
CHROMA_DIR      = str(Path(__file__).parent.parent / "chroma_db")
COLLECTION_NAME = "mediscan_knowledge"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Singleton embedding model — loaded once, reused every query ───────────────
_embeddings: HuggingFaceEmbeddings | None = None
_vectorstore: Chroma | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Lazy-load the embedding model once."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def ingest_documents() -> Chroma:
    """
    Reads all .txt files from documents/ → converts to LangChain Documents
    → embeds with all-MiniLM-L6-v2 → stores in ChromaDB.
    Called once at server startup.
    """
    global _vectorstore
    print("[RAG] Starting ingestion...")

    documents: list[Document] = []

    for doc_file in DOCUMENTS_DIR.glob("*.txt"):
        print(f"  [DOC] Processing: {doc_file.name}")
        text = doc_file.read_text(encoding="utf-8")

        # Split by blank lines — paragraph-level chunks work well for medical text
        paragraphs = [
            p.strip() for p in text.split("\n\n")
            if p.strip() and len(p.strip()) > 30
        ]

        for para in paragraphs:
            documents.append(Document(
                page_content=para,
                metadata={"source": doc_file.name, "type": "medical_knowledge"}
            ))

    if not documents:
        print("[WARN] No documents found in documents/ folder.")
        return None

    # Chroma.from_documents embeds + stores in one call — no manual batching needed
    _vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=_get_embeddings(),
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )

    file_count = len(list(DOCUMENTS_DIR.glob("*.txt")))
    print(f"[OK] Ingested {len(documents)} chunks from {file_count} file(s).")
    return _vectorstore


def get_vectorstore() -> Chroma:
    """
    Returns the LangChain Chroma vectorstore.
    Used by rag_lookup_node at query time.
    If not built yet, loads from persisted chroma_db/.
    """
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=_get_embeddings(),
            persist_directory=CHROMA_DIR,
        )
    return _vectorstore


if __name__ == "__main__":
    ingest_documents()
    print("[OK] Ingest complete. ChromaDB ready.")
