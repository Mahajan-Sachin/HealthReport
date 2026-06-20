"""
MediScan AI — FastAPI Backend
Endpoints: text analysis, PDF upload analysis, report download, health check.
Runs ingest on startup to build ChromaDB.
"""

import os
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# In-memory report store (replaced by DB in production)
report_store: dict = {}


# ─── Startup: Build ChromaDB + Graph ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup: ingest documents, build graph."""
    print("[START] MediScan AI starting up...")

    # Build RAG vector DB
    from backend.ingest import ingest_documents
    ingest_documents()

    # Pre-build the graph (so first request isn't slow)
    from backend.graph.graph import get_graph
    get_graph()

    print("[OK] MediScan AI ready to serve requests")
    yield
    print("[STOP] MediScan AI shutting down")


# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title="MediScan AI",
    description="Multi-agent AI lab report intelligence system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ──────────────────────────────────────────────────

class TextAnalysisRequest(BaseModel):
    report_text: str
    patient_name: str = "Patient"
    patient_age: int
    patient_sex: str  # "male" or "female"


class AnalysisResponse(BaseModel):
    report_id: str
    status: str
    message: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Deployment health check endpoint."""
    return {"status": "healthy", "service": "MediScan AI", "version": "1.0.0"}


@app.post("/analyze/text", response_model=AnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    """
    Analyze lab report provided as text.
    Returns report_id to fetch results.
    """
    if not request.report_text.strip():
        raise HTTPException(status_code=400, detail="Report text cannot be empty")

    if len(request.report_text) > 15000:
        raise HTTPException(status_code=400, detail="Report text too long (max 15,000 characters)")

    if request.patient_age < 1 or request.patient_age > 120:
        raise HTTPException(status_code=400, detail="Invalid age")

    if request.patient_sex.lower() not in ("male", "female"):
        raise HTTPException(status_code=400, detail="patient_sex must be 'male' or 'female'")

    report_id = str(uuid.uuid4())[:8]

    try:
        from backend.graph.graph import run_analysis
        # Run synchronous analysis in thread pool — avoids CrewAI/FastAPI event loop conflict
        report = await asyncio.to_thread(
            run_analysis,
            request.report_text,
            request.patient_name,
            request.patient_age,
            request.patient_sex.lower(),
        )
        report["report_id"] = report_id
        report["generated_at"] = datetime.now().isoformat()
        report_store[report_id] = report

        return AnalysisResponse(
            report_id=report_id,
            status="success",
            message=f"Analysis complete. {report.get('summary', {}).get('total_tests', 0)} tests analyzed."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/pdf", response_model=AnalysisResponse)
async def analyze_pdf(
    file: UploadFile = File(...),
    patient_name: str = Form(default="Patient"),
    patient_age: int = Form(...),
    patient_sex: str = Form(...),
):
    """
    Analyze lab report uploaded as PDF.
    Extracts text using PyMuPDF, then runs same analysis pipeline.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if patient_sex.lower() not in ("male", "female"):
        raise HTTPException(status_code=400, detail="patient_sex must be 'male' or 'female'")

    pdf_bytes = await file.read()

    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="PDF too large (max 10MB)")

    from backend.utils.pdf_extractor import extract_text_from_pdf, is_pdf_readable

    if not is_pdf_readable(pdf_bytes):
        raise HTTPException(
            status_code=400,
            detail="This PDF appears to be a scanned/image PDF. Please use a digital PDF or paste the text manually."
        )

    try:
        report_text = extract_text_from_pdf(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not report_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    report_id = str(uuid.uuid4())[:8]

    try:
        from backend.graph.graph import run_analysis
        # Run synchronous analysis in thread pool — avoids CrewAI/FastAPI event loop conflict
        report = await asyncio.to_thread(
            run_analysis,
            report_text,
            patient_name,
            patient_age,
            patient_sex.lower(),
        )
        report["report_id"] = report_id
        report["generated_at"] = datetime.now().isoformat()
        report_store[report_id] = report

        return AnalysisResponse(
            report_id=report_id,
            status="success",
            message=f"PDF analyzed. {report.get('summary', {}).get('total_tests', 0)} tests found."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/report/{report_id}")
async def get_report(report_id: str):
    """Fetch the full structured report by ID."""
    report = report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return JSONResponse(content=report)


@app.get("/download/{report_id}")
async def download_report(report_id: str):
    """Generate and download the report as a PDF file."""
    report = report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        from backend.utils.report_generator import generate_pdf_report
        pdf_bytes = generate_pdf_report(report)

        patient_name = report.get("patient_name", "Patient").replace(" ", "_")
        filename = f"MediScan_Report_{patient_name}_{report_id}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """
    Returns the last 20 request metrics.
    Shows per-node latency, total time, tests found, judge retries.
    Simple — no external tools needed.
    """
    from pathlib import Path
    import json

    metrics_file = Path("metrics.jsonl")
    if not metrics_file.exists():
        return JSONResponse(content={"message": "No requests logged yet.", "requests": []})

    lines = metrics_file.read_text(encoding="utf-8").strip().splitlines()
    recent = [json.loads(l) for l in lines[-20:]]   # last 20 only
    recent.reverse()  # newest first

    # Simple aggregate averages
    if recent:
        avg_total = round(sum(r["total_seconds"] for r in recent) / len(recent), 1)
        avg_tests = round(sum(r["tests_found"] for r in recent) / len(recent), 1)
    else:
        avg_total = avg_tests = 0

    return JSONResponse(content={
        "total_requests_logged": len(lines),
        "showing": len(recent),
        "averages": {
            "total_seconds": avg_total,
            "tests_found": avg_tests,
        },
        "requests": recent
    })



frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# ─── Run directly ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
