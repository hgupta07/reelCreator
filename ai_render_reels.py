#!/usr/bin/env python3
"""
ai_render_reels.py
------------------
AI-powered reel renderer. Two modes:

  --mode sd_keyframe      (default, ~5-10 min total)
    Generates 2 AI keyframes per slide via Stable Diffusion text-to-image,
    then smooth cross-dissolves + Ken Burns between them. Fast, practical.

  --mode animatediff_lcm  (AnimateDiff Lightning, 4 steps, best for MPS)
    True animated video per slide using ByteDance AnimateDiff-Lightning.
    ~15-30 min per clip on M1 Pro MPS (vs hours for standard AnimateDiff).

  --mode animatediff      (standard AnimateDiff, overnight batch only)
    25-step AnimateDiff — hours per slide on MPS. Use for Windows/CUDA.

Memory controls baked in:
  - PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 (disables MPS memory guard)
  - attention slicing + VAE slicing (reduces peak memory ~40%)
  - cache cleared between every slide
  - generates at 256x256, upscales to 1080x1920 (4x less VRAM)

Usage:
  python3 ai_render_reels.py
  python3 ai_render_reels.py --date 2026-03-07 --brand vedic_blueprint
  python3 ai_render_reels.py --mode animatediff_lcm   # Lightning 4-step
  python3 ai_render_reels.py --steps 20               # SD steps (default 25)
  python3 ai_render_reels.py --cpu-offload            # most memory-safe mode
"""

import argparse
import gc
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# MUST be set before importing torch — disables MPS memory high-watermark guard
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

import numpy as np
from PIL import Image

BASE = Path("/Users/himanshu/Documents/Reel Creator")
sys.path.insert(0, str(BASE / "daily_content"))

from visual_gen import BRANDS, add_logo, make_background, render_slide
from render_reels import (
    BRAND_SETTINGS,
    audio_duration,
    compute_durations,
    detect_planet,
    make_voiceover,
    save_ambient_wav,
)


# ── Per-slide AI prompts ────────────────────────────────────────────────────────
SLIDE_PROMPTS = {
    "planet_hook_shani":   "saturn planet golden rings floating in deep cosmic space, purple nebula, mystical light rays, 8k cinematic masterpiece",
    "planet_hook_rahu":    "dark eclipse planet in cosmic void, mysterious purple smoke, shadowy energy, cinematic 8k",
    "planet_hook_guru":    "jupiter planet with aurora cosmic space, golden green divine light, serene nebula, cinematic",
    "planet_hook_mangal":  "red mars planet in fiery cosmic space, intense energy, dramatic lighting, cinematic 8k",
    "planet_hook_surya":   "golden sun with solar flares, divine light rays streaming, cosmic space, cinematic 8k",
    "planet_hook_chandra": "silver crescent moon in starry night, soft blue cosmic glow, serene cinematic 8k",
    "planet_hook_shukra":  "venus planet rose gold ethereal light, beautiful cosmic nebula, cinematic 8k",
    "highlight":           "golden light particles floating in deep cosmic space, ancient energy, mystical atmosphere 8k",
    "body":                "ancient indian temple silhouette against starry cosmic night, divine atmosphere, cinematic 8k",
    "cta":                 "golden divine light rays deep space, celestial uplifting energy, cosmic cinematic 8k",
    "hook":                "dramatic cosmic nebula energy explosion, stars particles, mystical atmosphere, 8k cinematic",
    "quote":               "deep space nebula soft glowing stars, ancient cosmic wisdom, serene atmosphere 8k",
    "list":                "cosmic particles geometric light patterns, ancient wisdom energy, space cinematic 8k",
    "default":             "cosmic space stars purple nebula, dark mystical atmosphere, cinematic 8k",
}

NEG = (
    "blurry, low quality, distorted, text, watermark, logo, "
    "bad anatomy, ugly, nsfw, jpeg artifacts, overexposed, flat"
)

