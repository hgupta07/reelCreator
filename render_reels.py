#!/usr/bin/env python3
"""
render_reels.py - Render MP4 reel videos with Ken Burns motion effect
Usage: python3 render_reels.py
       python3 render_reels.py --date 2026-03-10
       python3 render_reels.py --brand vedic_blueprint
"""

import asyncio
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path("/Users/himanshu/Documents/Reel Creator")

# ── Brand settings ─────────────────────────────────────────────────────────────
BRAND_SETTINGS = {
    "vedic_blueprint": {
        "voice": "hi-IN-SwaraNeural",   # Hindi female — warm, spiritual
        "rate":  "+15%",
        "mood":  "mystical",
    },
    "trail_maker": {
        "voice": "en-GB-RyanNeural",    # British male — strong, confident
        "rate":  "+12%",
        "mood":  "energetic",
    },
    "cloudezee": {
        "voice": "en-GB-SoniaNeural",   # British female — authoritative
        "rate":  "+8%",
        "mood":  "corporate",
    },
}

# Ken Burns patterns per slide index (zoom_start, zoom_end, pan_x, pan_y)
# pan_x / pan_y: -1 = left/up, 0 = center, 1 = right/down
KB_PATTERNS = [
    (1.00, 1.09,  0.0,  0.0),   # slide 1: zoom in center   — HOOK, creates drama
    (1.08, 1.00,  0.3,  0.0),   # slide 2: zoom out + pan left
    (1.00, 1.08, -0.3,  0.0),   # slide 3: zoom in + pan right
    (1.06, 1.00,  0.0,  0.2),   # slide 4: zoom out + slight pan up
    (1.00, 1.07,  0.2, -0.2),   # slide 5: zoom in diagonal
    (1.00, 1.05,  0.0,  0.0),   # slide 6: slow gentle zoom — CTA, calm confidence
]


# ── Ken Burns clip ─────────────────────────────────────────────────────────────
def ken_burns_clip(img_path, duration, fps=30, slide_idx=0):
    """Return a VideoClip with slow zoom/pan (Ken Burns) applied to a still image."""
    from moviepy.editor import VideoClip

    pattern = KB_PATTERNS[slide_idx % len(KB_PATTERNS)]
    scale_s, scale_e, pan_x, pan_y = pattern

    img    = Image.open(str(img_path)).convert("RGB")
    W, H   = img.size
    arr    = np.array(img)

    def make_frame(t):
        progress = t / max(duration, 0.001)
        scale    = scale_s + (scale_e - scale_s) * progress

        crop_w = int(W / scale)
        crop_h = int(H / scale)
        extra_x = W - crop_w
        extra_y = H - crop_h

        x1 = extra_x // 2 + int(pan_x * extra_x / 2)
        y1 = extra_y // 2 + int(pan_y * extra_y / 2)
        x1 = max(0, min(x1, extra_x))
        y1 = max(0, min(y1, extra_y))

        cropped = arr[y1:y1 + crop_h, x1:x1 + crop_w]
        result  = Image.fromarray(cropped).resize((W, H), Image.BILINEAR)
        return np.array(result)

    return VideoClip(make_frame, duration=duration).set_fps(fps)


# Planet-specific voice overrides (planet_hook format)
# Male planets: Shani, Rahu, Mangal, Surya, Guru
# Female planets: Chandra, Shukra
PLANET_VOICES = {
    "shani":   ("hi-IN-MadhurNeural", "+8%"),    # deep Hindi male — stern, authoritative
    "rahu":    ("hi-IN-MadhurNeural", "+5%"),     # deep Hindi male — slow, mysterious
    "mangal":  ("hi-IN-MadhurNeural", "+20%"),    # fast and fierce
    "surya":   ("hi-IN-MadhurNeural", "+12%"),    # commanding Hindi male
    "guru":    ("hi-IN-MadhurNeural", "+6%"),     # calm, wise Hindi male
    "chandra": ("hi-IN-SwaraNeural",  "+5%"),     # soft Hindi female
    "shukra":  ("hi-IN-SwaraNeural",  "+10%"),    # warm Hindi female
}


