"""
Gully Commentator - minimal Streamlit front end.

    record -> transcript -> commentary -> audio plays

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import pipeline

st.set_page_config(page_title="Gully Commentator", page_icon="🏏", layout="centered")

st.title("🏏 Gully Commentator")
st.caption(
    "Speak what just happened in Hindi, Tamil or code-mixed speech — "
    "hear it back as a gully-uncle commentary line."
)

# Fail early and clearly if the key is missing.
if not os.environ.get("SARVAM_API_KEY"):
    st.error(
        "SARVAM_API_KEY is not set. Export it in the shell before launching "
        "(`export SARVAM_API_KEY=...`) or add it to a local `.env` file. "
        "Never commit or paste the key."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Input: record live, or fall back to a pre-recorded clip if the demo hiccups
# ---------------------------------------------------------------------------

st.subheader("1. The moment")
clip = st.audio_input("Record the moment (or use the fallback below)")

fallback_dir = Path(__file__).parent / "fallback"
fallback_files = sorted(fallback_dir.glob("*.wav")) if fallback_dir.exists() else []
fallback_choice = None
if fallback_files:
    fallback_choice = st.selectbox(
        "Pre-recorded fallback (use if the live mic misbehaves)",
        ["— none —"] + [f.name for f in fallback_files],
    )

use_fallback = fallback_choice and fallback_choice != "— none —"
if use_fallback:
    clip = (fallback_dir / fallback_choice).read_bytes()
    st.audio(clip, format="audio/wav")

# ---------------------------------------------------------------------------
# Run the one flow
# ---------------------------------------------------------------------------

if st.button("Commentate! 🎙️", type="primary", disabled=clip is None):
    audio_bytes = clip if isinstance(clip, bytes) else clip.read()
    try:
        with st.spinner("Saaras is listening…"):
            transcript, lang = pipeline.transcribe(audio_bytes)
        with st.spinner("Sarvam-105B is going full gully-uncle…"):
            data = pipeline.commentate(transcript, lang)
        with st.spinner("Bulbul is voicing it…"):
            audio = pipeline.speak(data["commentary"], lang)

        st.subheader("2. What Saaras heard")
        st.write(transcript or "_(empty transcript — try a clearer clip)_")
        st.caption(f"Detected language: {lang}")

        st.subheader("3. The commentary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Minute", data["minute"])
        c2.metric("Player", data["player"])
        c3.metric("Event", data["event"])
        st.success(data["commentary"])

        st.subheader("4. Hear it back")
        st.audio(audio, format="audio/wav", autoplay=True)
        st.download_button("Download this call (.wav)", audio,
                           file_name="commentary.wav", mime="audio/wav")

    except Exception as exc:  # surface the real error during a live demo
        st.error(f"Something broke: {exc}")