# Brand-specific prompt suffixes — keep visual identity consistent
BRAND_PROMPT_SUFFIX = {
    "vedic_blueprint": "vedic ancient indian mystical dark cosmos",
    "trail_maker":     "bold dramatic high contrast cinematic red black",
    "cloudezee":       "clean corporate blue purple soft light modern",
}


def slide_prompt(slide_data: dict, brand: str = "vedic_blueprint", slide_idx: int = 0) -> str:
    """
    Build a per-slide AI prompt.
    - style → base cosmic prompt
    - headline keywords → added for uniqueness across slides
    - brand suffix → keeps visual identity consistent
    """
    style   = slide_data.get("style", "default")
    suffix  = BRAND_PROMPT_SUFFIX.get(brand, "")

    if style == "planet_hook":
        planet = slide_data.get("planet", "shani")
        base = SLIDE_PROMPTS.get(f"planet_hook_{planet}", SLIDE_PROMPTS["planet_hook_shani"])
        return f"{base}, {suffix}"

    base = SLIDE_PROMPTS.get(style, SLIDE_PROMPTS["default"])

    # Inject 2-3 keywords from the slide headline for visual uniqueness
    headline = slide_data.get("headline", "")
    if headline:
        # Take first 3 significant words (skip short words)
        words = [w for w in headline.split() if len(w) > 3][:3]
        if words:
            base = f"{base}, {' '.join(words).lower()}"

    return f"{base}, {suffix}"


# ── Memory helpers ──────────────────────────────────────────────────────────────
def free_mps_cache():
    """Release MPS cached tensors and run Python GC."""
    import torch
    torch.mps.empty_cache()
    gc.collect()


def _apply_memory_opts(pipe, cpu_offload: bool = False):
    """Apply memory-saving options to any diffusers pipeline."""
    if cpu_offload:
        # Most aggressive: keeps only active layer on GPU, rest on CPU RAM
        pipe.enable_model_cpu_offload()
        print("  [mem] CPU offload enabled")
    else:
        pipe.enable_attention_slicing(1)   # slice size 1 = least peak memory
        pipe.enable_vae_slicing()          # decode one latent at a time
        pipe.to("mps")
    return pipe


# ── SD text-to-image pipeline (lazy loaded) ─────────────────────────────────────
_sd_pipe = None


def get_sd_pipe(cpu_offload: bool = False):
    global _sd_pipe
    if _sd_pipe is not None:
        return _sd_pipe

    import torch
    from diffusers import StableDiffusionPipeline

    print("  [AI] Loading SD 1.5 text-to-image pipeline…")
    pipe = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        dtype=torch.float16,
        safety_checker=None,           # disable false-positive NSFW blocking
        requires_safety_checker=False,
    )
    _sd_pipe = _apply_memory_opts(pipe, cpu_offload)
    print("  [AI] SD pipeline ready")
    return _sd_pipe


def _portrait_dims(res: int) -> tuple:
    """Return (width, height) in 9:16 portrait ratio, both divisible by 8."""
    w = (res // 8) * 8
    h = round(w * 16 / 9 / 8) * 8
    return w, h


def gen_keyframes(
    prompt: str, n: int = 2, steps: int = 25,
    base_seed: int = 42, cpu_offload: bool = False,
    res: int = 256,
) -> list:
    """
    Generate N SD keyframes at portrait 9:16 ratio (res wide).
    Default 256×448 — much less upscaling distortion than square.
    Returns list of PIL Images.
    """
    import torch

    pipe = get_sd_pipe(cpu_offload)
    w, h = _portrait_dims(res)
    frames = []
    for i in range(n):
        seed = base_seed + i * 1337
        print(f"  [AI] Keyframe {i+1}/{n}  {w}×{h}  seed={seed}  '{prompt[:50]}…'")
        with torch.inference_mode():
            out = pipe(
                prompt=prompt,
                negative_prompt=NEG,
                num_inference_steps=steps,
                height=h,
                width=w,
                generator=torch.Generator("mps").manual_seed(seed),
            )
        frames.append(out.images[0])
        free_mps_cache()   # release between keyframes
    return frames


# ── AnimateDiff Lightning pipeline (lazy, 4-step, best for MPS) ─────────────────
_adlcm_pipe = None


def get_adlcm_pipe(cpu_offload: bool = False):
    global _adlcm_pipe
    if _adlcm_pipe is not None:
        return _adlcm_pipe

    import torch
    from diffusers import AnimateDiffPipeline, MotionAdapter
    from diffusers.schedulers import EulerDiscreteScheduler

    print("  [AI] Loading AnimateDiff Lightning (4-step) adapter…")
    adapter = MotionAdapter.from_pretrained(
        "ByteDance/AnimateDiff-Lightning",
        subfolder="animatediff_lightning_4step_diffusers",
        dtype=torch.float16,
    )
    print("  [AI] Loading SD 1.5 checkpoint for Lightning…")
    pipe = AnimateDiffPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        motion_adapter=adapter,
        dtype=torch.float16,
        safety_checker=None,
        requires_safety_checker=False,
    )
    # Lightning requires Euler scheduler, NOT DDIM
    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config,
        timestep_spacing="trailing",
        beta_schedule="linear",
    )
    _adlcm_pipe = _apply_memory_opts(pipe, cpu_offload)
    print("  [AI] AnimateDiff Lightning ready")
    return _adlcm_pipe


