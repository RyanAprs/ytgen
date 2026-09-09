"""M7: Output metadata + thumbnail.

Generates YouTube title (from script.json), description, tags via LLM, appends
cited sources from research.json, and renders a thumbnail PNG via Pillow.

Outputs:
  output/metadata.json  -> {"title","description","tags"}
  output/description.txt -> ready-to-paste description (with sources)
  output/thumbnail.png
"""
from __future__ import annotations
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import llm

FONT_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size: int):
    for p in FONT_BOLD:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _gen_desc_tags(topic: str, title: str, script: str, cfg) -> tuple[str, list[str]]:
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model", "openai/gpt-oss-20b")
    try:
        data = llm.chat_json(
            [{"role": "system", "content": "You write YouTube metadata. Return strict JSON."},
             {"role": "user", "content":
                 f"Topic: {topic}\nTitle: {title}\nScript excerpt:\n{script[:1200]}\n\n"
                 'Return JSON: {"description":"2-3 sentence engaging description",'
                 '"tags":["8-12 lowercase search tags"]}'}],
            provider=provider, model=model, temperature=0.6,
        )
        desc = (data.get("description") or "").strip()
        tags = [str(t).strip().lower() for t in data.get("tags", []) if str(t).strip()][:12]
        if desc:
            return desc, tags
    except Exception:
        pass
    # fallback
    return f"An exploration of {topic}.", [topic.lower()]


def _thumb_text(title: str, topic: str) -> str:
    """Short punchy headline for thumbnail (full title overflows)."""
    # take part before colon/dash if present, else first ~5 words
    for sep in (":", " - ", " – "):
        if sep in title:
            head = title.split(sep)[0].strip()
            if len(head) >= 8:
                return head
    words = title.split()
    return " ".join(words[:5]) if len(words) > 5 else title


def _thumbnail(title: str, out: Path, w: int, h: int, bg_clip: str | None,
              topic: str = "") -> None:
    text = _thumb_text(title, topic)
    # base: blurred first frame of a stock clip, or gradient
    base = Image.new("RGB", (w, h), (20, 20, 46))
    if bg_clip:
        try:
            import subprocess, io
            png = subprocess.run(
                ["ffmpeg", "-y", "-ss", "1", "-i", bg_clip, "-frames:v", "1",
                 "-f", "image2pipe", "-vcodec", "png", "-"],
                capture_output=True, timeout=30).stdout
            if png:
                frame = Image.open(io.BytesIO(png)).convert("RGB")
                frame = frame.resize((w, h))
                from PIL import ImageFilter, ImageEnhance
                frame = frame.filter(ImageFilter.GaussianBlur(6))
                frame = ImageEnhance.Brightness(frame).enhance(0.55)
                base = frame
        except Exception:
            pass

    draw = ImageDraw.Draw(base)
    font = _font(int(h * 0.13))
    lines = textwrap.wrap(text, width=14)[:3]
    line_h = int(h * 0.15)
    total = line_h * len(lines)
    y = (h - total) // 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (w - tw) // 2
        for dx in (-4, 4):
            for dy in (-4, 4):
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 220, 60))
        y += line_h
    base.save(out)


