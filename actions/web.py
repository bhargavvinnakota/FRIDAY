"""
Friday :: Web Action Layer
Real internet access. Search + URL fetch + scraping.

Provider hierarchy (tries in order, uses first available):
  1. Brave Search API    — if BRAVE_API_KEY set (best quality, $5/mo free)
  2. Tavily              — if TAVILY_API_KEY set ($30/mo)
  3. Exa                 — if EXA_API_KEY set
  4. DuckDuckGo HTML     — keyless fallback, lower quality but works
  5. Wikipedia           — keyless, good for entity queries

All searches return a normalized list of results:
  [{"title": str, "url": str, "snippet": str, "source": str, "published": str | None}, ...]

URL fetcher uses BeautifulSoup for clean text extraction.
All calls timeout at 15s, never raise (return {"ok": False, "error": str}).
"""
from __future__ import annotations
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Friday/2.0"
TIMEOUT = 15

# ------------- Cache (15 min TTL) -------------
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 900  # 15 min


def _cache_get(key: str) -> Any | None:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, val = entry
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


# ------------- Providers -------------
def _brave_search(query: str, count: int = 8) -> list[dict]:
    key = os.environ.get("BRAVE_API_KEY") or _env_file_get("BRAVE_API_KEY")
    if not key:
        return []
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={count}"
    req = urllib.request.Request(url, headers={
        "X-Subscription-Token": key,
        "Accept": "application/json",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
        data = json.loads(r.read())
    results = []
    for item in (data.get("web", {}).get("results", []) or [])[:count]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": _strip_html(item.get("description", "")),
            "source": "brave",
            "published": item.get("age") or item.get("published"),
        })
    return results


