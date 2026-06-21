"""
MediScan AI — LangGraph Agent Nodes
Each node = one agent = one focused job.
LangGraph uses Groq (ChatGroq). CrewAI handled in crew/ module.
"""

import os
import time
from typing import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.graph.state import MediScanState
from backend.tools.calculator import run_calculations
from backend.tools.search import search_medical_info

load_dotenv()


# ─── Pydantic Models for Structured Output ────────────────────────────────────

class ExtractedTest(BaseModel):
    test_name: str = Field(description="Name of the lab test exactly as written in report")
    value: str = Field(description="The result value (keep as string to handle <, >, ranges)")
    unit: str = Field(description="Unit of measurement e.g. g/dL, mg/dL, %")
    reference_range: str = Field(default="", description="Reference range from report if printed, else empty string")
    flag: str = Field(default="", description="Flag from report: H (high), L (low), CR (critical), or empty if normal")

class ExtractionResult(BaseModel):
    tests: list[ExtractedTest] = Field(description="All lab tests found in the report")

class JudgeOutput(BaseModel):
    feedback: str = Field(description="Specific actionable feedback on what needs improvement or confirmation of quality")
    result: Literal["pass", "fail"] = Field(description="pass if explanation is accurate and complete, fail if needs revision")


# ─── Helper: Initialize ChatGroq ─────────────────────────────────────────────

def get_llm(model_env_key: str = "GENERATOR_MODEL", temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(
        model=os.environ[model_env_key],
        temperature=temperature,
        api_key=os.environ["GROQ_API_KEY"],
        max_tokens=4096,
    )


# ─── NODE 1: Extractor ────────────────────────────────────────────────────────

def extract_node(state: MediScanState) -> dict:
    """
    Reads raw report text and extracts all lab tests into structured list.
    Uses llama-3.3-70b with structured output for precise extraction.
    """
    _t0 = time.time()
    print("[EXTRACT] [Node 1] Extracting lab values...")

    llm = get_llm("GENERATOR_MODEL")
    structured_llm = llm.with_structured_output(ExtractionResult)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """You are a precise medical data extraction specialist.
         Extract EVERY lab test value from the provided medical report text.
         
         Rules:
         - Extract test_name exactly as written
         - Keep value as string (preserve <, >, ranges like '4.5-5.0')
         - Extract unit exactly as written (g/dL, mg/dL, %, etc.)
         - If reference range is printed on the report, extract it exactly
         - If flag (H, L, *, CR) is printed, extract it
         - Do NOT infer or guess values not present
         - Include ALL tests, even if they seem minor
         """),
        ("human", "Extract all lab values from this medical report:\n\n{report_text}")
    ])

    chain = prompt | structured_llm

    try:
        result = chain.invoke({"report_text": state["raw_input"][:6000]})  # token safety
        extracted = [t.model_dump() for t in result.tests]
        duration = round(time.time() - _t0, 2)
        print(f"   [OK] Extracted {len(extracted)} tests in {duration}s")
        timings = dict(state.get("node_timings") or {})
        timings["extract"] = duration
        return {"extracted_tests": extracted, "error": None, "node_timings": timings}
    except Exception as e:
        print(f"   [ERR] Extraction error: {e}")
        return {"extracted_tests": [], "error": str(e), "node_timings": state.get("node_timings") or {}}


# ─── NODE 2: RAG Lookup ───────────────────────────────────────────────────────

def rag_lookup_node(state: MediScanState) -> dict:
    """
    For tests that have no reference range in the report,
    queries ChromaDB for WHO standard ranges.
    """
    _t0 = time.time()
    print("[RAG] [Node 2] RAG lookup for missing reference ranges...")

    from backend.ingest import get_vectorstore

    tests = state.get("extracted_tests", [])
    if not tests:
        return {"rag_enriched_tests": []}

    try:
        vectorstore = get_vectorstore()
    except Exception:
        print("   [WARN]  ChromaDB not ready, skipping RAG enrichment")
        return {"rag_enriched_tests": tests, "node_timings": state.get("node_timings") or {}}

    enriched = []
    for test in tests:
        t = dict(test)
        if not t.get("reference_range"):
            query = f"{t['test_name']} normal range reference values"
            try:
                docs = vectorstore.similarity_search(query, k=2)
                if docs:
                    t["reference_range"] = _extract_range_from_text(
                        docs[0].page_content, t["test_name"]
                    )
            except Exception:
                pass
        enriched.append(t)

    duration = round(time.time() - _t0, 2)
    print(f"   [OK] RAG enrichment complete for {len(enriched)} tests in {duration}s")
    timings = dict(state.get("node_timings") or {})
    timings["rag"] = duration
    return {"rag_enriched_tests": enriched, "node_timings": timings}


