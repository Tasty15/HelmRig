"""Webbcrawler — Crawl4AI wrapper med SQLite-cache.

Användning i agent-skill:
    from agentkit.crawler import crawl
    result = await crawl("https://example.com")
    # → {"url": str, "content": str, "summary": str, "status": "ok"}
"""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

CACHE_DB = Path(__file__).parent / ".crawler_cache.db"
DEFAULT_MAX_CHARS = 10_000
DEFAULT_CACHE_TTL = 3600  # 1h


def _init_cache():
    with sqlite3.connect(str(CACHE_DB)) as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(url_hash TEXT PRIMARY KEY, url TEXT, content TEXT, ts INTEGER)"
        )


def _cache_get(url: str, ttl: int) -> str | None:
    _init_cache()
    h = hashlib.sha256(url.encode()).hexdigest()
    cutoff = time.time() - ttl
    with sqlite3.connect(str(CACHE_DB)) as c:
        row = c.execute(
            "SELECT content FROM cache WHERE url_hash=? AND ts > ?", (h, cutoff)
        ).fetchone()
    return row[0] if row else None


def _cache_set(url: str, content: str):
    _init_cache()
    h = hashlib.sha256(url.encode()).hexdigest()
    with sqlite3.connect(str(CACHE_DB)) as c:
        c.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)",
            (h, url, content, int(time.time())),
        )


async def crawl(
    url: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    cache_ttl: int = DEFAULT_CACHE_TTL,
) -> dict:
    """Hämta och extrahera text från en URL.

    Args:
        url: Full URL (https://...)
        max_chars: Max tecken att returnera (default 10k, 0 = obegränsat)
        cache_ttl: Cache-livslängd i sekunder (default 3600)

    Returns:
        Dict med url, content, summary, status
    """
    # Cache check
    cached = _cache_get(url, cache_ttl)
    if cached:
        return {"url": url, "content": cached, "status": "cached"}

    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            text = (result.markdown or result.text or "")[:max_chars] if max_chars else (result.markdown or result.text or "")
    except Exception as e:
        return {"url": url, "error": str(e)[:200], "status": "error"}

    if not text:
        return {"url": url, "error": "tom sida", "status": "error"}

    _cache_set(url, text)
    # ponytail: linjär summarization — kortaste 3 meningarna är en "summary"
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 20]
    summary = ". ".join(sentences[:3]) + "." if sentences else text[:200]

    return {
        "url": url,
        "content": text,
        "summary": summary,
        "chars": len(text),
        "status": "ok",
    }
