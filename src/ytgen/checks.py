"""Environment / dependency checks (M1)."""
from __future__ import annotations
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def check_ffmpeg() -> Check:
    exe = shutil.which("ffmpeg")
    if not exe:
        return Check("ffmpeg", False, "not found on PATH — install: brew install ffmpeg")
    try:
        out = subprocess.run(
            [exe, "-version"], capture_output=True, text=True, timeout=10
        ).stdout.splitlines()[0]
    except Exception as e:  # pragma: no cover
        return Check("ffmpeg", False, f"error running ffmpeg: {e}")
    return Check("ffmpeg", True, out)


def check_ffprobe() -> Check:
    exe = shutil.which("ffprobe")
    if not exe:
        return Check("ffprobe", False, "not found — usually ships with ffmpeg")
    return Check("ffprobe", True, exe)


def check_keys(cfg) -> list[Check]:
    checks = []
    for src in cfg.get("visuals.sources", []):
        key = f"{src.upper()}_API_KEY"
        val = cfg.env(key)
        checks.append(Check(key, bool(val), "set" if val else f"missing (free signup) — needed for {src}"))
    return checks


def run_all(cfg) -> list[Check]:
    checks = [check_ffmpeg(), check_ffprobe()]
    checks += check_keys(cfg)
    return checks