def gen_lightning_frames(
    prompt: str, n_frames: int = 8, steps: int = 4,
    seed: int = 42, cpu_offload: bool = False, res: int = 256,
) -> list:
    """Generate animated frames using AnimateDiff Lightning (4 steps). Returns list of PIL Images."""
    import torch

    pipe = get_adlcm_pipe(cpu_offload)
    print(f"  [AI] Lightning {n_frames} frames  steps={steps}  {res}px  '{prompt[:50]}…'")
    with torch.inference_mode():
        out = pipe(
            prompt=prompt,
            negative_prompt=NEG,
            num_frames=n_frames,
            guidance_scale=1.0,        # Lightning uses guidance_scale=1.0
            num_inference_steps=steps,
            height=res,
            width=res,
            generator=torch.Generator("mps").manual_seed(seed),
        )
    free_mps_cache()
    return out.frames[0]


# ── Standard AnimateDiff pipeline (lazy, for --mode animatediff / CUDA) ─────────
_ad_pipe = None


def get_ad_pipe(cpu_offload: bool = False):
    global _ad_pipe
    if _ad_pipe is not None:
        return _ad_pipe

    import torch
    from diffusers import AnimateDiffPipeline, DDIMScheduler, MotionAdapter

    print("  [AI] Loading AnimateDiff standard adapter…")
    adapter = MotionAdapter.from_pretrained(
        "guoyww/animatediff-motion-adapter-v1-5-2",
        torch_dtype=torch.float16,
    )
    pipe = AnimateDiffPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        motion_adapter=adapter,
        torch_dtype=torch.float16,
        safety_checker=None,
        requires_safety_checker=False,
    )
    pipe.scheduler = DDIMScheduler.from_config(
        pipe.scheduler.config,
        clip_sample=False,
        timestep_spacing="linspace",
        beta_schedule="linear",
        steps_offset=1,
    )
    _ad_pipe = _apply_memory_opts(pipe, cpu_offload)
    print("  [AI] AnimateDiff standard pipeline ready")
    return _ad_pipe


def gen_animatediff_frames(
    prompt: str, n_frames: int = 8, steps: int = 25,
    seed: int = 42, cpu_offload: bool = False, res: int = 256,
) -> list:
    """Generate animated frames using standard AnimateDiff. Returns list of PIL Images."""
    import torch

    pipe = get_ad_pipe(cpu_offload)
    print(f"  [AI] AnimateDiff {n_frames} frames  steps={steps}  {res}px  '{prompt[:50]}…'")
    with torch.inference_mode():
        out = pipe(
            prompt=prompt,
            negative_prompt=NEG,
            num_frames=n_frames,
            guidance_scale=7.5,
            num_inference_steps=steps,
            height=res,
            width=res,
            generator=torch.Generator("mps").manual_seed(seed),
        )
    free_mps_cache()
    return out.frames[0]


