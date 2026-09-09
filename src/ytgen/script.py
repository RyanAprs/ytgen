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
    "You are an expert faceless-YouTube scriptwriter for an educational HISTORY "
    "channel. Write engaging, accurate, spoken-word narration about documented "
    "historical events. Historical facts may include battles, assassinations, and "
    "the deaths of ancient figures — report them factually and soberly as any history "
    "documentary would; this is educational content about events ~1600 years ago. "
    "No stage directions, no 'welcome back', no headings — just clean narration "
    "sentences meant to be read aloud by a TTS voice. "
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

# generic literal terms that pull wrong/ambiguous stock footage
_BAD_KW = {"star death", "point of no return", "mystery", "idea", "history",
           "science", "concept", "theory", "process", "nature",
           # modern-military terms that pull tanks/soldiers/rockets instead of antiquity
           "army", "military", "soldier", "soldiers", "war", "battle", "crisis",
           "weapon", "weapons", "attack", "invasion", "troops", "fighter"}

# words that, if present, mean the scene is about ancient Rome -> force an antiquity anchor
_ROME_ANCHOR = "ancient roman"


def _clean_keywords(kws: list[str], topic: str) -> list[str]:
    """Drop ambiguous terms, keep concrete visual nouns, ensure ancient-Rome context."""
    out = []
    for k in kws:
        k = (k or "").strip().lower()
        if not k or k in _BAD_KW or len(k) < 3:
            continue
        # anchor generic terms to antiquity so stock search returns Roman ruins/reenactment,
        # not modern soldiers/tanks (hard-won: 'army'/'crisis' pulled Bundeswehr footage)
        if not any(w in k for w in ("roman", "rome", "ancient", "colosseum", "ruin",
                                    "empire", "legion", "gladiator", "marble", "statue")):
            k = f"{_ROME_ANCHOR} {k}"
        out.append(k)
    if not out:
        out = ["ancient roman ruins"]
    return out[:4]


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


def split_scenes(script: str, cfg, cache_dir: Path, topic: str = "") -> dict:
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model", "openai/gpt-oss-20b")
    wpm = cfg.get("llm.wpm", 150)

    user = (
        f"Topic of the video: {topic}\n\n"
        "Split this narration into sequential scenes. Each scene = 1-2 sentences "
        "of the ORIGINAL text (do not rewrite), plus 2-4 CONCRETE, UNAMBIGUOUS "
        "visual search keywords for stock footage. Rules for keywords:\n"
        "- Use literal filmable objects/scenes (e.g. 'collapsing star', 'galaxy', "
        "'telescope observatory'), NOT abstract nouns ('mystery','idea','history').\n"
        "- Avoid phrases that are famous movie/brand terms (e.g. 'star death' pulls "
        "Star Wars). Prefer scientific/physical descriptors.\n"
        "- When ambiguous, add topic context (e.g. 'black hole simulation').\n\n"
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
            "visual_keywords": _clean_keywords(sc.get("visual_keywords", []), topic),
            "est_duration_sec": round(words / wpm * 60, 1),
        })
    data = {"scenes": out}
    (cache_dir / "scenes.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
