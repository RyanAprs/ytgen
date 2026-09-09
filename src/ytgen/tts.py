"""M4: Text-to-speech voiceover via Edge-TTS.

Per scene: synthesize mp3 + collect word-level timestamps (Edge-TTS emits
WordBoundary events natively — exact, no whisper alignment needed).

Outputs:
  cache/audio/scene_000.mp3 ...
  cache/audio/tts.json -> {"scenes":[{"index","audio","duration_sec","words":[
                            {"word","offset_sec","duration_sec"}]}], "total_sec"}
"""
from __future__ import annotations
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts


def _probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        return round(float(out), 3)
    except Exception:
        return 0.0


async def _synth_scene(text: str, out_mp3: Path, voice: str, rate: str, pitch: str) -> list[dict]:
    """Synthesize one scene; return word timestamps (seconds)."""
    comm = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch,
                                boundary="WordBoundary")
    words: list[dict] = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "word": chunk["text"],
                    # edge-tts offsets are in 100-ns ticks
                    "offset_sec": round(chunk["offset"] / 1e7, 3),
                    "duration_sec": round(chunk["duration"] / 1e7, 3),
                })
    return words


def run(scenes: list[dict], cfg, cache_dir: Path) -> dict:
    voice = cfg.get("tts.voice", "en-US-AriaNeural")
    rate = cfg.get("tts.rate", "+0%")
    pitch = cfg.get("tts.pitch", "+0Hz")
    audio_dir = cache_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    out_scenes = []
    total = 0.0
    for sc in scenes:
        idx = sc["index"]
        mp3 = audio_dir / f"scene_{idx:03d}.mp3"
        words = asyncio.run(_synth_scene(sc["text"], mp3, voice, rate, pitch))
        dur = _probe_duration(mp3)
        total += dur
        out_scenes.append({
            "index": idx,
            "text": sc["text"],
            "audio": str(mp3),
            "duration_sec": dur,
            "visual_keywords": sc.get("visual_keywords", []),
            "words": words,
        })

    data = {"scenes": out_scenes, "total_sec": round(total, 2)}
    (cache_dir / "tts.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def list_voices_sync(filter_lang: str = "en") -> list[str]:
    """Convenience: list available Edge-TTS voices for a language prefix."""
    async def _go():
        vs = await edge_tts.list_voices()
        return [v["ShortName"] for v in vs if v["ShortName"].startswith(filter_lang)]
    return asyncio.run(_go())