# ── Frame scaling: 512x512 → 1080x1920 ─────────────────────────────────────────
def scale_frame(pil_img: Image.Image, out_w: int = 1080, out_h: int = 1920) -> np.ndarray:
    """Scale 512x512 to fill 1080x1920 — scale to height, crop center horizontally."""
    scale = out_h / pil_img.height       # 1920 / 512 = 3.75
    new_w = int(pil_img.width * scale)   # 1920
    img = pil_img.resize((new_w, out_h), Image.LANCZOS)
    x0 = (new_w - out_w) // 2
    img = img.crop((x0, 0, x0 + out_w, out_h))
    return np.array(img)


# ── sd_keyframe mode: cross-dissolve + Ken Burns between 2 AI keyframes ─────────
def make_clip_keyframe(
    keyframe_a: Image.Image,
    keyframe_b: Image.Image,
    overlay: Image.Image,
    duration: float,
    fps: int = 24,
):
    """
    Smooth clip: cross-dissolves from keyframe_a to keyframe_b over duration,
    with a gentle Ken Burns zoom-in. Text overlay composited on every frame.
    """
    from moviepy.editor import VideoClip

    W, H = overlay.size
    arr_a = scale_frame(keyframe_a, W, H).astype(float)
    arr_b = scale_frame(keyframe_b, W, H).astype(float)

    ov = np.array(overlay.convert("RGBA"))
    ov_rgb = ov[:, :, :3].astype(float)
    ov_a   = ov[:, :, 3:4].astype(float) / 255.0

    def make_frame(t):
        alpha = t / max(duration, 0.001)   # 0.0 → 1.0

        # Smooth S-curve dissolve (starts and ends gracefully)
        s = alpha * alpha * (3 - 2 * alpha)
        bg_float = arr_a * (1.0 - s) + arr_b * s

        # Gentle Ken Burns: 1.0 → 1.06 zoom-in over duration
        zoom = 1.0 + 0.06 * alpha
        if zoom > 1.001:
            zh = int(H / zoom)
            zw = int(W / zoom)
            y0 = (H - zh) // 2
            x0 = (W - zw) // 2
            crop = bg_float[y0:y0+zh, x0:x0+zw]
            # Resize back using nearest-neighbor (fast, avoid PIL round-trip)
            ys = np.linspace(0, zh - 1, H).astype(int).clip(0, zh - 1)
            xs = np.linspace(0, zw - 1, W).astype(int).clip(0, zw - 1)
            bg_float = crop[np.ix_(ys, xs)]

        out = (ov_rgb * ov_a + bg_float * (1.0 - ov_a)).clip(0, 255).astype(np.uint8)
        return out

    return VideoClip(make_frame, duration=duration).set_fps(fps)


# ── animatediff mode: composite overlay over looped AI frames ───────────────────
def make_clip_animatediff(frames: list, overlay: Image.Image, duration: float, fps: int = 24):
    from moviepy.editor import VideoClip

    W, H = overlay.size
    scaled = [scale_frame(f, W, H) for f in frames]
    n = len(scaled)

    ov = np.array(overlay.convert("RGBA"))
    ov_rgb = ov[:, :, :3].astype(float)
    ov_a   = ov[:, :, 3:4].astype(float) / 255.0

    def make_frame(t):
        idx = int(t * fps) % n
        bg  = scaled[idx].astype(float)
        out = (ov_rgb * ov_a + bg * (1.0 - ov_a)).clip(0, 255).astype(np.uint8)
        return out

    return VideoClip(make_frame, duration=duration).set_fps(fps)


