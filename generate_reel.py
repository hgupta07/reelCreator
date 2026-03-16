#!/usr/bin/env python3
"""
Reel Generator: Vedic Astrology vs Rs.500 Online Readings
Date: 13 Feb | Category: Education
Output: 1080x1920 (9:16 vertical) @ 30fps  |  Target ~45-55s
"""

import os, math, random, shutil, time, wave as wave_mod
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import requests

# ── Paths ────────────────────────────────────────────────────────────────────
OUT_DIR  = Path(__file__).parent
TMP_DIR  = OUT_DIR / "tmp_reel"
FONT_DIR = OUT_DIR / "fonts"
OUTPUT   = OUT_DIR / "Feb13_VedicAstrology_Reel.mp4"

# ── Video specs ──────────────────────────────────────────────────────────────
W, H        = 1080, 1920
FPS         = 30
SAMPLE_RATE = 44100

# ── Colour palette ───────────────────────────────────────────────────────────
BG_TOP    = (12, 3, 3)
BG_BOTTOM = (5, 1, 1)
SAFFRON   = (217, 119,  6)
GOLD      = (200, 160, 40)
MAROON    = (140,  35, 35)
WHITE     = (255, 255, 255)
OFF_WHITE = (220, 210, 195)
DIM       = (150, 135, 120)
SHADOW    = (30,   8,  8)

# ── Fonts ────────────────────────────────────────────────────────────────────
FONT_DIR.mkdir(exist_ok=True)
_font_cache = {}

CINZEL_URL = "https://fonts.gstatic.com/s/cinzel/v26/8vIU7ww63mVu7gtR-kwKxNvkNOjw-jHgTYo.ttf"

def _download_font(name, url):
    path = FONT_DIR / name
    if path.exists():
        return str(path)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"  ✓ Downloaded {name}")
        return str(path)
    except Exception as e:
        print(f"  ! Font download failed: {e}  — using system fallback")
        return None