def _tavily_search(query: str, count: int = 8) -> list[dict]:
    key = os.environ.get("TAVILY_API_KEY") or _env_file_get("TAVILY_API_KEY")
    if not key:
        return []
    payload = json.dumps({
        "api_key": key, "query": query, "max_results": count,
        "include_answer": False, "search_depth": "basic",
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search", data=payload,
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
        data = json.loads(r.read())
    return [{
        "title": i.get("title", ""), "url": i.get("url", ""),
        "snippet": i.get("content", "")[:400], "source": "tavily",
        "published": i.get("published_date"),
    } for i in data.get("results", [])[:count]]


def _exa_search(query: str, count: int = 8) -> list[dict]:
    key = os.environ.get("EXA_API_KEY") or _env_file_get("EXA_API_KEY")
    if not key:
        return []
    payload = json.dumps({
        "query": query, "numResults": count, "type": "auto",
        "contents": {"text": {"maxCharacters": 400}},
    }).encode()
    req = urllib.request.Request(
        "https://api.exa.ai/search", data=payload,
        headers={"Content-Type": "application/json", "x-api-key": key, "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
        data = json.loads(r.read())
    return [{
        "title": i.get("title", ""), "url": i.get("url", ""),
        "snippet": (i.get("text", "") or "")[:400], "source": "exa",
        "published": i.get("publishedDate"),
    } for i in data.get("results", [])[:count]]


def _ddg_search(query: str, count: int = 8) -> list[dict]:
    """DuckDuckGo HTML scrape — keyless fallback.
    Uses the lite endpoint which is simpler to parse and less blocked."""
    q = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        # fall back to lite endpoint
        url = f"https://lite.duckduckgo.com/lite/?q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
            html = r.read().decode("utf-8", errors="replace")
    # Parse DDG HTML result cards
    results = []
    # Each card has class="result" with result__a (link) and result__snippet
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        raw_url, raw_title, raw_snip = m.group(1), m.group(2), m.group(3)
        # DDG wraps URLs in /l/?uddg=<encoded_url>
        real_url = raw_url
        if "uddg=" in raw_url:
            try:
                real_url = urllib.parse.unquote(
                    re.search(r"uddg=([^&]+)", raw_url).group(1)
                )
            except Exception:
                pass
        results.append({
            "title": _strip_html(raw_title).strip(),
            "url": real_url,
            "snippet": _strip_html(raw_snip).strip(),
            "source": "ddg",
            "published": None,
        })
        if len(results) >= count:
            break
    # Fallback: simpler pattern if the above missed
    if not results:
        simple = re.findall(r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html)
        for url2, title2 in simple[:count]:
            results.append({"title": _strip_html(title2), "url": url2,
                            "snippet": "", "source": "ddg", "published": None})
    return results


def _wiki_search(query: str, count: int = 3) -> list[dict]:
    """Wikipedia REST — keyless, great for entity queries."""
    q = urllib.parse.quote(query)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit={count}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
        data = json.loads(r.read())
    results = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        results.append({
            "title": title,
            "url": page_url,
            "snippet": _strip_html(item.get("snippet", "")),
            "source": "wikipedia",
            "published": item.get("timestamp"),
        })
    return results


# ------------- Public API -------------
def search(query: str, count: int = 8, prefer: list[str] | None = None) -> dict:
    """
    Search the web. Tries providers in preferred order, falls back to DuckDuckGo.
    Returns {"ok": bool, "query": str, "provider": str, "results": list, "error": str | None}
    """
    if not query.strip():
        return {"ok": False, "error": "empty query", "results": []}

    cache_key = f"search::{query}::{count}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    order = prefer or ["brave", "tavily", "exa", "ddg"]
    providers = {
        "brave": _brave_search, "tavily": _tavily_search,
        "exa": _exa_search, "ddg": _ddg_search,
    }
    last_err = None
    for name in order:
        fn = providers.get(name)
        if not fn:
            continue
        try:
            results = fn(query, count=count)
            if results:
                out = {"ok": True, "query": query, "provider": name,
                       "results": results, "count": len(results), "error": None}
                _cache_set(cache_key, out)
                return out
        except Exception as e:
            last_err = f"{name}: {type(e).__name__}: {e}"
            continue

    return {"ok": False, "query": query, "provider": "none",
            "results": [], "error": last_err or "all providers returned empty"}


def fetch_url(url: str, max_chars: int = 8000) -> dict:
    """Fetch + extract readable text from a URL."""
    cache_key = f"fetch::{url}::{max_chars}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
            ctype = r.headers.get("Content-Type", "").lower()
            raw = r.read(max_chars * 8).decode("utf-8", errors="replace")
        if "html" in ctype:
            text = _html_to_text(raw)
        else:
            text = raw
        text = text[:max_chars]
        out = {"ok": True, "url": url, "text": text, "chars": len(text),
               "content_type": ctype, "error": None}
        _cache_set(cache_key, out)
        return out
    except Exception as e:
        return {"ok": False, "url": url, "text": "", "error": f"{type(e).__name__}: {e}"}


def wiki(query: str, count: int = 3) -> dict:
    """Wikipedia-first entity lookup."""
    try:
        results = _wiki_search(query, count=count)
        return {"ok": True, "provider": "wikipedia", "results": results, "count": len(results)}
    except Exception as e:
        return {"ok": False, "error": str(e), "results": []}


def multi_search(queries: list[str], per_query_count: int = 5) -> dict:
    """Run multiple searches, deduplicate by URL."""
    all_results = []
    seen_urls = set()
    per_query = {}
    for q in queries:
        r = search(q, count=per_query_count)
        per_query[q] = {"provider": r.get("provider"), "count": r.get("count", 0),
                        "ok": r.get("ok")}
        for item in r.get("results", []):
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(item)
    return {"ok": bool(all_results), "total": len(all_results),
            "per_query": per_query, "results": all_results}


# ------------- helpers -------------
_SCRIPT_STYLE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = _TAG.sub(" ", html)
    text = _WS.sub(" ", text)
    return text.strip()


def _html_to_text(html: str) -> str:
    """Minimal HTML-to-text. Not as good as BeautifulSoup but zero-dep."""
    html = _SCRIPT_STYLE.sub(" ", html)
    # Preserve paragraph/heading breaks
    html = re.sub(r"</(p|div|br|li|h[1-6]|article|section)>", "\n", html, flags=re.I)
    text = _TAG.sub(" ", html)
    # Collapse whitespace but keep line breaks
    lines = [_WS.sub(" ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _env_file_get(key: str) -> str | None:
    """Check ~/.openclaw/.env for a key without re-loading full env."""
    env_file = Path(os.path.expanduser("~/.openclaw/.env"))
    if not env_file.exists():
        return None
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                return val or None
    except Exception:
        return None
    return None


# ------------- CLI smoke test -------------
if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "what is happening in AI this week"
    print(f"Searching: {q}")
    r = search(q, count=5)
    print(f"Provider: {r['provider']}  |  Results: {r['count']}")
    for i, item in enumerate(r["results"], 1):
        print(f"\n[{i}] {item['title']}")
        print(f"    {item['url']}")
        print(f"    {item['snippet'][:200]}")