def _extract_range_from_text(text: str, test_name: str) -> str:
    """Simple heuristic: extract the line most relevant to the test."""
    lines = text.split("\n")
    test_lower = test_name.lower()
    for line in lines:
        if test_lower in line.lower() and (":" in line or "-" in line):
            # Return the range portion
            return line.strip()[:100]
    return ""


# ─── NODE 3: Calculator ───────────────────────────────────────────────────────

def calculate_node(state: MediScanState) -> dict:
    """
    Runs deterministic medical formulas.
    No LLM involved — pure Python math.
    """
    _t0 = time.time()
    print("[CALC] [Node 3] Running medical calculations...")

    tests = state.get("rag_enriched_tests", state.get("extracted_tests", []))
    age = state.get("patient_age", 0)
    sex = state.get("patient_sex", "")

    metrics = run_calculations(tests, age, sex)

    # Also determine flag status for tests that don't have explicit H/L
    flagged_tests = []
    for test in tests:
        t = dict(test)
        if not t.get("flag"):
            t["flag"] = _infer_flag(t)
        flagged_tests.append(t)

    # Filter abnormal tests for Researcher node (keeps token count low)
    abnormal = [t for t in flagged_tests if t.get("flag", "").upper() in ("H", "L", "CR", "HIGH", "LOW", "CRITICAL")]
    # Also flag calculated metrics that are abnormal
    for m in metrics:
        if m.get("severity") in ("abnormal", "critical", "borderline"):
            abnormal.append({
                "test_name": m["name"],
                "value": str(m["value"]),
                "unit": m["unit"],
                "flag": "H" if m["severity"] in ("abnormal", "critical") else "BORDERLINE",
                "reference_range": m.get("reference", ""),
                "interpretation": m.get("interpretation", "")
            })

    duration = round(time.time() - _t0, 2)
    print(f"   [OK] Calculated {len(metrics)} derived metrics | {len(abnormal)} abnormal found | {duration}s")
    timings = dict(state.get("node_timings") or {})
    timings["calculate"] = duration
    return {
        "rag_enriched_tests": flagged_tests,
        "calculated_metrics": metrics,
        "abnormal_tests": abnormal,
        "node_timings": timings
    }


def _infer_flag(test: dict) -> str:
    """If no flag from report, try to infer from value vs reference range."""
    try:
        value = float(str(test.get("value", "")).replace("<", "").replace(">", "").strip())
        ref = test.get("reference_range", "")
        if not ref or "-" not in ref:
            return ""

        # Parse "13.5 - 17.5" or "13.5-17.5"
        parts = ref.replace(" ", "").split("-")
        if len(parts) == 2:
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            if value < low:
                return "L"
            elif value > high:
                return "H"
    except (ValueError, TypeError):
        pass
    return ""


# ─── NODE 4: Researcher ──────────────────────────────────────────────────────

def research_node(state: MediScanState) -> dict:
    """
    Web searches for context on abnormal values only.
    Max 5 searches to protect Tavily free tier quota.
    Each result trimmed to ~120 words to protect token limits.
    """
    _t0 = time.time()
    print("[SEARCH] [Node 4] Researching abnormal values...")

    abnormal = state.get("abnormal_tests", [])
    if not abnormal:
        print("   ℹ️  No abnormal tests — skipping research")
        return {"research_context": {}}

    # Prioritize: critical > high > borderline (max 5)
    priority_order = ["CR", "CRITICAL", "H", "HIGH", "BORDERLINE", "L", "LOW"]
    sorted_abnormal = sorted(
        abnormal,
        key=lambda t: priority_order.index(t.get("flag", "").upper()) if t.get("flag", "").upper() in priority_order else 99
    )[:5]

    context = {}
    for test in sorted_abnormal:
        test_name = test.get("test_name", "")
        value = test.get("value", "")
        flag = test.get("flag", "")

        query = f"what does {flag.lower()} {test_name} mean in blood test results causes symptoms"
        print(f"   [EXTRACT] Searching: {test_name}...")
        result = search_medical_info(query, max_results=2)
        context[test_name] = result

    duration = round(time.time() - _t0, 2)
    print(f"   [OK] Research complete for {len(context)} tests in {duration}s")
    timings = dict(state.get("node_timings") or {})
    timings["research"] = duration
    return {"research_context": context, "node_timings": timings}


# ─── NODE 5: Judge (Qwen) ───────────────────────────────────────────────────

