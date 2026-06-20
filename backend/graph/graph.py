"""
MediScan AI — LangGraph Graph Assembly
Assembles all nodes into a stateful multi-agent graph with conditional edges.

Flow:
  extract → rag_lookup → calculate → research → crew → judge
                                                    ↑         ↓ fail (retry < 2)
                                                    └─────────┘
                                                         ↓ pass
                                                      finalize
"""

import time
import json
from datetime import datetime
from pathlib import Path
from langgraph.graph import StateGraph, START, END

from backend.graph.state import MediScanState
from backend.graph.nodes import (
    extract_node,
    rag_lookup_node,
    calculate_node,
    research_node,
    judge_node,
    finalize_node,
    should_retry,
)
from backend.crew.tasks import run_crew


# ─── Crew Node (wraps CrewAI inside LangGraph) ────────────────────────────────

def crew_node(state: MediScanState) -> dict:
    """
    Calls the CrewAI crew (Explainer + Report Architect) using Llama4-Scout.
    Passes judge feedback on retries so crew can improve.
    """
    _t0 = time.time()
    print("[CREW] [Node 5] CrewAI crew generating explanation...")

    crew_output = run_crew(
        all_tests=state.get("rag_enriched_tests", state.get("extracted_tests", [])),
        calculated_metrics=state.get("calculated_metrics", []),
        research_context=state.get("research_context", {}),
        judge_feedback=state.get("judge_feedback", ""),
        patient_name=state.get("patient_name", "Patient"),
        patient_age=state.get("patient_age", 0),
        patient_sex=state.get("patient_sex", ""),
    )

    duration = round(time.time() - _t0, 2)
    print(f"   [OK] Crew output: {len(crew_output)} characters in {duration}s")
    timings = dict(state.get("node_timings") or {})
    existing = timings.get("crew", 0)
    timings["crew"] = round(existing + duration, 2)  # accumulate across retries
    return {"crew_output": crew_output, "node_timings": timings}


# ─── Build the Graph ──────────────────────────────────────────────────────────

def build_graph():
    """
    Constructs and compiles the MediScan AI LangGraph.
    Returns a compiled graph ready to invoke.
    """
    builder = StateGraph(MediScanState)

    # Register all nodes
    builder.add_node("extract", extract_node)
    builder.add_node("rag_lookup", rag_lookup_node)
    builder.add_node("calculate", calculate_node)
    builder.add_node("research", research_node)
    builder.add_node("crew", crew_node)
    builder.add_node("judge", judge_node)
    builder.add_node("finalize", finalize_node)

    # Linear flow: START → extract → rag → calculate → research → crew
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "rag_lookup")
    builder.add_edge("rag_lookup", "calculate")
    builder.add_edge("calculate", "research")
    builder.add_edge("research", "crew")

    # crew → judge
    builder.add_edge("crew", "judge")

    # Conditional: judge → retry (crew) OR finalize
    builder.add_conditional_edges(
        "judge",
        should_retry,
        {
            "retry": "crew",       # fail + retries remaining → back to crew
            "finalize": "finalize" # pass OR max retries → finalize
        }
    )

    # finalize → END
    builder.add_edge("finalize", END)

    return builder.compile()


# ─── Singleton Graph Instance ─────────────────────────────────────────────────

_graph = None

def get_graph():
    """Returns singleton compiled graph (built once, reused per request)."""
    global _graph
    if _graph is None:
        print("[BUILD] Building LangGraph...")
        _graph = build_graph()
        print("[OK] LangGraph ready")
    return _graph


# ─── Main Runner ─────────────────────────────────────────────────────────────

def run_analysis(
    report_text: str,
    patient_name: str,
    patient_age: int,
    patient_sex: str,
) -> dict:
    """
    Main entry point for report analysis.
    Called by FastAPI endpoints.
    Returns the final_report dict.
    """
    graph = get_graph()

    initial_state: MediScanState = {
        "raw_input": report_text,
        "patient_name": patient_name,
        "patient_age": patient_age,
        "patient_sex": patient_sex,
        "extracted_tests": [],
        "rag_enriched_tests": [],
        "calculated_metrics": [],
        "abnormal_tests": [],
        "research_context": {},
        "crew_output": "",
        "judge_feedback": "",
        "judge_result": "",
        "retry_count": 0,
        "final_report": {},
        "node_timings": {},        # ← metrics: filled by each node
        "error": None,
    }

    print("\n" + "="*50)
    print("[START] MediScan AI Analysis Started")
    print("="*50)

    _pipeline_start = time.time()
    final_state = graph.invoke(initial_state)
    total_seconds = round(time.time() - _pipeline_start, 2)

    print("="*50)
    print(f"[OK] Analysis Complete in {total_seconds}s")
    print("="*50 + "\n")

    report = final_state.get("final_report", {})

    # ── Log metrics to file (one JSON line per request) ───────────────────────
    _log_metrics(report, total_seconds)

    return report


# ── Metrics Logger ────────────────────────────────────────────────────────────

_METRICS_FILE = Path(__file__).parent.parent.parent / "metrics.jsonl"

def _log_metrics(report: dict, total_seconds: float):
    """Appends one JSON line to metrics.jsonl after each completed request."""
    try:
        perf = report.get("performance", {})
        entry = {
            "timestamp": datetime.now().isoformat(),
            "total_seconds": total_seconds,
            "node_timings": perf.get("node_timings_seconds", {}),
            "tests_found": report.get("summary", {}).get("total_tests", 0),
            "abnormal_count": report.get("summary", {}).get("abnormal_count", 0),
            "judge_iterations": report.get("judge_iterations", 1),
            "status": "success" if report else "error",
        }
        with open(_METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[METRICS] Log error (non-critical): {e}")
