#!/usr/bin/env python3
"""Generate DBSurgeon demo voiceover with ElevenLabs TTS.

Reads ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID from .env / .env.local.
Writes .local/demo_video/DBSurgeon/voiceover/{beat}.mp3 and full.mp3 (+ timings.json).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local" / "demo_video" / "DBSurgeon" / "voiceover"

# Launch-demo VO (~45–55s). On-screen callouts still carry muted viewing.
BEATS = [
    {
        "id": "01_problem",
        "callout": "Wrong SQL beats slow SQL",
        "text": (
            "Agent fleets dump SQL onto Postgres. Blind open models look cheap — "
            "then return wrong answers. On our sealed ninety-eight case bench, "
            "Fireworks open raw accepts forty-seven percent but returns eleven incorrect rewrites. "
            "Never ship that."
        ),
    },
    {
        "id": "02_stack",
        "callout": "Fireworks + surgical harness",
        "text": (
            "We run Fireworks serverless — flash, open one-twenty-B, Nemotron Ultra on escalate — "
            "behind a surgical harness. Verify on every fixture including nulls. "
            "Repair or abstain. Fine-tune optional. "
            "Result: fifty-seven percent accept, zero wrong — frontier parity on an open stack."
        ),
    },
    {
        "id": "03_demo",
        "callout": "57% accept · 0 wrong",
        "text": (
            "Live surgery: accept only when the rewrite is equivalent and twenty percent faster. "
            "Nullable anti-joins that would corrupt? The harness abstains. "
            "Database Surgeon — open models, surgical harness, zero wrong returned."
        ),
    },
]


def load_dotenv() -> None:
    for name in (".env.local", ".env"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def tts(text: str, voice_id: str, api_key: str, dest: Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = json.dumps(
        {
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": float(os.environ.get("ELEVENLABS_STABILITY", "0.45")),
                "similarity_boost": float(os.environ.get("ELEVENLABS_SIMILARITY", "0.75")),
                "style": float(os.environ.get("ELEVENLABS_STYLE", "0.15")),
                "use_speaker_boost": True,
            },
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"ElevenLabs HTTP {exc.code}: {detail}") from exc


def duration_seconds(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def concat_mp3(parts: list[Path], dest: Path) -> None:
    lst = dest.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            str(dest),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise SystemExit("Need ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env.local")
    OUT.mkdir(parents=True, exist_ok=True)
    timings = []
    cursor = 0.0
    parts = []
    for beat in BEATS:
        path = OUT / f"{beat['id']}.mp3"
        print(f"TTS {beat['id']}…", flush=True)
        tts(beat["text"], voice_id, api_key, path)
        dur = duration_seconds(path)
        timings.append(
            {
                "id": beat["id"],
                "callout": beat["callout"],
                "path": str(path.relative_to(ROOT)),
                "start": round(cursor, 3),
                "duration": round(dur, 3),
                "end": round(cursor + dur, 3),
                "text": beat["text"],
            }
        )
        cursor += dur + 0.35  # short breath between beats
        parts.append(path)
        # write silence gap as separate tiny file? concat with pad via ffmpeg filter instead
        print(f"  {dur:.1f}s → {path.name}", flush=True)

    # Rebuild full with 350ms silence between beats
    silence = OUT / "_silence_350ms.mp3"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "0.35",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(silence),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sequenced: list[Path] = []
    for i, p in enumerate(parts):
        sequenced.append(p)
        if i < len(parts) - 1:
            sequenced.append(silence)
    full = OUT / "full.mp3"
    concat_mp3(sequenced, full)
    meta = {
        "voice_id": voice_id,
        "model_id": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        "full": str(full.relative_to(ROOT)),
        "total_seconds": round(duration_seconds(full), 3),
        "beats": timings,
    }
    (OUT / "timings.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({"ok": True, "total_seconds": meta["total_seconds"], "full": meta["full"]}, indent=2))


if __name__ == "__main__":
    main()
