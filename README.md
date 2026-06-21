---
title: MediScan AI
emoji: 🩺
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: AI-powered lab report analyzer — LangGraph + CrewAI + RAG
---

# MediScan AI 🩺

> **AI-powered lab report analysis pipeline** — Upload a blood test PDF or paste raw lab values, get a plain-English health report written by 6 AI agents, validated by a judge model, and downloadable as a PDF.


![CI](https://github.com/Mahajan-Sachin/HealthReport/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What It Does

Most people receive lab reports they can't understand. MediScan AI takes those reports and:

1. **Extracts** every test value using a structured LLM extraction agent
2. **Enriches** missing reference ranges from a WHO-sourced RAG database
3. **Calculates** derived clinical metrics (eGFR, LDL, Non-HDL, VLDL, ratios)
4. **Researches** abnormal values using live web search
5. **Writes** a plain-English explanation using CrewAI multi-agent system
6. **Validates** the output with a Qwen reasoning judge (loops back if quality is poor)
7. **Delivers** a styled web report + downloadable PDF

---

## System Architecture

```
User (text / PDF)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Backend                          │
│                                                          │
│   ┌──────────────── LangGraph Pipeline ───────────────┐  │
│   │                                                   │  │
│   │  [1] Extractor Node  ──► [2] RAG Lookup Node      │  │
│   │        │                       │                  │  │
│   │        ▼                       ▼                  │  │
│   │  [3] Calculator Node ──► [4] Researcher Node      │  │
│   │                                │                  │  │
│   │                                ▼                  │  │
│   │                     [5] CrewAI Node               │  │
│   │                       (2 AI agents)               │  │
│   │                                │                  │  │
│   │                                ▼                  │  │
│   │                     [6] Judge Node (Qwen)         │  │
│   │                       pass ─────────► [7] Finalize│  │
│   │                       fail ◄──── retry (max 2)    │  │
│   └───────────────────────────────────────────────────┘  │
│                                                          │
│   /analyze/text   /analyze/pdf   /report/{id}            │
│   /download/{id}  /metrics       /health                 │
└──────────────────────────────────────────────────────────┘
        │
        ▼
  Frontend (Vanilla JS + CSS)
  ┌─────────────────────────────────┐
  │  • Animated results rendering   │
  │  • HIGH ↑ / LOW ↓ badges        │
  │  • Calculated metrics cards     │
  │  • PDF download (Arial TTF)     │
  └─────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Orchestration** | LangGraph | Stateful multi-agent pipeline with conditional retry loop |
| **Agent Framework** | CrewAI | Explainer + Report Architect agents (sequential) |
| **LLM (Pipeline)** | Groq — `llama-3.3-70b-versatile` | Extraction, Research, Judge (12K TPM pool) |
| **LLM (Crew)** | Groq — `llama-4-scout-17b-16e-instruct` | Report writing (30K TPM pool — separated to avoid rate limits) |
| **Judge** | Groq — `qwen/qwen3-32b` | Quality validation with pass/fail + feedback |
| **RAG** | ChromaDB + `all-MiniLM-L6-v2` | WHO reference range lookup for missing test values |
| **Web Search** | Tavily API | Real-time context for abnormal lab values |
| **PDF Extraction** | PyMuPDF (fitz) | Extracts text from uploaded lab report PDFs |
| **PDF Generation** | fpdf2 + Arial TTF | Unicode-capable health report PDF output |
| **API** | FastAPI + Uvicorn | REST endpoints for analysis, reports, metrics |
| **Frontend** | Vanilla HTML/CSS/JS | No framework overhead — fast, no build step |
| **CI/CD** | GitHub Actions + Render | Unit tests on push, auto-deploy on main |

---

## Project Structure

```
UltimateAiProject/
├── backend/
│   ├── main.py                  # FastAPI app + all endpoints
│   ├── graph/
│   │   ├── graph.py             # LangGraph assembly + metrics logger
│   │   ├── nodes.py             # 6 agent nodes (extract, rag, calc, research, crew, judge, finalize)
│   │   └── state.py             # Shared state TypedDict
│   ├── crew/
│   │   ├── agents.py            # CrewAI agent definitions (Llama4-Scout)
│   │   └── tasks.py             # CrewAI task definitions + run_crew()
│   ├── tools/
│   │   ├── calculator.py        # Medical formulas (eGFR, LDL, Non-HDL, BMI, ratios)
│   │   └── search.py            # Tavily web search wrapper
│   ├── utils/
│   │   └── report_generator.py  # fpdf2 PDF generation (Arial TTF, Unicode-safe)
│   └── ingest.py                # ChromaDB ingestion + retrieval
├── frontend/
│   ├── index.html               # Single-page app
│   ├── style.css                # Dark theme + animations + badge styles
│   └── script.js                # API calls + markdown rendering + badge injection
├── documents/
│   └── medical_ranges.txt       # WHO reference ranges corpus (RAG source)
├── tests/
│   ├── test_calculator.py       # 8 unit tests — medical formula correctness
│   └── test_pdf.py              # 8 unit tests — PDF generation + Unicode safety
├── .github/workflows/ci.yml     # GitHub Actions CI (runs on push/PR)
├── render.yaml                  # Render.com deployment config
├── metrics.jsonl                # Per-request performance log (auto-generated)
├── test_pipeline.py             # Integration test (requires live server)
└── requirements.txt
```

---

## Setup & Run Locally

### Prerequisites
- Python 3.11
- Conda (or venv)
- A [Groq API key](https://console.groq.com) (free)
- A [Tavily API key](https://tavily.com) (free tier — 1000 searches/month)

### 1. Clone & Install

```bash
git clone https://github.com/Mahajan-Sachin/HealthReport.git
cd mediscan-ai

conda create -n langgraph_env python=3.11
conda activate langgraph_env
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

GENERATOR_MODEL=meta-llama/llama-3.3-70b-versatile
JUDGE_MODEL=qwen/qwen3-32b
CREW_MODEL=groq/meta-llama/llama-4-scout-17b-16e-instruct
```

### 3. Build the RAG Database

```bash
python -c "from backend.ingest import ingest_documents; ingest_documents()"
```

### 4. Start the Server

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze/text` | Analyze pasted lab report text |
| `POST` | `/analyze/pdf` | Upload and analyze a lab report PDF |
| `GET` | `/report/{report_id}` | Fetch full structured report JSON |
| `GET` | `/download/{report_id}` | Download report as PDF |
| `GET` | `/metrics` | View last 20 request performance metrics |
| `GET` | `/health` | Server health check |

### Example Request

```bash
curl -X POST http://localhost:8000/analyze/text \
  -H "Content-Type: application/json" \
  -d '{
    "report_text": "Hemoglobin: 9.2 g/dL [L]\nTotal Cholesterol: 238 mg/dL [H]",
    "patient_name": "Test Patient",
    "patient_age": 42,
    "patient_sex": "male"
  }'
```

---

## Metrics & Observability

Every request is automatically logged to `metrics.jsonl`. View via:

```
GET /metrics
```

```json
{
  "total_requests_logged": 5,
  "averages": { "total_seconds": 43.3, "tests_found": 14 },
  "requests": [{
    "timestamp": "2026-06-20T01:20:57",
    "total_seconds": 43.33,
    "node_timings": {
      "extract": 1.88,
      "rag": 0.02,
      "calculate": 0.0,
      "research": 13.95,
      "crew": 14.59,
      "judge": 12.88
    },
    "tests_found": 16,
    "abnormal_count": 14,
    "judge_iterations": 2,
    "status": "success"
  }]
}
```

**Key insight:** `extract + rag + calculate` = ~2s (4% of total time). `research + crew + judge` = ~41s (96%). The LLM nodes dominate — future optimization target is parallel execution of research and crew.

---

## Running Tests

```bash
# Unit tests only (no API keys needed, runs in ~3 seconds)
python -m pytest tests/ -v

# Integration test (requires live server + real API keys)
python test_pipeline.py
```

| Test Suite | Tests | What It Covers |
|------------|-------|----------------|
| `test_calculator.py` | 8 | eGFR formula, Friedewald LDL, Non-HDL, BUN ratio, edge cases |
| `test_pdf.py` | 8 | PDF generation, Unicode safety, markdown stripping |

---

## CI/CD

- **CI**: GitHub Actions runs all unit tests on every push to `main`/`dev` and on PRs
- **CD**: Render auto-deploys on every merge to `main`

```
Push to main
    │
    ├── GitHub Actions CI
    │     └── python -m pytest tests/ -v   ← must pass
    │
    └── Render Auto-Deploy
          └── pip install + uvicorn start
```

### Deploy to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect repo
3. Add secrets in Render dashboard: `GROQ_API_KEY`, `TAVILY_API_KEY`
4. Deploy — `render.yaml` handles the rest

---

## Design Decisions

**Why two separate Groq models?**
Groq enforces TPM limits per model. Using `llama-3.3-70b` (12K TPM) for LangGraph nodes and `llama-4-scout-17b` (30K TPM) for CrewAI separates the workloads across two independent rate limit pools, preventing one from starving the other.

**Why no LLM output caching?**
Lab report values change between visits — the same patient with the same name/age could have completely different results after an illness. Caching on patient identity would return stale analysis. The only valid cache is the RAG reference range data (ChromaDB), which doesn't change per-request.

**Why Vanilla JS (no React/Next.js)?**
No build step. No bundler. The frontend is served as static files by FastAPI. Any change to `script.js` or `style.css` is live immediately — ideal for rapid iteration on a single-page tool.

---

## Limitations

- **Rate limits**: Groq free tier limits throughput. Concurrent users will queue at the API level.
- **PDF scans**: Scanned/image-based PDFs are not supported (only text-extractable PDFs). OCR (Tesseract) not yet integrated.
- **In-memory report store**: Reports are lost on server restart. Acceptable for a public demo tool — would need Redis/SQLite for persistent doctor-facing use.
- **Arial font**: PDF generation requires Arial TTF (available on Windows). Linux deployments fall back to ASCII-safe mode.

---

## License

MIT — free to use, modify, and deploy.

---

*Built with LangGraph + CrewAI + Groq + FastAPI*
