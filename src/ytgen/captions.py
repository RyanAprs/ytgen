"""M6a: Caption rendering via Pillow (minimal-ffmpeg-safe).

This ffmpeg build lacks drawtext/subtitles/libass, so we render caption text to
transparent PNGs and overlay them with ffmpeg's `overlay` filter (always present).

Word timings (from tts.json) are grouped into short phrase chunks (~3-5 words).
Each chunk -> one PNG + (start, end) time relative to its scene.

render_scene_captions() returns a list of:
  {"png": path, "start": sec, "end": sec}  (times relative to scene audio start)
"""
from __future__ import annotations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _chunk_words(words: list[dict], max_words: int = 4) -> list[dict]:
    """Group word timings into caption phrases. Returns [{text,start,end}]."""
    chunks = []
    i = 0
    while i < len(words):
        group = words[i:i + max_words]
        text = " ".join(w["word"] for w in group).strip()
        start = group[0]["offset_sec"]
        last = group[-1]
        end = last["offset_sec"] + last["duration_sec"]
        chunks.append({"text": text, "start": round(start, 3), "end": round(end, 3)})
        i += max_words
    return chunks


def _render_png(text: str, out: Path, video_w: int, video_h: int, cfg) -> None:
    font_size = cfg.get("captions.font_size", 42)
    outline = cfg.get("captions.outline", 3)
    font = _load_font(font_size)

    img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # wrap text to ~85% width
    max_w = int(video_w * 0.85)
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    line_h = font_size + 12
    total_h = line_h * len(lines)
    # position: lower third, safe area
    y = int(video_h * 0.80) - total_h // 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (video_w - tw) // 2
        # outline
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 230))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    img.save(out)


def render_scene_captions(scene: dict, scene_idx: int, cap_dir: Path,
                          video_w: int, video_h: int, cfg) -> list[dict]:
    words = scene.get("words", [])
    if not words:
        return []
    chunks = _chunk_words(words, cfg.get("captions.max_words", 4))
    out = []
    for j, ch in enumerate(chunks):
        png = cap_dir / f"cap_{scene_idx:03d}_{j:03d}.png"
        _render_png(ch["text"], png, video_w, video_h, cfg)
        out.append({"png": str(png), "start": ch["start"], "end": ch["end"]})
    return out
