# yt-video-generator (ytgen)

Faceless YouTube video generator. **Topic in → finished `.mp4` out.** Fully automatic, free tools only.

## Pipeline

`research → script → scenes → tts → visuals → captions → assemble → output`

Grounds script on real web research, AI voiceover (Edge-TTS), stock visuals
(Pexels/Pixabay), word-synced captions, ffmpeg render. See [PRD.md](PRD.md).

## Setup

```bash
uv venv --python 3.11
uv pip install -e .
cp .env.example .env   # add free Pexels/Pixabay keys
```

## Usage

```bash
ytgen doctor                          # check environment
ytgen generate --topic "black holes"  # generate a video
ytgen generate --script my.txt        # use existing script
```

## Config

- `config.yaml` — video/voice/caption/music settings.
- `.env` — API keys (`PEXELS_API_KEY`, `PIXABAY_API_KEY`).

## Status

M1 done (CLI skeleton + config + env checks). Stages implemented incrementally.
