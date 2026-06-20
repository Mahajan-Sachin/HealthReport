"""
MediScan AI — CrewAI Agent Definitions
100% Groq (llama-3.3-70b-versatile) — no Gemini needed.
CrewAI 0.80+ with LiteLLM. cache_breakpoint disabled via cache=False on agents.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Must set BEFORE importing litellm/crewai — stops cache_breakpoint injection
os.environ["LITELLM_CACHE"] = "False"
os.environ["LITELLM_DROP_PARAMS"] = "True"
os.environ["CREWAI_DISABLE_CACHE"] = "True"

# ── Monkey-patch fix for CrewAI cache_breakpoint bug ──────────────────────────
# CrewAI injects cache_breakpoint into messages (Anthropic-only feature).
# Groq rejects it with 400 error. This patch makes mark_cache_breakpoint a no-op.
# Source: CrewAI community fix for v1.14.4 bug
try:
    import crewai.llms.cache as _crewai_cache
    _crewai_cache.mark_cache_breakpoint = lambda msg: msg
except (ImportError, AttributeError):
    pass  # module path may differ across versions — safe to ignore
# ──────────────────────────────────────────────────────────────────────────────

import litellm
from crewai import Agent, LLM

litellm.cache = None
litellm.drop_params = True


def get_groq_llm() -> LLM:
    """
    LLM for CrewAI agents — Meta Llama 4 Scout 17B on Groq.
    Why: 30,000 TPM (vs 12,000 for llama-3.3-70b) — separate pool from LangGraph nodes.
    LangGraph uses llama-3.3-70b (12K TPM), CrewAI uses llama-4-scout (30K TPM).
    No more rate limit conflicts between the two.
    """
    return LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.4,
        max_tokens=4096,
    )


def get_explainer_agent() -> Agent:
    """
    Senior Medical Content Writer.
    Translates lab values into clear, empathetic plain English.
    """
    return Agent(
        role="Senior Medical Content Writer",
        goal=(
            "Explain each lab test result in simple, accurate, empathetic language "
            "that any adult can understand without a medical background."
        ),
        backstory=(
            "You are an experienced medical writer with 15 years of experience translating "
            "complex clinical lab results into patient-friendly language. You specialize in "
            "making people feel informed, not scared. You always prioritize clarity over "
            "completeness, and you never use unexplained medical jargon. "
            "You know the difference between explaining and diagnosing, and you always "
            "stay within the boundary of explanation."
        ),
        llm=get_groq_llm(),
        verbose=False,
        allow_delegation=False,
        cache=False,        # <-- disables CrewAI prompt caching (prevents cache_breakpoint)
    )


def get_report_architect_agent() -> Agent:
    """
    Health Report Designer.
    Structures the final report with clear sections and doctor questions.
    """
    return Agent(
        role="Health Report Architect",
        goal=(
            "Organize all medical explanations into a clear, structured, and actionable "
            "health report that patients can bring to their doctor."
        ),
        backstory=(
            "You are a specialist in health communication design. You have worked with "
            "major healthcare companies to create patient-facing report templates. "
            "Your reports are known for being scannable, organized, and empowering — "
            "they give patients exactly what they need to have an informed conversation "
            "with their doctor. You always include a list of smart questions patients "
            "should ask their doctor based on their results."
        ),
        llm=get_groq_llm(),
        verbose=False,
        allow_delegation=False,
        cache=False,        # <-- disables CrewAI prompt caching (prevents cache_breakpoint)
    )


# Keep old name as alias for backward compatibility
get_gemini_llm = get_groq_llm
