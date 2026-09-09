"""M2: Research stage — web search + extract → cited facts.

Produces cache/research.json:
  {
    "topic": str,
    "sources": [{"title","url","text_excerpt"}],
    "facts": [{"claim","source_url"}],
  }
Grounds later script generation. Network via requests (urllib stalls on IPv6).
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
import trafilatura
from ddgs import DDGS

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ytgen/0.1"


@dataclass
class Source:
    title: str
    url: str
    text_excerpt: str


@dataclass
class Fact:
    claim: str
    source_url: str


def search(topic: str, max_results: int) -> list[dict]:
    """DuckDuckGo text search. Returns list of {title,href,body}."""
    with DDGS() as ddg:
        return list(ddg.text(topic, max_results=max_results))


def fetch_text(url: str, timeout: int = 20) -> str:
    """Download + extract main article text. Empty string on failure."""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return ""
    extracted = trafilatura.extract(
        resp.text, include_comments=False, include_tables=False, favor_precision=True
    )
    return extracted or ""


_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def extract_facts(text: str, url: str, max_facts: int = 5) -> list[Fact]:
    """Naive fact extraction: informative sentences (has a digit or is declarative).

    Placeholder heuristic for M2; LLM refinement happens in M3 script grounding.
    """
    facts: list[Fact] = []
    for sent in _SENT_RE.split(text):
        s = sent.strip()
        if not (40 <= len(s) <= 300):
            continue
        informative = bool(re.search(r"\d", s)) or bool(
            re.search(r"\b(is|are|was|were|has|have|can|will|contains|consists|measures)\b", s)
        )
        if informative:
            facts.append(Fact(claim=s, source_url=url))
        if len(facts) >= max_facts:
            break
    return facts


def run(topic: str, cache_dir: Path, max_sources: int = 6) -> dict:
    """Execute research stage. Writes and returns research.json dict."""
    results = search(topic, max_sources)
    sources: list[Source] = []
    facts: list[Fact] = []
    for r in results:
        url = r.get("href") or r.get("url") or ""
        title = r.get("title", "")
        if not url:
            continue
        text = fetch_text(url)
        if not text:
            # keep search snippet as fallback source
            body = r.get("body", "")
            if body:
                sources.append(Source(title=title, url=url, text_excerpt=body[:500]))
            continue
        sources.append(Source(title=title, url=url, text_excerpt=text[:500]))
        facts.extend(extract_facts(text, url))

    data = {
        "topic": topic,
        "sources": [asdict(s) for s in sources],
        "facts": [asdict(f) for f in facts],
    }
    out = cache_dir / "research.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
