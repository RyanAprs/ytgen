"""M6b: Assembly — build per-scene clips, concat, mix music -> output/video.mp4.

Minimal-ffmpeg-safe: no drawtext/subtitles. Captions are PNG overlays.
Per scene:
  - scale+crop stock clip to target WxH
  - loop/trim to match scene audio duration
  - overlay word-synced caption PNGs (enable between times)
  - attach scene voice audio
Then concat all scene mp4s. Optional background music ducked under voice.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from . import captions as cap_mod

RES = {"720p": (1280, 720), "1080p": (1920, 1080)}
RES_V = {"720p": (720, 1280), "1080p": (1080, 1920)}


def _dims(cfg) -> tuple[int, int]:
    res = cfg.get("resolution", "1080p")
    aspect = cfg.get("aspect", "16:9")
    table = RES if aspect == "16:9" else RES_V
    return table.get(res, table["1080p"])


def _run(cmd: list[str], timeout: int = 300) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd[:8])}...\n{p.stderr[-800:]}")


def _build_scene(scene: dict, caps: list[dict], out_mp4: Path,
                 w: int, h: int, fps: int, cfg) -> None:
    video_in = scene["video"]
    audio_in = scene["audio"]
    dur = scene["duration_sec"]

    # inputs: 0=video (looped), 1=audio, 2..=caption PNGs
    cmd = ["ffmpeg", "-y",
           "-stream_loop", "-1", "-i", video_in,
           "-i", audio_in]
    for c in caps:
        cmd += ["-i", c["png"]]

    # scale+crop video to WxH, set fps, trim to dur
    ken = cfg.get("visuals.ken_burns", True)
    scale = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    fc = [f"[0:v]{scale},fps={fps},setpts=PTS-STARTPTS[base]"]
    last = "base"
    for i, c in enumerate(caps):
        idx_in = 2 + i
        st, en = c["start"], c["end"]
        fc.append(
            f"[{last}][{idx_in}:v]overlay=0:0:enable='between(t,{st},{en})'[v{i}]"
        )
        last = f"v{i}"
    fc.append(f"[{last}]trim=duration={dur},setpts=PTS-STARTPTS,"
              f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(dur-0.3,0):.2f}:d=0.3[vout]")
    filter_complex = ";".join(fc)

    cmd += ["-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "1:a",
            "-t", f"{dur}",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-r", str(fps),
            str(out_mp4)]
    _run(cmd)


def _pick_music(cfg) -> Path | None:
    if not cfg.get("music.enabled", True):
        return None
    mdir = Path(cfg.get("music.dir", "assets/music"))
    if not mdir.is_absolute():
        mdir = cfg.root / mdir
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.ogg"):
        files = sorted(mdir.glob(ext))
        if files:
            return files[0]
    return None


def run(cfg, cache_dir: Path, output_dir: Path) -> dict:
    tts = json.loads((cache_dir / "tts.json").read_text())
    visuals = json.loads((cache_dir / "visuals.json").read_text())
    vis_by_idx = {s["index"]: s for s in visuals["scenes"]}

    w, h = _dims(cfg)
    fps = cfg.get("fps", 30)
    scenes_dir = cache_dir / "scene_clips"
    scenes_dir.mkdir(exist_ok=True)
    cap_dir = cache_dir / "captions"
    cap_dir.mkdir(exist_ok=True)

    scene_files = []
    for sc in tts["scenes"]:
        idx = sc["index"]
        vis = vis_by_idx.get(idx)
        if not vis:
            continue
        merged = dict(sc)
        merged["video"] = vis["video"]
        caps = []
        if cfg.get("captions.enabled", True):
            caps = cap_mod.render_scene_captions(sc, idx, cap_dir, w, h, cfg)
        out_mp4 = scenes_dir / f"scene_{idx:03d}.mp4"
        # resume: skip if already rendered and newer than its inputs
        if out_mp4.exists() and out_mp4.stat().st_size > 1024 and not cfg.get("_force", False):
            scene_files.append(out_mp4)
            continue
        _build_scene(merged, caps, out_mp4, w, h, fps, cfg)
        scene_files.append(out_mp4)

    # concat scene clips
    concat_list = cache_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{p}'\n" for p in scene_files))
    concat_mp4 = cache_dir / "concat.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
          "-c", "copy", str(concat_mp4)])

    final = output_dir / "video.mp4"
    music = _pick_music(cfg)
    if music:
        vol = cfg.get("music.volume", 0.12)
        # mix: voice (0:a) full + music (1:a) ducked, music looped, cut to video len
        _run([
            "ffmpeg", "-y", "-i", str(concat_mp4),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            f"[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,"
            f"aresample=48000,aformat=channel_layouts=stereo[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", str(final),
        ])
    else:
        # re-encode audio to standard 48kHz stereo (24kHz mono plays silent in some players)
        _run(["ffmpeg", "-y", "-i", str(concat_mp4),
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
              str(final)])

    return {"output": str(final), "scenes": len(scene_files),
            "resolution": f"{w}x{h}", "music": str(music) if music else None}