def _system_font():
    for p in [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        if Path(p).exists():
            return p
    return None

_font_path = None

def get_font(size):
    global _font_path
    if size in _font_cache:
        return _font_cache[size]
    if _font_path is None:
        _font_path = _download_font("Cinzel-Bold.ttf", CINZEL_URL) or _system_font()
    try:
        f = ImageFont.truetype(_font_path, size) if _font_path else ImageFont.load_default()
    except Exception:
        f = ImageFont.load_default()
    _font_cache[size] = f
    return f


# ── Drawing helpers ──────────────────────────────────────────────────────────
def _wrap(text, font, draw, max_w):
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        bb = draw.textbbox((0, 0), test, font=font)
        if (bb[2] - bb[0]) > max_w and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines

def draw_text(draw, text, y, font, color, max_w=940, gap=14, shadow=True):
    """Draw centered, word-wrapped text with optional shadow. Returns new y."""
    for line in _wrap(text, font, draw, max_w):
        bb = draw.textbbox((0, 0), line, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (W - tw) // 2
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=SHADOW)
        draw.text((x, y), line, font=font, fill=color)
        y += th + gap
    return y

def hline(draw, y, half_w=180, color=GOLD, thick=2):
    draw.line([(W // 2 - half_w, y), (W // 2 + half_w, y)], fill=color, width=thick)

def progress_dots(draw, slide_idx, total):
    dot_y    = H - 60
    spacing  = 22
    start_x  = (W - (total - 1) * spacing) // 2
    for i in range(total):
        cx = start_x + i * spacing
        if i == slide_idx:
            draw.ellipse([cx - 7, dot_y - 7, cx + 7, dot_y + 7], fill=SAFFRON)
        else:
            draw.ellipse([cx - 4, dot_y - 4, cx + 4, dot_y + 4], fill=(60, 40, 20))


# ── Background ───────────────────────────────────────────────────────────────
def make_bg():
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    for py in range(H):
        t = py / H
        r = int(BG_TOP[0] + t * (BG_BOTTOM[0] - BG_TOP[0]))
        g = int(BG_TOP[1] + t * (BG_BOTTOM[1] - BG_TOP[1]))
        b = int(BG_TOP[2] + t * (BG_BOTTOM[2] - BG_TOP[2]))
        draw.line([(0, py), (W, py)], fill=(r, g, b))

    rng = random.Random(42)
    for _ in range(200):
        sx, sy = rng.randint(0, W), rng.randint(0, H)
        ss = rng.choice([1, 1, 1, 2])
        br = rng.randint(55, 175)
        draw.ellipse([sx - ss, sy - ss, sx + ss, sy + ss],
                     fill=(br, int(br * .84), int(br * .48)))

    # Faint dotted orbital rings
    for (cx, cy, rad) in [(W // 2, H // 2, 440), (W // 2, H // 2, 510)]:
        for angle in range(0, 360, 6):
            ax = cx + int(rad * math.cos(math.radians(angle)))
            ay = cy + int(rad * math.sin(math.radians(angle)))
            if 0 <= ax < W and 0 <= ay < H:
                draw.point((ax, ay), fill=(65, 40, 8))

    # Corner ticks (gold)
    corners = [
        (55, 55, 55, 100), (55, 55, 100, 55),
        (W-55, 55, W-55, 100), (W-55, 55, W-100, 55),
        (55, H-55, 55, H-100), (55, H-55, 100, H-55),
        (W-55, H-55, W-55, H-100), (W-55, H-55, W-100, H-55),
    ]
    for (x1, y1, x2, y2) in corners:
        draw.line([(x1, y1), (x2, y2)], fill=GOLD, width=2)

    return img


# ── Slides ────────────────────────────────────────────────────────────────────
# Each slide: id, render type, voice text (SHORT & PUNCHY for reel timing)
SLIDES = [
    dict(id=1,  render="hook",
         voice="That 500 rupee reading? It probably only looked at 10 percent of your chart."),

    dict(id=2,  render="setup",
         voice="Here's what real Vedic astrology covers — versus what those apps actually do."),

    dict(id=3,  render="critique",
         voice="Apps only check your Sun sign. That's just the month you were born. That's it."),

    dict(id=4,  render="quote",
         voice="Your Sun sign is just the book cover. It tells you nothing about the story inside."),

    # Slide 5 split into 4 quick component slides
    dict(id=5,  render="comp_moon",
         voice="Moon sign — your mind and emotions."),

    dict(id=6,  render="comp_asc",
         voice="Ascendant — your personality and life path."),

    dict(id=7,  render="comp_dasha",
         voice="Dasha system — which planetary period is running right now."),

    dict(id=8,  render="comp_div",
         voice="Divisional charts — career, marriage, and health. Separately."),

    dict(id=9,  render="timing",
         voice="Without Dasha, a reading can't tell you WHEN. And timing is the whole point."),

    dict(id=10, render="punchline",
         voice="If someone reads you based only on your Sun sign — you got a horoscope, not a reading."),

    dict(id=11, render="requirements",
         voice="Real Vedic astrology needs your exact birth time, date, and place. No birth time? No reading."),

    dict(id=12, render="cta",
         voice="Have you ever gotten an astrology reading that was actually accurate? YES or NO in the comments."),
]
N = len(SLIDES)


def make_slide(slide, bg):
    img  = bg.copy()
    draw = ImageDraw.Draw(img)
    idx  = slide["id"] - 1
    r    = slide["render"]

    f96 = get_font(96)
    f80 = get_font(80)
    f66 = get_font(66)
    f52 = get_font(52)
    f42 = get_font(42)
    f30 = get_font(30)
    mw  = 920

    progress_dots(draw, idx, N)

    # ── HOOK ──────────────────────────────────────────────────────────────────
    if r == "hook":
        y = 580
        y = draw_text(draw, "That \u20b9500 reading?", y, f96, WHITE,   mw, 18) + 40
        hline(draw, y, 130); y += 55
        y = draw_text(draw, "Probably only looked at", y, f52, OFF_WHITE, mw, 12) + 8
        y = draw_text(draw, "10% of your chart.",      y, f80, SAFFRON,   mw, 12)

    # ── SETUP ─────────────────────────────────────────────────────────────────
    elif r == "setup":
        y = 760
        y = draw_text(draw, "Real Vedic astrology", y, f80, GOLD,      mw, 16) + 14
        hline(draw, y, 220, DIM, 1); y += 44
        y = draw_text(draw, "vs what apps actually do", y, f66, OFF_WHITE, mw, 14)

    # ── CRITIQUE ──────────────────────────────────────────────────────────────
    elif r == "critique":
        y = 590
        y = draw_text(draw, "Apps only check your", y, f66, OFF_WHITE, mw, 12) + 10
        y = draw_text(draw, "SUN SIGN",             y, f96, SAFFRON,   mw, 12) + 32
        hline(draw, y, 110, MAROON, 3); y += 58
        y = draw_text(draw, "That's just the month you were born.", y, f52, OFF_WHITE, mw, 10) + 6
        y = draw_text(draw, "That's it.",                           y, f52, DIM,       mw, 10)

    # ── QUOTE ─────────────────────────────────────────────────────────────────
    elif r == "quote":
        y = 620
        y = draw_text(draw, "Your Sun sign is just", y, f66, OFF_WHITE, mw, 12) + 8
        y = draw_text(draw, "the book cover.",       y, f96, SAFFRON,   mw, 12) + 38
        hline(draw, y, 170); y += 58
        y = draw_text(draw, "It tells you nothing about", y, f52, OFF_WHITE, mw, 10) + 6
        y = draw_text(draw, "the story inside.",          y, f52, DIM,       mw, 10)

    # ── COMPONENT SLIDES (5–8) ────────────────────────────────────────────────
    elif r == "comp_moon":
        _component_slide(draw, "\u263d", "Moon Sign", "your mind & emotions", f96, f66, f52, mw)

    elif r == "comp_asc":
        _component_slide(draw, "\u2191", "Ascendant", "your personality & life path", f96, f66, f52, mw)

    elif r == "comp_dasha":
        _component_slide(draw, "\u29d6", "Dasha System", "which planetary period is NOW", f96, f66, f52, mw)

    elif r == "comp_div":
        _component_slide(draw, "\u29c9", "Divisional Charts", "career  -  marriage  -  health", f96, f66, f52, mw)

    # ── TIMING ────────────────────────────────────────────────────────────────
    elif r == "timing":
        y = 620
        y = draw_text(draw, "Without Dasha,",             y, f80, OFF_WHITE, mw, 14) + 5
        y = draw_text(draw, "a reading can't tell you",   y, f66, OFF_WHITE, mw, 12) + 5
        y = draw_text(draw, "WHEN.",                      y, f96, SAFFRON,   mw, 12) + 38
        hline(draw, y, 150); y += 58
        y = draw_text(draw, "Timing is the whole point.", y, f52, DIM,       mw, 10)

    # ── PUNCHLINE ─────────────────────────────────────────────────────────────
    elif r == "punchline":
        y = 590
        y = draw_text(draw, '"You\'re a Scorpio"', y, f80, OFF_WHITE, mw, 14) + 5
        y = draw_text(draw, "= not a reading.",    y, f66, DIM,       mw, 12) + 38
        hline(draw, y, 190, MAROON, 3); y += 58
        y = draw_text(draw, "You got",        y, f66, OFF_WHITE, mw, 12) + 8
        y = draw_text(draw, "a horoscope.",   y, f96, SAFFRON,   mw, 12)

    # ── REQUIREMENTS ──────────────────────────────────────────────────────────
    elif r == "requirements":
        y = 440
        y = draw_text(draw, "Real Vedic needs:", y, f80, GOLD, mw, 14) + 20
        hline(draw, y, 220); y += 50
        for item in ["Exact birth time", "Date of birth", "Place of birth"]:
            y = draw_text(draw, item, y, f66, WHITE, mw, 10) + 28
        hline(draw, y + 10, 260, MAROON, 2); y += 55
        y = draw_text(draw, "No birth time = No reading. Period.", y, f52, SAFFRON, mw, 10)

    # ── CTA ───────────────────────────────────────────────────────────────────
    elif r == "cta":
        y = 575
        y = draw_text(draw, "Ever gotten a reading",       y, f80, WHITE, mw, 16) + 5
        y = draw_text(draw, "that was actually accurate?", y, f80, WHITE, mw, 16) + 44
        hline(draw, y, 170); y += 64
        y = draw_text(draw, "Drop a",        y, f52, OFF_WHITE, mw, 10) + 5
        y = draw_text(draw, "YES  or  NO",   y, f96, SAFFRON,   mw, 12) + 8
        y = draw_text(draw, "in the comments below", y, f52, OFF_WHITE, mw, 10)

    # Branding watermark
    draw_text(draw, "Vedic Astrology Decoded", H - 100, f30,
              (90, 55, 15), mw, 0, shadow=False)
    return img


def _component_slide(draw, symbol, label, desc, f_sym, f_lbl, f_desc, mw):
    """Shared layout for the 4 Vedic component slides."""
    y = 700

    # Big symbol (use fallback char if font doesn't support it)
    try:
        y = draw_text(draw, symbol, y, f_sym, GOLD, mw, 8) + 20
    except Exception:
        pass

    hline(draw, y, 80, SAFFRON, 2); y += 40
    y = draw_text(draw, label, y, f_lbl, SAFFRON, mw, 12) + 14
    hline(draw, y, 140, DIM, 1);   y += 36
    y = draw_text(draw, desc,  y, f_desc, OFF_WHITE, mw, 10)


# ── Ambient music ─────────────────────────────────────────────────────────────
def save_ambient_wav(duration, path):
    sr = SAMPLE_RATE
    t  = np.linspace(0, duration, int(sr * duration), dtype=np.float64)

    music = (
        0.32 * np.sin(2 * np.pi * 55.0  * t) +
        0.18 * np.sin(2 * np.pi * 110.0 * t) +
        0.10 * np.sin(2 * np.pi * 165.0 * t) +
        0.06 * np.sin(2 * np.pi * 220.0 * t) +
        0.04 * np.sin(2 * np.pi * 330.0 * t)
    )
    music *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.22 * t))
    music += (0.025 * np.sin(2 * np.pi * 880 * t)
              * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t)))

    fade = int(sr * 2.0)
    music[:fade]  *= np.linspace(0, 1, fade)
    music[-fade:] *= np.linspace(1, 0, fade)

    music   = music / np.max(np.abs(music)) * 0.45
    samples = (music * 32767).astype(np.int16)
    stereo  = np.column_stack([samples, samples])

    with wave_mod.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(stereo.tobytes())


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    from moviepy.editor import (
        ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips,
    )

    TMP_DIR.mkdir(exist_ok=True)
    print("\n✨  Vedic Astrology Reel Generator")
    print("=" * 45)

    # 1. Background
    print("\n[1/5] Rendering background...")
    bg = make_bg()
    print("      Done.")

    # 2. Voiceovers — Indian English female
    print("\n[2/5] Generating voiceovers (Indian English)...")
    voice_paths = []
    for s in SLIDES:
        vp = TMP_DIR / f"v{s['id']:02d}.mp3"
        tts = gTTS(text=s["voice"], lang="en", tld="co.in", slow=False)
        tts.save(str(vp))
        preview = s["voice"][:55] + ("..." if len(s["voice"]) > 55 else "")
        print(f"      Slide {s['id']:2d} ✓  \"{preview}\"")
        time.sleep(0.5)
        voice_paths.append(vp)

    # 3. Slide frames
    print("\n[3/5] Rendering slides...")
    slide_paths = []
    for s in SLIDES:
        img = make_slide(s, bg)
        sp  = TMP_DIR / f"s{s['id']:02d}.png"
        img.save(str(sp))
        slide_paths.append(sp)
    print(f"      {N} slides ✓")

    # 4. Build clips
    print("\n[4/5] Assembling clips...")
    clips     = []
    total_dur = 0.0
    for s, sp, vp in zip(SLIDES, slide_paths, voice_paths):
        ac  = AudioFileClip(str(vp))
        dur = ac.duration + 0.25
        vc  = ImageClip(str(sp)).set_duration(dur).set_audio(ac)
        clips.append(vc)
        total_dur += dur
        print(f"      Slide {s['id']:2d}: {dur:.1f}s")

    final = concatenate_videoclips(clips, method="compose")
    print(f"\n      Total duration: {total_dur:.1f}s")

    # 5. Music + render
    print("\n[5/5] Mixing music and rendering...")
    music_path = TMP_DIR / "ambient.wav"
    save_ambient_wav(final.duration + 1.0, music_path)
    music = AudioFileClip(str(music_path)).set_duration(final.duration).volumex(0.13)
    mixed = CompositeAudioClip([music, final.audio.volumex(1.0)])
    final = final.set_audio(mixed)

    final.write_videofile(
        str(OUTPUT),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(TMP_DIR / "tmp_audio.m4a"),
        remove_temp=True,
        verbose=False,
        logger=None,
    )

    shutil.rmtree(TMP_DIR)

    print(f"\n✅  Reel ready!  →  {OUTPUT}")
    print(f"    {total_dur:.0f}s  |  {W}×{H} @ {FPS}fps  |  9:16 vertical")
    print(f"    Ready for Instagram Reels / YouTube Shorts\n")


if __name__ == "__main__":
    main()