# ── Render one reel ─────────────────────────────────────────────────────────────
def render_reel_ai(
    brand: str, content: dict, out_dir: Path,
    steps: int = 25, mode: str = "sd_keyframe",
    cpu_offload: bool = False, res: int = 256,
):
    from moviepy.editor import (
        AudioFileClip,
        CompositeAudioClip,
        concatenate_audioclips,
        concatenate_videoclips,
    )

    mood      = BRAND_SETTINGS.get(brand, BRAND_SETTINGS["vedic_blueprint"])["mood"]
    slides    = content["visual"].get("slides", [])
    voiceover = content["visual"].get("voiceover", "")
    n         = len(slides)
    W, H      = 1080, 1920

    if not slides:
        print(f"  ERROR: no slides in content")
        return

    print(f"\n  [{brand}] {n} slides  mood={mood}  mode={mode}  steps={steps}  res={res}  cpu_offload={cpu_offload}")

    # Voiceover
    planet  = detect_planet(content)
    vo_path = out_dir / "voiceover.mp3"
    has_vo  = bool(voiceover) and make_voiceover(voiceover, vo_path, brand, planet)

    durations = compute_durations(n, audio_duration(vo_path) if has_vo else None)
    print(f"  [timing] {[round(d, 1) for d in durations]}s per slide")

    # Generate AI backgrounds, one slide at a time (clears cache between each)
    black_bg = make_background(W, H, brand)
    clips = []

    for i, (slide, dur) in enumerate(zip(slides, durations)):
        prompt = slide_prompt(slide, brand=brand, slide_idx=i)
        print(f"  [slide {i+1}/{n}] '{slide.get('headline', '')[:40]}'")
        seed = 42 + i * 7

        if mode == "animatediff_lcm":
            frames  = gen_lightning_frames(prompt, n_frames=8, steps=4, seed=seed, cpu_offload=cpu_offload, res=res)
            overlay = render_slide(slide, i, n, brand, "reel", black_bg, overlay_only=True)
            overlay = add_logo(overlay, brand, W, H).convert("RGBA")
            clip = make_clip_animatediff(frames, overlay, dur)
        elif mode == "animatediff":
            frames  = gen_animatediff_frames(prompt, n_frames=8, steps=steps, seed=seed, cpu_offload=cpu_offload, res=res)
            overlay = render_slide(slide, i, n, brand, "reel", black_bg, overlay_only=True)
            overlay = add_logo(overlay, brand, W, H).convert("RGBA")
            clip = make_clip_animatediff(frames, overlay, dur)
        else:
            # sd_keyframe: 2 AI keyframes + smooth dissolve (default, fastest)
            kfs     = gen_keyframes(prompt, n=2, steps=steps, base_seed=seed, cpu_offload=cpu_offload, res=res)
            overlay = render_slide(slide, i, n, brand, "reel", black_bg, overlay_only=True)
            overlay = add_logo(overlay, brand, W, H).convert("RGBA")
            clip = make_clip_keyframe(kfs[0], kfs[1], overlay, dur)

        clips.append(clip)
        free_mps_cache()   # clear after every slide

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

    suffix = "ai" if mode == "sd_keyframe" else "ai_hq"
    out = out_dir / f"{brand}_reel_{suffix}.mp4"
    print(f"  [export] {out.name}…")
    video.write_videofile(
        str(out), fps=24, codec="libx264",
        audio_codec="aac", preset="fast", logger=None,
    )
    print(f"  Done -> {out}")

    for p in [music_path, vo_path]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",  default=None)
    parser.add_argument("--brand", default="all")
    parser.add_argument(
        "--steps", type=int, default=25,
        help="SD inference steps (default 25). Use 15 for quick preview.",
    )
    parser.add_argument(
        "--mode", default="sd_keyframe",
        choices=["sd_keyframe", "animatediff_lcm", "animatediff"],
        help="sd_keyframe=fast (default), animatediff_lcm=Lightning 4-step, animatediff=standard 25-step",
    )
    parser.add_argument(
        "--res", type=int, default=256,
        help="Generation width (default 256 → 256×448 portrait). Use 384 for sharper backgrounds.",
    )
    parser.add_argument(
        "--cpu-offload", action="store_true",
        help="Enable CPU offload (slowest but safest on low memory — guaranteed no OOM).",
    )
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
        render_reel_ai(
            brand, content, reel_dir,
            steps=args.steps, mode=args.mode,
            cpu_offload=args.cpu_offload, res=args.res,
        )

    print("\n  All done.\n")


if __name__ == "__main__":
    main()
