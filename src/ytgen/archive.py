"""Archive used stock clips per-project so cache-clears don't waste them.

Copies each scene's sourced clip into output/<slug>/clips/ and writes a
manifest.json recording provider + query + original scene text. This is for
LOCAL keeping only. These clips are Pexels/Pixabay footage licensed for use in
videos, NOT for redistribution/resale (e.g. do not re-upload to stock sites).
"""
from __future__ import annotations
import json
import re
import shutil
from pathlib import Path


def _slug(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (topic or "project").lower()).strip("_")
    return s[:60] or "project"


def run(cfg, cache_dir: Path, output_dir: Path) -> dict:
    vp = cache_dir / "visuals.json"
    topic = ""
    sp = cache_dir / "script.json"
    if sp.exists():
        topic = json.loads(sp.read_text()).get("topic", "")
    if not topic and (cache_dir / ".topic").exists():
        topic = (cache_dir / ".topic").read_text().strip()

    dest = output_dir / _slug(topic) / "clips"
    dest.mkdir(parents=True, exist_ok=True)

    if not vp.exists():
        # fallback: no manifest — archive loose cache clips raw
        src_dir = cache_dir / "visuals"
        clips = sorted(src_dir.glob("*.mp4")) if src_dir.exists() else []
        n = 0
        for c in clips:
            out = dest / c.name
            if not out.exists():
                shutil.copy2(c, out)
            n += 1
        (dest.parent / "clips_manifest.json").write_text(json.dumps({
            "topic": topic, "count": n,
            "license_note": "Pexels/Pixabay footage — free to USE in videos; "
                            "NOT for redistribution or resale as stock.",
            "note": "raw archive (no scene manifest — source run incomplete)",
            "clips": [c.name for c in clips],
        }, indent=2, ensure_ascii=False))
        return {"archived": n, "dir": str(dest)}

    visuals = json.loads(vp.read_text())
    manifest = []
    n = 0
    for s in visuals.get("scenes", []):
        src = Path(s.get("video", ""))
        if not src.exists() or s.get("is_placeholder"):
            continue
        idx = s["index"]
        out = dest / f"clip_{idx:03d}{src.suffix or '.mp4'}"
        if not out.exists():
            shutil.copy2(src, out)
        n += 1
        manifest.append({
            "file": out.name,
            "scene_index": idx,
            "source": s.get("source"),
            "query": s.get("query"),
        })

    (dest.parent / "clips_manifest.json").write_text(
        json.dumps({
            "topic": topic,
            "count": n,
            "license_note": "Pexels/Pixabay footage — free to USE in videos; "
                            "NOT for redistribution or resale as stock.",
            "clips": manifest,
        }, indent=2, ensure_ascii=False)
    )
    return {"archived": n, "dir": str(dest)}


def project_dir(cfg, cache_dir: Path, output_dir: Path) -> Path:
    """Per-project output folder output/<slug> derived from the cached topic."""
    topic = ""
    sp = cache_dir / "script.json"
    if sp.exists():
        topic = json.loads(sp.read_text()).get("topic", "")
    if not topic and (cache_dir / ".topic").exists():
        topic = (cache_dir / ".topic").read_text().strip()
    return output_dir / _slug(topic)


def finalize(cfg, cache_dir: Path, output_dir: Path) -> dict:
    """Move the final deliverables (video/thumbnail/description/metadata) from the
    top-level output/ into output/<slug>/ so a new video never overwrites them."""
    dest = project_dir(cfg, cache_dir, output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in ("video.mp4", "thumbnail.png", "description.txt", "metadata.json",
                 "bilibili_zh.txt", "bilibili_zh.json"):
        src = output_dir / name
        if src.exists():
            out = dest / name
            shutil.move(str(src), str(out))
            moved.append(out.name)
    return {"moved": moved, "dir": str(dest)}
