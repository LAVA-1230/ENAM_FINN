"""Optional web search for management bios (Tavily or Brave). Off unless a key is configured.
LinkedIn is never scraped: only a search API's public snippets are used."""
import logging

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)


def search(query: str, n: int = 3) -> list[dict]:
    s = get_settings()
    if s.websearch_provider == "none" or not s.websearch_api_key:
        return []
    try:
        if s.websearch_provider == "tavily":
            r = httpx.post("https://api.tavily.com/search", timeout=20,
                           json={"api_key": s.websearch_api_key, "query": query, "max_results": n})
            r.raise_for_status()
            return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")[:600]}
                    for x in r.json().get("results", [])[:n]]
        if s.websearch_provider == "brave":
            r = httpx.get("https://api.search.brave.com/res/v1/web/search", timeout=20,
                          params={"q": query, "count": n},
                          headers={"X-Subscription-Token": s.websearch_api_key, "Accept": "application/json"})
            r.raise_for_status()
            return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("description", "")[:600]}
                    for x in r.json().get("web", {}).get("results", [])[:n]]
    except Exception as e:  # noqa: BLE001
        log.info("websearch failed: %s", e)
    return []