def _gen_bilibili_zh(topic: str, title: str, script: str, cfg,
                     music_credit: str, sources: list[str]) -> dict:
    """Generate Chinese (Simplified) Bilibili metadata: title, description, tags.

    Translates/adapts the English script into a 简介 (intro), a punchy 标题, and
    Chinese search 标签. Falls back gracefully if the LLM refuses or errors.
    """
    provider = cfg.get("llm.provider", "groq")
    model = cfg.get("llm.model", "openai/gpt-oss-20b")
    zh = {"title": title, "description": "", "tags": []}
    try:
        data = llm.chat_json(
            [{"role": "system", "content":
                "You are a bilingual (English↔Simplified Chinese) editor for a Bilibili "
                "history channel. Return strict JSON with Simplified Chinese values."},
             {"role": "user", "content":
                f"English topic: {topic}\nEnglish title: {title}\n"
                f"English script excerpt:\n{script[:1600]}\n\n"
                "Produce Bilibili metadata in SIMPLIFIED CHINESE. Return JSON: "
                '{"title":"<catchy Chinese title, <=40 chars>",'
                '"description":"<3-5 sentence Chinese 简介 summarizing the video>",'
                '"tags":["<6-10 Chinese search tags, no # symbol>"]}'}],
            provider=provider, model=model, temperature=0.6,
        )
        t = (data.get("title") or "").strip()
        d = (data.get("description") or "").strip()
        tg = [str(x).strip().lstrip("#") for x in data.get("tags", []) if str(x).strip()][:10]
        if t:
            zh["title"] = t
        if d:
            zh["description"] = d
        if tg:
            zh["tags"] = tg
    except Exception:
        pass
    if not zh["description"]:
        zh["description"] = f"本视频讲述：{topic}。"  # minimal fallback
    if not zh["tags"]:
        zh["tags"] = ["历史", "历史科普"]

    # build ready-to-paste 简介 with attribution (license compliance carries over)
    body = zh["description"].rstrip() + "\n\n"
    if music_credit:
        body += music_credit + "\n"
    body += "素材 Footage: Pexels & Pixabay (free license).\n"
    if sources:
        body += "史料 Sources: " + "、".join(sources) + "\n"
    body += "原声为英文旁白 / Original narration in English.\n"
    zh["desc_full"] = body
    zh["tid"] = cfg.get("bilibili.tid", 228)
    zh["copyright"] = cfg.get("bilibili.copyright", 2)
    zh["source_url"] = sources[0] if sources else ""
    return zh


def run(cfg, cache_dir: Path, output_dir: Path) -> dict:
    script_data = json.loads((cache_dir / "script.json").read_text())
    topic = script_data.get("topic", "")
    title = script_data.get("title") or topic
    script = script_data.get("script", "")

    desc, tags = _gen_desc_tags(topic, title, script, cfg)

    # append sources
    sources = []
    rp = cache_dir / "research.json"
    if rp.exists():
        research = json.loads(rp.read_text())
        seen = set()
        for s in research.get("sources", []):
            u = s.get("url") if isinstance(s, dict) else s
            if u and u not in seen:
                seen.add(u)
                sources.append(u)

    desc_full = desc + "\n\n"
    # music attribution (Jamendo CC-BY compliance)
    music_credit = ""
    mp = cache_dir / "music.json"
    if mp.exists():
        try:
            from . import music as music_mod
            line = music_mod.credit_line(json.loads(mp.read_text()))
            if line:
                music_credit = line
                desc_full += line + "\n\n"
        except Exception:
            pass
    if sources:
        desc_full += "Sources:\n" + "\n".join(f"- {u}" for u in sources) + "\n\n"
    desc_full += "#" + " #".join(t.replace(" ", "") for t in tags[:5])

    meta = {"title": title, "description": desc, "tags": tags, "sources": sources}
    (output_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (output_dir / "description.txt").write_text(desc_full)

    # ---- Bilibili Chinese metadata (cross-post) ----
    if cfg.get("bilibili.enabled", False):
        try:
            zh = _gen_bilibili_zh(topic, title, script, cfg, music_credit, sources)
            (output_dir / "bilibili_zh.json").write_text(
                json.dumps(zh, indent=2, ensure_ascii=False))
            txt = (
                f"【标题 Title】\n{zh['title']}\n\n"
                f"【分区 Partition】tid={zh['tid']} (知识→人文历史)\n"
                f"【类型 Copyright】{zh['copyright']} "
                f"({'自制/original' if zh['copyright'] == 1 else '转载/reprint'})\n"
                f"【转载来源 Source】{zh.get('source_url','')}\n\n"
                f"【标签 Tags】\n{' '.join(zh['tags'])}\n\n"
                f"【简介 Description】\n{zh['desc_full']}"
            )
            (output_dir / "bilibili_zh.txt").write_text(txt)
        except Exception:
            pass

    # thumbnail — use first non-placeholder clip as bg
    aspect = cfg.get("aspect", "16:9")
    tw, th = (1280, 720) if aspect == "16:9" else (720, 1280)
    bg = None
    vp = cache_dir / "visuals.json"
    if vp.exists():
        for s in json.loads(vp.read_text()).get("scenes", []):
            if not s.get("is_placeholder") and s.get("video"):
                bg = s["video"]
                break
    thumb = output_dir / "thumbnail.png"
    _thumbnail(title, thumb, tw, th, bg, topic)

    return {"title": title, "tags": len(tags), "sources": len(sources),
            "thumbnail": str(thumb), "description": str(output_dir / "description.txt")}
