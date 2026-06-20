"""
MediScan AI — LangGraph State Definition
All agents share and update this single state object.
"""

from typing import TypedDict, Optional


class MediScanState(TypedDict):
    # ── User Inputs ────────────────────────────────────────────────────────────
    raw_input: str                  # Report text (from manual entry or PDF extraction)
    patient_name: str               # Optional display name
    patient_age: int                # Required for eGFR calculation
    patient_sex: str                # "male" or "female" — required for eGFR

    # ── Stage 1: Extraction ───────────────────────────────────────────────────
    extracted_tests: list           # List of dicts: {test_name, value, unit, ref_range, flag}

    # ── Stage 2: RAG Enrichment ───────────────────────────────────────────────
    rag_enriched_tests: list        # Tests with missing ref_ranges filled from RAG corpus

    # ── Stage 3: Calculations ─────────────────────────────────────────────────
    calculated_metrics: list        # Derived metrics: eGFR, BMI, LDL, ratios, etc.

    # ── Stage 4: Research ─────────────────────────────────────────────────────
    abnormal_tests: list            # Filtered: only flagged H/L/abnormal tests
    research_context: dict          # {test_name: "brief web research summary"}

    # ── Stage 5: CrewAI Output ────────────────────────────────────────────────
    crew_output: str                # Raw crew result (explanations + report structure)

    # ── Stage 6: Judge ────────────────────────────────────────────────────────
    judge_feedback: str             # Qwen judge's specific feedback
    judge_result: str               # "pass" or "fail"
    retry_count: int                # Current retry count (max 2)

    # ── Stage 7: Final Output ─────────────────────────────────────────────────
    final_report: dict              # Structured report ready for API response

    # ── Metrics / Timing ──────────────────────────────────────────────────────
    node_timings: dict              # {node_name: seconds} — how long each node took

    # ── Error Handling ────────────────────────────────────────────────────────
    error: Optional[str]            # Non-None if a node encountered an error
