from typing import List, Dict, Any
from ddgs import DDGS

SEARCH_RESULTS = 5  # number of DuckDuckGo results to retrieve


def duckduckgo_search(query: str, n: int = SEARCH_RESULTS) -> List[Dict[str, Any]]:
    if not query.strip():
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(
                query, max_results=n, safesearch="moderate", region="us-en"
            ):
                # r keys: title, href, body
                results.append(
                    {
                        "title": r.get("title"),
                        "url": r.get("href"),
                        "snippet": r.get("body"),
                    }
                )
    except Exception as e:
        results.append({"title": "Search error", "url": "", "snippet": str(e)})
    return results


def render_search_block(results: List[Dict[str, Any]]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title") or "No title"
        url = r.get("url") or ""
        snippet = r.get("snippet") or ""
        lines.append(f"[{i}] {title}\nURL: {url}\nSnippet: {snippet}")
    return "\n\n".join(lines)
