"""
MediScan AI — Web Search Tool
Primary: Tavily API (free 1000/month)
Fallback: DuckDuckGo (fully free, no key)
"""

import os
from typing import Optional


def search_medical_info(query: str, max_results: int = 3) -> str:
    """
    Searches for medical context.
    Tries Tavily first, falls back to DuckDuckGo.
    Returns a brief, clean summary string (max ~300 words).
    """
    result = _try_tavily(query, max_results)
    if result:
        return result

    # Fallback
    result = _try_duckduckgo(query, max_results)
    if result:
        return result

    return f"No additional context found for: {query}"


def _try_tavily(query: str, max_results: int) -> Optional[str]:
    """Tavily search — reliable, structured medical results."""
    try:
        from tavily import TavilyClient

        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            return None

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )

        # Use the direct answer if available
        if response.get("answer"):
            return _trim(response["answer"])

        # Otherwise combine top result snippets
        snippets = []
        for r in response.get("results", [])[:max_results]:
            content = r.get("content", "").strip()
            if content:
                snippets.append(content)

        return _trim(" ".join(snippets)) if snippets else None

    except Exception:
        return None


def _try_duckduckgo(query: str, max_results: int) -> Optional[str]:
    """DuckDuckGo fallback — no API key needed."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(
                query,
                max_results=max_results,
                safesearch="moderate"
            ):
                body = r.get("body", "").strip()
                if body:
                    results.append(body)

        return _trim(" ".join(results)) if results else None

    except Exception:
        return None


def _trim(text: str, max_words: int = 120) -> str:
    """Trim to max_words to keep LLM input under token limits."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."