# ── TTS ────────────────────────────────────────────────────────────────────────
async def _tts_async(text, out_path, voice, rate):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))


def detect_planet(content):
    """Return planet name if this is a planet_hook reel, else None."""
    slides = content.get("visual", {}).get("slides", [])
    if slides and slides[0].get("style") == "planet_hook":
        return slides[0].get("planet", "shani")
    return None


def make_voiceover(text, out_path, brand="vedic_blueprint", planet=None):
    if planet and planet in PLANET_VOICES:
        voice, rate = PLANET_VOICES[planet]
        print(f"  [tts] planet={planet} → {voice}  rate={rate}")
    else:
        s = BRAND_SETTINGS.get(brand, BRAND_SETTINGS["vedic_blueprint"])
        voice, rate = s["voice"], s["rate"]
        print(f"  [tts] {voice}  rate={rate}")
    try:
        asyncio.run(_tts_async(text, out_path, voice, rate))
        return True
    except Exception as e:
        print(f"  [tts] WARN: {e}")
        return False


# ── Ambient music ──────────────────────────────────────────────────────────────
def save_ambient_wav(out_path, duration, mood="mystical"):
    try:
        import wave

        sr = 44100
        n  = int(sr * duration)
        t  = np.linspace(0, duration, n, False)

        if mood == "mystical":
            freqs, amps = [110, 220, 330, 440], [0.40, 0.25, 0.15, 0.10]
            trem_hz, trem_dep = 0.30, 0.15
        elif mood == "energetic":
            freqs, amps = [330, 440, 660, 880, 1100], [0.30, 0.28, 0.20, 0.12, 0.08]
            trem_hz, trem_dep = 4.0, 0.35
        elif mood == "upbeat":
            freqs, amps = [220, 330, 440, 550], [0.30, 0.30, 0.20, 0.10]
            trem_hz, trem_dep = 1.20, 0.20
        else:  # corporate
            freqs, amps = [130, 260, 390, 520], [0.35, 0.30, 0.20, 0.10]
            trem_hz, trem_dep = 0.50, 0.10

        audio = sum(a * np.sin(2 * math.pi * f * t) for f, a in zip(freqs, amps))
        audio *= (1.0 - trem_dep) + trem_dep * np.sin(2 * math.pi * trem_hz * t)

        if mood == "energetic":
            beat_env = np.clip(np.sin(2 * math.pi * 2.0 * t), 0, 1) ** 8
            audio   += 0.15 * beat_env * np.sin(2 * math.pi * 220 * t)

        # Short 0.1 s fade-in only (music must hit immediately)
        fade_in  = min(int(0.1 * sr), n // 8)
        fade_out = min(int(1.5 * sr), n // 4)
        audio[:fade_in]   *= np.linspace(0, 1, fade_in)
        audio[-fade_out:] *= np.linspace(1, 0, fade_out)

        peak = float(np.abs(audio).max())
        if peak > 0:
            audio = audio / peak * 0.6

        samples = (audio * 32767).astype(np.int16)
        with wave.open(str(out_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(samples.tobytes())
        print(f"  [music] mood={mood}  {duration:.1f}s")
        return True
    except Exception as e:
        print(f"  [music] WARN: {e}")
        return False


# ── Audio duration ─────────────────────────────────────────────────────────────
def audio_duration(path):
    try:
        from moviepy.editor import AudioFileClip
        with AudioFileClip(str(path)) as a:
            return a.duration
    except Exception:
        return 4.0


# ── Slide timing ───────────────────────────────────────────────────────────────
def compute_durations(n_slides, total_vo_duration):
    """
    Hook slide (first) = shortest — creates urgency, viewer can't read fast enough = stays.
    Middle slides = normal.
    CTA slide (last) = longest — time to act.
    """
    weights = [0.7] + [1.0] * (n_slides - 2) + [1.5]  # hook short, CTA long
    if n_slides == 1:
        weights = [1.0]
    w_sum = sum(weights)

    if total_vo_duration:
        durations = [max(total_vo_duration * w / w_sum, 2.5) for w in weights]
        # Hook slide never more than 3.5 s — keeps scroll-stopping tension
        durations[0] = min(durations[0], 3.5)
    else:
        durations = [2.8] + [4.2] * (n_slides - 2) + [5.0]
        if n_slides == 1:
            durations = [5.0]

    return durations


# ── Render one reel ────────────────────────────────────────────────────────────
def render_reel(brand, content, out_dir):
    from moviepy.editor import (
        AudioFileClip, CompositeAudioClip,
        concatenate_videoclips, concatenate_audioclips,
    )

    mood       = BRAND_SETTINGS.get(brand, BRAND_SETTINGS["vedic_blueprint"])["mood"]
    slide_imgs = sorted(out_dir.glob("slide_*.png"))
    voiceover  = content["visual"].get("voiceover", "")
    n          = len(slide_imgs)

    if not slide_imgs:
        print(f"  ERROR: no slides in {out_dir}")
        return

    print(f"\n  [{brand}] {n} slides  mood={mood}")

    # Voiceover — use planet voice if planet_hook reel
    planet  = detect_planet(content)
    vo_path = out_dir / "voiceover.mp3"
    has_vo  = bool(voiceover) and make_voiceover(voiceover, vo_path, brand, planet)

    # Durations
    durations = compute_durations(n, audio_duration(vo_path) if has_vo else None)
    print(f"  [timing] {[round(d,1) for d in durations]}s per slide")

    # Ken Burns clips
    clips = []
    for i, (img, dur) in enumerate(zip(slide_imgs, durations)):
        print(f"  [kb] slide {i+1}/{n}  {dur:.1f}s…")
        clips.append(ken_burns_clip(img, dur, fps=30, slide_idx=i))
    video = concatenate_videoclips(clips, method="compose")

    # Audio
    tracks = []
    music_path = out_dir / "ambient.wav"
    if brand != "trail_maker" and save_ambient_wav(music_path, video.duration, mood):
        mc = AudioFileClip(str(music_path)).volumex(0.18)
        if mc.duration < video.duration:
            loops = int(video.duration / mc.duration) + 1
            mc = concatenate_audioclips([mc] * loops).subclip(0, video.duration)
        else:
            mc = mc.subclip(0, video.duration)
        tracks.append(mc)

    if has_vo:
        vc = AudioFileClip(str(vo_path)).volumex(1.0)
        if vc.duration > video.duration:
            vc = vc.subclip(0, video.duration)
        tracks.append(vc)

    if tracks:
        video = video.set_audio(CompositeAudioClip(tracks))

    out = out_dir / f"{brand}_reel.mp4"
    print(f"  [export] {out.name}…")
    video.write_videofile(str(out), fps=30, codec="libx264",
                          audio_codec="aac", preset="fast", logger=None)
    print(f"  Done -> {out}")

    for p in [music_path, vo_path]:
        if p.exists():
            try: p.unlink()
            except: pass


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser()
    parser.add_argument("--date",  default=None)
    parser.add_argument("--brand", default="all")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    output   = BASE / "output" / date_str
    brands   = list(BRAND_SETTINGS.keys()) if args.brand == "all" else [args.brand]

    for brand in brands:
        reel_dir   = output / brand / "reel"
        json_files = list(reel_dir.glob("*_content.json"))
        if not json_files:
            print(f"  SKIP {brand}: no content json in {reel_dir}")
            continue
        content = json.loads(json_files[0].read_text())
        render_reel(brand, content, reel_dir)

    print("\n  All done.\n")


if __name__ == "__main__":
    main()
