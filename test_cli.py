"""
Command-line tester — the "test with real input" step, without Streamlit.

Usage:
    python test_cli.py path/to/clip.wav
    python test_cli.py clip1.wav clip2.wav clip3.wav

Records nothing itself; point it at real clips you recorded, including one
with crowd/room noise and one where you stumble or code-mix.
"""

import sys
from pathlib import Path

import pipeline


def run_one(path: Path) -> None:
    print(f"\n=== {path.name} ({path.stat().st_size / 1024:.0f} KB) ===")
    audio_bytes = path.read_bytes()

    transcript, lang = pipeline.transcribe(audio_bytes)
    print(f"  language : {lang}")
    print(f"  transcript: {transcript}")

    data = pipeline.commentate(transcript, lang)
    print(f"  minute   : {data['minute']}")
    print(f"  player   : {data['player']}")
    print(f"  event    : {data['event']}")
    print(f"  commentary: {data['commentary']}")

    audio = pipeline.speak(data["commentary"], lang)
    out = path.with_suffix(".commentary.wav")
    out.write_bytes(audio)
    print(f"  audio    : wrote {out.name} ({len(audio) / 1024:.0f} KB)")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.exists():
            print(f"!! not found: {p}")
            continue
        run_one(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
