"""M3: Grounded script generation + scene segmentation.

Uses research.json facts to write an accurate narration script, then splits
it into scenes with visual keywords for the visuals stage.

Outputs:
  cache/script.json  -> {"topic","title","script","word_count"}
  cache/scenes.json  -> {"scenes":[{"index","text","visual_keywords","est_duration_sec"}]}
"""
from __future__ import annotations
import json
from pathlib import Path

from . import llm

SCRIPT_SYS = (
    "You are an expert faceless-YouTube scriptwriter. Write engaging, accurate, "
    "spoken-word narration. No stage directions, no 'welcome back', no headings — "
    "just clean narration sentences meant to be read aloud by a TTS voice. "
    "Ground every claim in the provided facts; do not invent statistics."
)


def _facts_block(research: dict, limit: int = 30) -> str:
    lines = []
    for f in research.get("facts", [])[:limit]:
        lines.append(f"- {f['claim']}  (source: {f['source_url']})")
    return "\n".join(lines) if lines else "(no research facts available)"


def generate_script(topic: str, research: dict, cfg, cache_dir: Path) -> dict:
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model", "llama-3.3-70b-versatile")
    duration = cfg.get("llm.target_duration_sec", 180)
    wpm = cfg.get("llm.wpm", 150)
    target_words = int(duration / 60 * wpm)

    facts = _facts_block(research)
    user = (
        f"Topic: {topic}\n\n"
        f"Research facts to ground the script:\n{facts}\n\n"
        f"Write a narration script of about {target_words} words "
        f"(~{duration} seconds at {wpm} wpm). Start with a strong hook. "
        f"End with a brief call-to-action to like and subscribe. "
        f"Output ONLY the narration text."
    )
    script = llm.chat(
        [{"role": "system", "content": SCRIPT_SYS}, {"role": "user", "content": user}],
        provider=provider, model=model, temperature=0.7,
    ).strip()

    # Title
    title = llm.chat(
        [{"role": "system", "content": "You write clickable but honest YouTube titles."},
         {"role": "user", "content": f"Topic: {topic}\nScript:\n{script[:800]}\n\n"
                                     f"Give ONE concise YouTube title (<70 chars). Output only the title."}],
        provider=provider, model=model, temperature=0.8,
    ).strip().strip('"')

    data = {
        "topic": topic,
        "title": title,
        "script": script,
        "word_count": len(script.split()),
    }
    (cache_dir / "script.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


SCENES_SYS = (
    "You split narration scripts into short visual scenes for a faceless video. "
    "Return strict JSON."
)


def _local_split(script: str, wpm: int) -> list[dict]:
    """Fallback: split by sentences into ~2-sentence scenes, keywords from nouns."""
    import re
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    out, buf = [], []
    for s in sents:
        buf.append(s)
        if len(buf) >= 2:
            text = " ".join(buf)
            words = [w.strip(".,!?;:\"'").lower() for w in text.split()]
            kw = [w for w in words if len(w) > 4][:3] or ["abstract", "background"]
            out.append({"text": text, "visual_keywords": kw})
            buf = []
    if buf:
        text = " ".join(buf)
        out.append({"text": text, "visual_keywords": ["abstract", "background"]})
    return out


def split_scenes(script: str, cfg, cache_dir: Path) -> dict:
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model", "openai/gpt-oss-20b")
    wpm = cfg.get("llm.wpm", 150)

    user = (
        "Split this narration into sequential scenes. Each scene = 1-2 sentences "
        "of the ORIGINAL text (do not rewrite), plus 2-4 concrete visual search "
        "keywords for stock footage.\n\n"
        "Return ONLY valid JSON, no prose:\n"
        "{\"scenes\":[{\"text\":\"...\",\"visual_keywords\":[\"...\"]}]}\n\n"
        f"Narration:\n{script}"
    )
    try:
        parsed = llm.chat_json(
            [{"role": "system", "content": SCENES_SYS}, {"role": "user", "content": user}],
            provider=provider, model=model, temperature=0.2,
        )
        scenes = parsed.get("scenes", [])
        if not scenes:
            raise ValueError("empty scenes")
    except Exception:
        scenes = _local_split(script, wpm)

    out = []
    for i, sc in enumerate(scenes):
        text = (sc.get("text") or "").strip()
        if not text:
            continue
        words = len(text.split())
        out.append({
            "index": i,
            "text": text,
            "visual_keywords": sc.get("visual_keywords", [])[:4],
            "est_duration_sec": round(words / wpm * 60, 1),
        })
    data = {"scenes": out}
    (cache_dir / "scenes.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
