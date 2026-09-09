#!/usr/bin/env bash
# Generate a copyright-free ambient space drone (fully synthesized, no samples).
# Layered low sine drones + slow tremolo + long echo for a cinematic pad.
set -e
OUT="$1"; DUR="${2:-190}"
ffmpeg -y \
  -f lavfi -i "sine=frequency=55:sample_rate=48000:duration=$DUR" \
  -f lavfi -i "sine=frequency=82.5:sample_rate=48000:duration=$DUR" \
  -f lavfi -i "sine=frequency=110:sample_rate=48000:duration=$DUR" \
  -f lavfi -i "sine=frequency=164.8:sample_rate=48000:duration=$DUR" \
  -filter_complex "\
    [0:a]volume=0.9[a0];\
    [1:a]volume=0.5[a1];\
    [2:a]volume=0.35[a2];\
    [3:a]volume=0.18[a3];\
    [a0][a1][a2][a3]amix=inputs=4:normalize=0[mix];\
    [mix]tremolo=f=0.12:d=0.4,\
         aecho=0.8:0.7:600|1100:0.4|0.25,\
         highpass=f=40,lowpass=f=1200,\
         afade=t=in:st=0:d=4,afade=t=out:st=$((DUR-5)):d=5,\
         aformat=channel_layouts=stereo,volume=0.6[out]" \
  -map "[out]" -ar 48000 -ac 2 -c:a libmp3lame -q:a 3 "$OUT"