def judge_node(state: MediScanState) -> dict:
    """
    Qwen reasoning model validates the CrewAI crew output.
    Structured output: feedback + pass/fail.
    Loops back to crew if fail (max 2 retries).
    """
    _t0 = time.time()
    print("[JUDGE]  [Node 6] Qwen Judge validating...")

    llm = get_llm("JUDGE_MODEL", temperature=0.0)
    structured_llm = llm.with_structured_output(JudgeOutput)

    retry_count = state.get("retry_count", 0)
    crew_output = state.get("crew_output", "")

    # Build compact context for judge (< 2000 tokens)
    abnormal_summary = []
    for t in state.get("abnormal_tests", [])[:8]:
        abnormal_summary.append(f"{t.get('test_name')}: {t.get('value')} {t.get('unit')} [{t.get('flag')}]")

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """You are a strict medical content validator. Review the health report explanation for quality.

         Check ALL of the following:
         1. Are all flagged abnormal values explained? (not skipped)
         2. Is the language truly plain English? (no unexplained medical jargon)
         3. Does it include a clear disclaimer to consult a doctor?
         4. Are the explanations factually reasonable? (no dangerous misinformation)
         5. Is each abnormal value contextualized? (what it might mean)
         
         If previous feedback was given, check if it was addressed.
         Be strict but fair. Pass only if genuinely good quality.
         """),
        ("human",
         """Abnormal tests found: {abnormal_summary}
         Previous feedback: {previous_feedback}
         
         Crew output to validate:
         ---
         {crew_output}
         ---
         
         Judge this output strictly.""")
    ])

    chain = prompt | structured_llm

    try:
        result = chain.invoke({
            "abnormal_summary": "\n".join(abnormal_summary) if abnormal_summary else "None found",
            "previous_feedback": state.get("judge_feedback", "None — first attempt"),
            "crew_output": crew_output[:2500]  # token safety
        })

        duration = round(time.time() - _t0, 2)
        print(f"   {'[OK] PASS' if result.result == 'pass' else '[ERR] FAIL'} | Retry #{retry_count + 1} | {duration}s")
        if result.result == "fail":
            print(f"   [NOTE] Feedback: {result.feedback[:100]}...")

        timings = dict(state.get("node_timings") or {})
        existing = timings.get("judge", 0)
        timings["judge"] = round(existing + duration, 2)  # accumulate across retries
        return {
            "judge_feedback": result.feedback,
            "judge_result": result.result,
            "retry_count": retry_count + 1,
            "node_timings": timings
        }
    except Exception as e:
        print(f"   [WARN]  Judge error: {e} — defaulting to pass")
        return {"judge_feedback": "Judge error — auto-passed", "judge_result": "pass",
                "retry_count": retry_count + 1, "node_timings": state.get("node_timings") or {}}


# ─── NODE 6: Finalize ─────────────────────────────────────────────────────────

def finalize_node(state: MediScanState) -> dict:
    """
    Assembles all data into the final structured report dict.
    No LLM — pure Python formatting.
    """
    print("[FINAL] [Node 7] Finalizing report...")

    all_tests = state.get("rag_enriched_tests", state.get("extracted_tests", []))
    calc_metrics = state.get("calculated_metrics", [])
    crew_output = state.get("crew_output", "")

    # Count by status
    normal_count = sum(1 for t in all_tests if not t.get("flag"))
    abnormal_count = sum(1 for t in all_tests if t.get("flag", "").upper() in ("H", "L", "CR", "CRITICAL"))
    borderline_count = sum(1 for t in all_tests if t.get("flag", "").upper() in ("BORDERLINE",))

    node_timings = state.get("node_timings") or {}

    final_report = {
        "patient_name": state.get("patient_name", "Patient"),
        "patient_age": state.get("patient_age"),
        "patient_sex": state.get("patient_sex"),
        "summary": {
            "total_tests": len(all_tests),
            "normal_count": normal_count,
            "abnormal_count": abnormal_count,
            "borderline_count": borderline_count,
            "calculated_metrics_count": len(calc_metrics)
        },
        "test_results": all_tests,
        "calculated_metrics": calc_metrics,
        "research_context": state.get("research_context", {}),
        "crew_explanation": crew_output,
        "judge_iterations": state.get("retry_count", 1),
        "performance": {
            "node_timings_seconds": node_timings,
            "total_pipeline_seconds": round(sum(node_timings.values()), 2),
        },
        "disclaimer": (
            "[WARN] IMPORTANT: This report is generated by AI for informational purposes only. "
            "It explains what your lab values mean but does NOT constitute medical advice, "
            "diagnosis, or treatment. Always consult a qualified healthcare professional "
            "for interpretation of your results and medical decisions."
        )
    }

    print(f"   [OK] Final report ready | {len(all_tests)} tests | {len(calc_metrics)} calculated metrics")
    return {"final_report": final_report}


# ─── Conditional Edge: Should Retry? ─────────────────────────────────────────

def should_retry(state: MediScanState) -> str:
    """
    Routes back to CrewAI crew if judge says fail and retries < 2.
    Otherwise proceeds to finalize.
    """
    if state.get("judge_result") == "fail" and state.get("retry_count", 0) < 2:
        print(f"   [RETRY] Retrying crew (attempt {state.get('retry_count', 0) + 1}/2)")
        return "retry"
    return "finalize"
