"""
Friday :: News Aggregator
Multi-source news without API keys required.

Sources (all keyless):
  - HackerNews (top, best, new) via official Firebase API
  - Reddit (subreddit .json — public, no auth)
  - RSS feeds (configurable list)
  - Google News RSS (unofficial, works)

Returns normalized items:
  {"title": str, "url": str, "source": str, "score": int | None,
   "comments": int | None, "published": str | None, "summary": str | None}
"""
from __future__ import annotations
import html
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

UA = "Mozilla/5.0 Friday/2.0"
TIMEOUT = 12


DEFAULT_RSS = [
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Hacker News front", "https://hnrss.org/frontpage"),
    ("Anthropic blog", "https://www.anthropic.com/news/rss.xml"),
    ("OpenAI blog", "https://openai.com/blog/rss.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("Bloomberg Tech", "https://feeds.bloomberg.com/technology/news.rss"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
]

DEFAULT_SUBREDDITS = [
    "artificial", "LocalLLaMA", "ChatGPT", "singularity",
    "Entrepreneur", "SaaS", "startups",
    "IndiaInvestments", "india",
]


def hacker_news(mode: str = "top", limit: int = 15) -> list[dict]:
    """HN via Firebase API. mode: top | best | new | ask | show"""
    url = f"https://hacker-news.firebaseio.com/v0/{mode}stories.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
        ids = json.loads(r.read())[:limit]
    items = []
    for sid in ids:
        try:
            iurl = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
            ireq = urllib.request.Request(iurl, headers={"User-Agent": UA})
            with urllib.request.urlopen(ireq, timeout=TIMEOUT, context=_SSL) as r:
                it = json.loads(r.read())
            if not it or it.get("type") != "story":
                continue
            items.append({
                "title": it.get("title", ""),
                "url": it.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                "source": "hackernews",
                "score": it.get("score"),
                "comments": it.get("descendants"),
                "published": datetime.fromtimestamp(it.get("time", 0), tz=timezone.utc).isoformat(),
                "summary": None,
            })
        except Exception:
            continue
    return items


def reddit_sub(subreddit: str, sort: str = "hot", limit: int = 10) -> list[dict]:
    """Public Reddit JSON. No auth needed."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
            data = json.loads(r.read())
    except Exception:
        return []
    items = []
    for post in data.get("data", {}).get("children", []):
        d = post.get("data", {})
        if d.get("stickied") or d.get("over_18"):
            continue
        items.append({
            "title": d.get("title", ""),
            "url": d.get("url_overridden_by_dest") or f"https://reddit.com{d.get('permalink', '')}",
            "source": f"reddit/{subreddit}",
            "score": d.get("score"),
            "comments": d.get("num_comments"),
            "published": datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).isoformat(),
            "summary": d.get("selftext", "")[:280] or None,
        })
    return items


# ------------- RSS (ultra-simple parser) -------------
_RSS_ITEM = re.compile(r"<item[^>]*>(.*?)</item>", re.DOTALL | re.IGNORECASE)
_RSS_ENTRY = re.compile(r"<entry[^>]*>(.*?)</entry>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def _rss_field(block: str, *tags) -> str:
    for tag in tags:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.DOTALL | re.IGNORECASE)
        if m:
            raw = m.group(1)
            # Handle CDATA
            cd = re.search(r"<!\[CDATA\[(.*?)\]\]>", raw, re.DOTALL)
            if cd:
                raw = cd.group(1)
            return html.unescape(_TAG.sub("", raw)).strip()
    return ""


def _rss_link(block: str) -> str:
    # Atom: <link href="..."/> ; RSS: <link>URL</link>
    m = re.search(r'<link[^>]+href="([^"]+)"', block, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"<link[^>]*>([^<]+)</link>", block, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def rss(feed_url: str, source_name: str | None = None, limit: int = 10) -> list[dict]:
    req = urllib.request.Request(feed_url, headers={"User-Agent": UA,
                                                      "Accept": "application/rss+xml,application/xml,text/xml"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
            body = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    items = []
    blocks = _RSS_ITEM.findall(body) or _RSS_ENTRY.findall(body)
    for block in blocks[:limit]:
        title = _rss_field(block, "title")
        url = _rss_link(block)
        summary = _rss_field(block, "description", "summary", "content:encoded", "content")
        published = _rss_field(block, "pubDate", "published", "updated")
        if not title or not url:
            continue
        items.append({
            "title": title, "url": url, "source": source_name or "rss",
            "score": None, "comments": None,
            "published": published or None,
            "summary": summary[:400] if summary else None,
        })
    return items


def google_news(topic: str, limit: int = 10) -> list[dict]:
    """Unofficial Google News RSS — respects topic query."""
    q = urllib.parse.quote(topic)
    feed = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return rss(feed, source_name=f"google_news:{topic}", limit=limit)


# ------------- Aggregate pipelines -------------
def world_pulse(limit_per_source: int = 8) -> dict:
    """
    One-shot 'what's happening' snapshot. Pulls from all keyless sources.
    Returns grouped + flat for LLM consumption.
    """
    out = {"fetched_at": datetime.now().isoformat(), "groups": {}}
    # Hacker News
    try:
        out["groups"]["hackernews"] = hacker_news("top", limit=limit_per_source)
    except Exception as e:
        out["groups"]["hackernews"] = {"error": str(e)}
    # Reddit key subs
    reddit_items = []
    for sub in ["artificial", "Entrepreneur", "worldnews", "technology"]:
        reddit_items.extend(reddit_sub(sub, "hot", limit=5))
    out["groups"]["reddit"] = reddit_items
    # RSS headline sample (expanded for better world coverage)
    rss_items = []
    # Tech/AI bias (Bhargav's focus)
    for name, feed in DEFAULT_RSS[:5]:
        rss_items.extend(rss(feed, source_name=name, limit=5))
    # Global/General Pulse
    rss_items.extend(rss("https://feeds.reuters.com/Reuters/worldNews", source_name="Reuters", limit=8))
    rss_items.extend(rss("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en", source_name="GoogleNews", limit=5))
    
    out["groups"]["rss"] = rss_items
    # Flat list sorted by score where available, then recent
    flat = []
    for src_name, src in out["groups"].items():
        if isinstance(src, list):
            flat.extend(src)
    out["flat"] = flat
    out["total"] = len(flat)
    return out


def topic_pulse(topic: str, limit_per_source: int = 6) -> dict:
    """Topic-focused news scan. Google News RSS + Reddit search + HN search."""
    out = {"topic": topic, "fetched_at": datetime.now().isoformat(), "items": []}
    # Google News RSS
    out["items"].extend(google_news(topic, limit=limit_per_source))
    # HN search via Algolia (keyless)
    try:
        q = urllib.parse.quote(topic)
        url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={limit_per_source}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
            data = json.loads(r.read())
        for hit in data.get("hits", []):
            out["items"].append({
                "title": hit.get("title", ""),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "source": "hackernews",
                "score": hit.get("points"),
                "comments": hit.get("num_comments"),
                "published": hit.get("created_at"),
                "summary": None,
            })
    except Exception:
        pass
    # Reddit search (keyless)
    try:
        q = urllib.parse.quote(topic)
        url = f"https://www.reddit.com/search.json?q={q}&sort=relevance&limit={limit_per_source}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
            data = json.loads(r.read())
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            out["items"].append({
                "title": d.get("title", ""),
                "url": d.get("url_overridden_by_dest") or f"https://reddit.com{d.get('permalink', '')}",
                "source": f"reddit/{d.get('subreddit', '?')}",
                "score": d.get("score"), "comments": d.get("num_comments"),
                "published": datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).isoformat(),
                "summary": (d.get("selftext") or "")[:280] or None,
            })
    except Exception:
        pass
    out["total"] = len(out["items"])
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
        r = topic_pulse(topic)
        print(f"Topic pulse '{topic}': {r['total']} items")
        for it in r["items"][:12]:
            print(f"  [{it['source']}] {it['title']}")
            print(f"    {it['url']}")
    else:
        r = world_pulse()
        print(f"World pulse: {r['total']} items across {len(r['groups'])} groups")
        for group, items in r["groups"].items():
            if isinstance(items, list):
                print(f"\n{group} ({len(items)}):")
                for it in items[:6]:
                    print(f"  · {it['title'][:100]}")
