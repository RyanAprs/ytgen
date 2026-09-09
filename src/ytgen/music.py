"""Fetch royalty-free background music from the Jamendo API.

Jamendo has a real music API (unlike Pixabay Music, which has none). Tracks are
Creative Commons; many are CC-BY (attribution required) — we auto-write credits
to the video description. Instrumental-only by default so music sits under the
voiceover without competing lyrics.

Env: JAMENDO_CLIENT_ID  (free, from https://devportal.jamendo.com/)
Config: music.provider ("jamendo"|"local"), music.mood, music.volume
Cache: assets/music/jamendo_<trackid>.mp3 + cache/music.json (credit record)
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

import requests

API = "https://api.jamendo.com/v3.0"


def _client_id() -> str | None:
    return os.environ.get("JAMENDO_CLIENT_ID")


# map a topic to a musical mood/tag for the Jamendo `fuzzytags` search
_MOOD_TAGS = {
    "default": "ambient+cinematic",
}


def _pick_tags(cfg, topic: str) -> str:
    m = cfg.get("music.mood")
    if m:
        return m.replace(" ", "+")
    return _MOOD_TAGS["default"]


def fetch(cfg, cache_dir: Path, topic: str, min_duration: float = 0.0) -> dict | None:
    """Search Jamendo for an instrumental track, download it to assets/music/,
    and record credit. Returns {path, title, artist, url, license} or None."""
    cid = _client_id()
    if not cid:
        return None
    music_dir = Path(cfg.get("music.dir", "assets/music"))
    music_dir.mkdir(parents=True, exist_ok=True)

    tags = _pick_tags(cfg, topic)
    # fuzzytags with '+' is AND (all tags must be present) -> often 0 results.
    # Try the full mood, then progressively looser single-tag fallbacks.
    candidates = [tags]
    parts = tags.split("+")
    if len(parts) > 1:
        candidates += parts               # each tag alone
    for fallback in ("ambient", "instrumental", "relaxing"):
        if fallback not in candidates:
            candidates.append(fallback)

    dur_lo = int(min_duration) if min_duration else 60
    results = []
    used_tag = None
    for tag in candidates:
        params = {
            "client_id": cid,
            "format": "json",
            "limit": 20,
            "fuzzytags": tag,
            "vocalinstrumental": "instrumental",
            "audioformat": "mp32",
            "include": "musicinfo licenses",
            "order": "popularity_total",
            "durationbetween": f"{dur_lo}_600",
            # license safety: exclude NonCommercial and NoDerivatives so the track
            # is safe for a (possibly monetized) YouTube video AND for mixing with voice.
            "ccnc": "false",
            "ccnd": "false",
        }
        try:
            r = requests.get(f"{API}/tracks/", params=params, timeout=30)
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception as e:
            print(f"  jamendo fetch failed ({tag}): {e}")
            continue
        if results:
            used_tag = tag
            break
    if not results:
        return None
    print(f"  jamendo: matched tag '{used_tag}', {len(results)} tracks")

    # keep only tracks with an explicit CC license URL: some tracks pass the
    # ccnc/ccnd filter yet have an empty license_ccurl, so we can't write a
    # correct attribution line for them -> skip (attribution is legally required).
    results = [t for t in results if t.get("license_ccurl")]
    if not results:
        print("  jamendo: no track had an explicit license URL")
        return None

    # order candidates: long-enough tracks first (avoid loop seams), then the rest
    long_first = [t for t in results if float(t.get("duration", 0)) >= min_duration]
    rest = [t for t in results if t not in long_first]
    ordered = long_first + rest

    # try each track until one downloads (some audiodownload URLs return 500)
    for track in ordered:
        tid = track["id"]
        dest = music_dir / f"jamendo_{tid}.mp3"
        if not dest.exists():
            ok = False
            for url in (track.get("audio"), track.get("audiodownload")):
                if not url:
                    continue
                try:
                    with requests.get(url, stream=True, timeout=120) as resp:
                        resp.raise_for_status()
                        with open(dest, "wb") as f:
                            for chunk in resp.iter_content(65536):
                                f.write(chunk)
                    if dest.stat().st_size > 10000:
                        ok = True
                        break
                except Exception as e:
                    print(f"  download failed ({tid}): {e}")
                    dest.unlink(missing_ok=True)
            if not ok:
                continue

        lic_url = track.get("license_ccurl", "")
        info = {
            "path": str(dest),
            "track_id": tid,
            "title": track.get("name", ""),
            "artist": track.get("artist_name", ""),
            "url": track.get("shareurl", ""),
            "license_url": lic_url,
            "duration": float(track.get("duration", 0)),
        }
        (cache_dir / "music.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        return info

    print("  jamendo: no downloadable track among results")
    return None


def credit_line(info: dict) -> str:
    """Attribution line for the video description (CC-BY compliance)."""
    if not info:
        return ""
    lic = info.get("license_url", "")
    return (f"Music: \"{info['title']}\" by {info['artist']} "
            f"({info['url']}) — licensed via Jamendo. {lic}").strip()
