# PRD — Faceless YouTube Video Generator

**Owner:** rr
**Status:** Draft v1
**Last updated:** 2026-09-09

---

## 1. Summary

CLI tool. Input a topic (or script). Output a finished, upload-ready `.mp4`
faceless YouTube video — AI script → AI voiceover → matched visuals → captions →
music → rendered video. Fully automatic: `topic in → mp4 out`.

## 2. Goals

- One command produces a complete video with zero manual editing.
- Use **free** tools only, high output quality.
- Reproducible: same topic + seed → deterministic-ish build.
- Modular: any stage (script/voice/visuals) swappable.

## 3. Non-Goals (v1)

- Talking-head / real-camera footage editing.
- Auto-upload to YouTube (later phase).
- Web UI (CLI first).
- Multi-language dubbing (English first).

## 4. Users & Use Case

Solo creator wants to mass-produce faceless narration videos (explainers,
listicles, top-10, facts) without editing skill or paid subscriptions.

## 5. Pipeline (fully auto)

```
topic
  → 1. Research               (web search + extract → cited facts/sources)
  → 2. Script generation      (LLM, grounded on research)
  → 3. Scene segmentation      (split script into ~5-15s beats + visual keywords)
  → 4. Voiceover (TTS)         (per-scene audio + word timestamps)
  → 5. Visual sourcing         (stock clip/image per scene by keyword)
  → 6. Captions                (word-synced subtitles burned in)
  → 7. Assembly                (ffmpeg: visuals + Ken Burns + voice + music)
  → 8. Output                  (1080p mp4 + thumbnail + title/description)
```

**Stage 1 Research (new):** before writing, tool searches the web, extracts
top sources, dedupes facts, and produces a `research.json` (claims + source URLs).
Script gen is grounded on this — reduces hallucination, adds credibility. Sources
saved for description/citations. Skippable via `--no-research` (or `--script` input).

## 6. Recommended Free Stack

| Stage | Tool | Why free / quality |
|---|---|---|
| Language/tech | **Python 3.11 + ffmpeg** | Best media ecosystem |
| Research | **web search + scrape** (DuckDuckGo/free) | Grounds script in real facts |
| Script LLM | Local **Ollama** (llama3.1/qwen2.5) or free API tier | No cost, offline capable |
| TTS voice | **Edge-TTS** (Microsoft neural voices) | Free, very natural. Fallback: Piper / Coqui |
| Word timestamps | **faster-whisper** (align voice→captions) | Free, local |
| Stock visuals | **Pexels API** + **Pixabay API** (free keys) | Free HD clips/photos, commercial-ok |
| AI images (optional) | **Pollinations** / local SDXL | Free generative b-roll |
| Music | **YouTube Audio Library** / **Pixabay Music** (local pack) | Royalty-free |
| Captions render | ffmpeg `subtitles`/ASS | Free, styled |
| Video assembly | **ffmpeg** (+ moviepy optional) | Free |

> Note: Edge-TTS = free & near-commercial quality. Runway/Pika/Kling are paid —
> excluded from v1. AI b-roll optional via free Pollinations.

## 7. Functional Requirements

- **FR1** Accept `--topic "..."` or `--script file.txt`.
- **FR1b** Research stage: web search + extract top sources → `research.json` (facts + URLs); `--no-research` to skip. Sources auto-added to description.
- **FR2** Generate script with configurable length (target duration, e.g. 60s / 3min / 8min), grounded on research.
- **FR3** Segment script into scenes each with: text, duration, visual keyword(s).
- **FR4** Synthesize voiceover per scene; select voice/rate/pitch via config.
- **FR5** Fetch ≥1 relevant clip/image per scene; cache to avoid re-download.
- **FR6** Generate word-synced captions (styled, positioned, safe-area).
- **FR7** Assemble: fit visuals to voice length, Ken Burns on stills, crossfades,
  background music ducked under voice.
- **FR8** Export 1080p (config 720/1080/vertical 9:16 for Shorts) H.264 mp4.
- **FR9** Also output: title, description, tags, thumbnail image.
- **FR10** Resumable: cache each stage; re-run skips completed steps.

## 8. Non-Functional

- Runs on macOS (user's machine), CPU-only acceptable.
- One video (3 min) end-to-end < ~5 min on laptop.
- Config via `config.yaml` + `.env` for API keys.
- Clear logs per stage; fail loud with actionable errors.

## 9. Config & Keys

- `.env`: `PEXELS_API_KEY`, `PIXABAY_API_KEY` (both free signup).
- `config.yaml`: voice, resolution, aspect, music volume, LLM model, duration.

## 10. Project Structure (proposed)

```
yt-video-generator/
  main.py                 # CLI entry
  config.yaml
  .env.example
  pipeline/
    script_gen.py
    scene_split.py
    tts.py
    visuals.py
    captions.py
    assemble.py
    metadata.py           # title/desc/tags/thumbnail
  cache/                  # per-project intermediate files
  output/                 # final mp4 + assets
  assets/music/           # royalty-free tracks
```

## 11. Milestones

- **M1** Skeleton CLI + config + ffmpeg check.
- **M2** Research stage (web search/extract → research.json).
- **M3** Script gen (grounded) + scene split (text only).
- **M4** TTS voiceover + whisper alignment.
- **M5** Visual sourcing (Pexels/Pixabay).
- **M6** Assembly + captions + music → first full mp4.
- **M7** Metadata + thumbnail + vertical/Shorts mode.
- **M8** Polish: transitions, caching/resume, presets.

## 12. Risks

- Stock footage relevance for niche topics → fallback to AI images / keyword broadening.
- TTS robotic on long text → chunk per sentence, add pauses.
- Copyright: only royalty-free/CC sources; log source per asset.
- Whisper alignment drift → sentence-level fallback timing.

## 13. Open Questions

- Target niche/topics? (affects visual style + music mood)
- **Resolved:** Aspect → **16:9 horizontal primary** (long-form). 9:16 Shorts = later toggle (M6).
- **Resolved:** Auto-upload → **No.** Manual review/publish. Revisit later.
