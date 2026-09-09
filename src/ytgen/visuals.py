"""M5: Visual sourcing — stock video per scene via Pexels + Pixabay.

For each scene: query providers by visual_keywords, download best matching
HD clip (prefer landscape, duration >= scene voice length), cache by URL hash.
Falls back across keywords and providers; last resort = solid-color placeholder.

Outputs:
  cache/visuals/<hash>.mp4 ...
  cache/visuals.json -> {"scenes":[{"index","video","source","query","is_placeholder"}]}
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
from pathlib import Path

import requests

UA = "ytgen/0.1"
PEXELS_URL = "https://api.pexels.com/videos/search"
PIXABAY_URL = "https://pixabay.com/api/videos/"


def _cache_name(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16] + ".mp4"


def _download(url: str, dest: Path, timeout: int = 60) -> bool:
    try:
        with requests.get(url, stream=True, headers={"User-Agent": UA}, timeout=timeout) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        return dest.stat().st_size > 1024
    except Exception:
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def _pexels_search(query: str, min_dur: float, want_landscape: bool) -> str | None:
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get(
            PEXELS_URL,
            headers={"Authorization": key},
            params={"query": query, "per_page": 8,
                    "orientation": "landscape" if want_landscape else "portrait"},
            timeout=25,
        )
        r.raise_for_status()
        vids = r.json().get("videos", [])
    except Exception:
        return None
    best = None
    for v in vids:
        files = sorted(
            [f for f in v.get("video_files", []) if f.get("width")],
            key=lambda f: f.get("width", 0), reverse=True,
        )
        # prefer ~720p-1080p mp4 (smaller = faster, still sharp)
        for f in files:
            if f.get("file_type") == "video/mp4" and 1200 <= f.get("width", 0) <= 1300:
                best = f["link"]
                break
        if not best:
            for f in files:
                if f.get("file_type") == "video/mp4" and 1000 <= f.get("width", 0) <= 1920:
                    best = f["link"]
                    break
        if best:
            break
    return best


def _pixabay_search(query: str, want_landscape: bool) -> str | None:
    key = os.getenv("PIXABAY_API_KEY")
    if not key:
        return None
    try:
        r = requests.get(
            PIXABAY_URL,
            params={"key": key, "q": query, "per_page": 8, "video_type": "film"},
            timeout=25,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception:
        return None
    for h in hits:
        vids = h.get("videos", {})
        for size in ("large", "medium", "small"):
            v = vids.get(size, {})
            if v.get("url"):
                return v["url"]
    return None


def _placeholder(dest: Path, aspect: str, seconds: float = 6.0) -> bool:
    w, h = (1920, 1080) if aspect == "16:9" else (1080, 1920)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", f"color=c=0x1a1a2e:s={w}x{h}:d={max(seconds,3):.1f}",
             "-c:v", "libx264", "-t", f"{max(seconds,3):.1f}",
             "-pix_fmt", "yuv420p", str(dest)],
            capture_output=True, timeout=60,
        )
        return dest.exists()
    except Exception:
        return False


def _source_one(keywords: list[str], min_dur: float, vis_dir: Path,
                sources: list[str], want_landscape: bool) -> tuple[str, str, str, bool]:
    """Return (path, source, query, is_placeholder)."""
    queries = keywords or ["abstract background"]
    for q in queries:
        for src in sources:
            link = None
            if src == "pexels":
                link = _pexels_search(q, min_dur, want_landscape)
            elif src == "pixabay":
                link = _pixabay_search(q, want_landscape)
            if not link:
                continue
            dest = vis_dir / _cache_name(link)
            if dest.exists() and dest.stat().st_size > 1024:
                return str(dest), src, q, False
            if _download(link, dest):
                return str(dest), src, q, False
    return "", "", queries[0], True


def run(scenes: list[dict], cfg, cache_dir: Path) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    vis_dir = cache_dir / "visuals"
    vis_dir.mkdir(exist_ok=True)
    sources = cfg.get("visuals.sources", ["pexels", "pixabay"])
    aspect = cfg.get("aspect", "16:9")
    want_landscape = aspect == "16:9"

    def work(sc):
        idx = sc["index"]
        dur = sc.get("duration_sec", 6.0)
        path, source, query, placeholder = _source_one(
            sc.get("visual_keywords", []), dur, vis_dir, sources, want_landscape)
        if placeholder:
            path = str(vis_dir / f"placeholder_{idx:03d}.mp4")
            _placeholder(Path(path), aspect, dur)
            source = "placeholder"
        return {"index": idx, "video": path, "source": source,
                "query": query, "is_placeholder": placeholder}

    with ThreadPoolExecutor(max_workers=5) as ex:
        out = list(ex.map(work, scenes))
    out.sort(key=lambda s: s["index"])

    data = {"scenes": out}
    (cache_dir / "visuals.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
