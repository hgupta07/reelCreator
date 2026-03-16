from typing import Optional
"""
visual_gen.py
-------------
Creates branded images for each content type and brand.
Formats supported:
  - Instagram single post  → 1080x1080 (1:1)
  - Instagram carousel     → 1080x1080 per slide
  - Instagram reel cover   → 1080x1920 (9:16)
  - LinkedIn post image    → 1200x628 (1.91:1)
"""

import math
import os
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
FONT_DIR   = BASE_DIR / "fonts"
LOGOS      = {
    "vedic_blueprint": BASE_DIR / "VedicBlueprintLogo" / "Wordmark Logo for Vedic Blueprint.png",
    "cloudezee":       BASE_DIR / "CloudEzeeLogos" / "CloudEzee.png",
    "trail_maker":     BASE_DIR / "fonts" / "trail_maker_logo.png",  # generated below
}
FONT_DIR.mkdir(exist_ok=True)

# ── Brand palettes ─────────────────────────────────────────────────────────────
BRANDS = {
    "vedic_blueprint": {
        "bg":        (10,  3,  3),
        "bg2":       (5,   1,  1),
        "primary":   (217, 119, 6),    # saffron
        "secondary": (122,  31, 31),   # maroon
        "accent":    (200, 160, 40),   # gold
        "white":     (255, 255, 255),
        "dim":       (180, 165, 145),
        "shadow":    (30,   8,  8),
        "stars":     True,
        "orbital":   True,
    },
    "cloudezee": {
        "bg":        (248, 248, 255),  # white bg (slight blue tint)
        "bg2":       (235, 242, 255),  # soft blue-white
        "primary":   (91,  155, 213),  # blue #5B9BD5
        "secondary": (155, 108, 200),  # purple/violet #9B6CC8
        "accent":    (107,  63, 160),  # deep purple #6B3FA0
        "white":     (36,  22,  80),   # dark purple — headline text on white bg
        "dim":       (107,  63, 160),  # deep purple — body text
        "shadow":    (210, 220, 238),  # light blue-gray shadow
        "stars":     False,
        "orbital":   False,
    },
    "trail_maker": {
        "bg":        (10,  10,  10),   # near-black
        "bg2":       (5,    5,   5),
        "primary":   (204,  31,  31),  # bold red
        "secondary": (255, 107,   0),  # electric orange
        "accent":    (255, 255, 255),  # white accent
        "white":     (255, 255, 255),
        "dim":       (180, 180, 180),
        "shadow":    (20,   5,   5),
        "stars":     False,
        "orbital":   False,
    },
    "himanshu": {
        "bg":        (20,  22,  28),   # deep charcoal
        "bg2":       (30,  33,  42),   # slightly lighter charcoal
        "primary":   (212, 160,  28),  # warm amber/gold
        "secondary": (255, 255, 255),  # white text
        "accent":    (240, 190,  55),  # bright gold highlight
        "white":     (255, 255, 255),  # main text on dark bg
        "dim":       (175, 168, 150),  # dimmed body text
        "shadow":    (10,  10,  15),   # deep shadow
        "stars":     False,
        "orbital":   False,
    },
}

# ── Canvas sizes ───────────────────────────────────────────────────────────────
SIZES = {
    "1:1":      (1080, 1080),
    "9:16":     (1080, 1920),
    "1.91:1":   (1200, 628),
    "4:5":      (1080, 1350),
}

FORMAT_MAP = {
    "single_post":        "1:1",
    "carousel":           "1:1",
    "reel":               "9:16",
    "linkedin_post":      "1.91:1",
    "linkedin_carousel":  "1:1",
}

# ── Font cache ─────────────────────────────────────────────────────────────────
_font_cache: dict = {}
_font_path: Optional[str] = None

def _get_font_path() -> Optional[str]:
    global _font_path
    if _font_path:
        return _font_path
    # Prefer Cinzel (already downloaded by reel generator)
    cinzel = FONT_DIR / "Cinzel-Bold.ttf"
    if cinzel.exists():
        _font_path = str(cinzel)
        return _font_path
    # System fallbacks
    candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            _font_path = c
            return _font_path
    return None

def font(size: int) -> ImageFont.FreeTypeFont:
    if size in _font_cache:
        return _font_cache[size]
    path = _get_font_path()
    try:
        f = ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except Exception:
        f = ImageFont.load_default()
    _font_cache[size] = f
    return f


# ── Helpers ───────────────────────────────────────────────────────────────────
def _wrap(draw, text: str, fnt, max_w: int) -> list:
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        bb = draw.textbbox((0, 0), test, font=fnt)
        if (bb[2] - bb[0]) > max_w and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines

def draw_text(draw, text: str, y: int, fnt, color, W: int,
              max_w: int = None, gap: int = 12, shadow_color=None) -> int:
    if max_w is None:
        max_w = W - 120
    for line in _wrap(draw, text, fnt, max_w):
        bb = draw.textbbox((0, 0), line, font=fnt)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (W - tw) // 2
        if shadow_color:
            draw.text((x + 3, y + 3), line, font=fnt, fill=shadow_color)
        draw.text((x, y), line, font=fnt, fill=color)
        y += th + gap
    return y

def hline(draw, y: int, W: int, half_w: int = 160, color=(200, 160, 40), thick: int = 2):
    draw.line([(W // 2 - half_w, y), (W // 2 + half_w, y)], fill=color, width=thick)

def progress_dots(draw, idx: int, total: int, W: int, H: int, accent):
    dy = H - 55
    sp = 22
    sx = (W - (total - 1) * sp) // 2
    for i in range(total):
        cx = sx + i * sp
        if i == idx:
            draw.ellipse([cx - 7, dy - 7, cx + 7, dy + 7], fill=accent)
        else:
            draw.ellipse([cx - 4, dy - 4, cx + 4, dy + 4], fill=(80, 60, 30))

def corner_ticks(draw, W: int, H: int, color, margin: int = 50, length: int = 40):
    pts = [
        (margin, margin, margin, margin + length),
        (margin, margin, margin + length, margin),
        (W - margin, margin, W - margin, margin + length),
        (W - margin, margin, W - margin - length, margin),
        (margin, H - margin, margin, H - margin - length),
        (margin, H - margin, margin + length, H - margin),
        (W - margin, H - margin, W - margin, H - margin - length),
        (W - margin, H - margin, W - margin - length, H - margin),
    ]
    for (x1, y1, x2, y2) in pts:
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)


# ── Background ────────────────────────────────────────────────────────────────
def make_background(W: int, H: int, brand: str) -> Image.Image:
    p   = BRANDS[brand]
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Gradient
    for py in range(H):
        t = py / H
        r = int(p["bg"][0] + t * (p["bg2"][0] - p["bg"][0]))
        g = int(p["bg"][1] + t * (p["bg2"][1] - p["bg"][1]))
        b = int(p["bg"][2] + t * (p["bg2"][2] - p["bg"][2]))
        draw.line([(0, py), (W, py)], fill=(r, g, b))

    if p["stars"]:
        rng = random.Random(7)
        for _ in range(160):
            sx, sy = rng.randint(0, W), rng.randint(0, H)
            ss = rng.choice([1, 1, 1, 2])
            br = rng.randint(50, 160)
            draw.ellipse([sx-ss, sy-ss, sx+ss, sy+ss],
                         fill=(br, int(br*.84), int(br*.48)))

    if p["orbital"]:
        cx, cy = W // 2, H // 2
        for rad in [int(min(W, H) * 0.38), int(min(W, H) * 0.46)]:
            for angle in range(0, 360, 6):
                ax = cx + int(rad * math.cos(math.radians(angle)))
                ay = cy + int(rad * math.sin(math.radians(angle)))
                if 0 <= ax < W and 0 <= ay < H:
                    draw.point((ax, ay), fill=(65, 40, 8))

    corner_ticks(draw, W, H, p["accent"])
    return img


# ── Logo overlay ──────────────────────────────────────────────────────────────
def add_logo(img: Image.Image, brand: str, W: int, H: int,
             max_w: int = 200, margin: int = 60) -> Image.Image:
    logo_path = LOGOS.get(brand)
    if not logo_path or not Path(logo_path).exists():
        return img

    logo = Image.open(logo_path).convert("RGBA")
    ratio = max_w / logo.width
    lw = int(logo.width * ratio)
    lh = int(logo.height * ratio)
    if lh > 80:            # cap height too
        ratio = 80 / logo.height
        lw, lh = int(logo.width * ratio), 80
    logo = logo.resize((lw, lh), Image.LANCZOS)

    x = (W - lw) // 2
    y = H - margin - lh

    # Paste with transparency
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.paste(logo, (x, y), logo)
    img = img.convert("RGB")
    return img


# ── Planet character generator ────────────────────────────────────────────────
PLANET_CONFIGS = {
    "shani":  {"body_dark":(18,12,55),  "body_light":(62,46,110), "glow":(95,65,175),  "accent":(200,160,40),  "eye":(12,6,40),    "ring":True,  "ring_col":(200,160,40),  "expr":"stern"},
    "rahu":   {"body_dark":(4,4,14),    "body_light":(28,22,58),  "glow":(75,35,135),  "accent":(148,78,218),  "eye":(190,55,55),  "ring":False, "ring_col":(148,78,218),  "expr":"mysterious"},
    "guru":   {"body_dark":(28,44,8),   "body_light":(75,115,28), "glow":(140,190,45), "accent":(200,160,40),  "eye":(18,38,4),    "ring":False, "ring_col":(200,160,40),  "expr":"wise"},
    "mangal": {"body_dark":(68,14,8),   "body_light":(155,38,22), "glow":(195,48,18),  "accent":(255,107,0),   "eye":(38,4,4),     "ring":False, "ring_col":(255,107,0),   "expr":"fierce"},
    "surya":  {"body_dark":(175,78,4),  "body_light":(252,162,18),"glow":(252,138,0),  "accent":(255,220,48),  "eye":(98,38,0),    "ring":False, "ring_col":(255,220,48),  "expr":"regal"},
    "chandra":{"body_dark":(18,28,58),  "body_light":(175,180,215),"glow":(155,165,215),"accent":(198,208,252), "eye":(8,12,48),    "ring":False, "ring_col":(198,208,252), "expr":"dreamy"},
    "shukra": {"body_dark":(58,8,48),   "body_light":(195,58,155),"glow":(215,75,175), "accent":(252,178,228), "eye":(78,4,58),    "ring":False, "ring_col":(252,178,228), "expr":"charming"},
}

def make_planet_character(planet_name: str, size: int = 900) -> Image.Image:
    """Draw a planet character with expressive face. Returns RGBA image."""
    cfg = PLANET_CONFIGS.get(planet_name.lower(), PLANET_CONFIGS["shani"])
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size // 2
    R  = int(size * 0.26)   # body radius — keeps ring within canvas

    # Outer glow
    gc = cfg["glow"]
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    for i in range(12, 0, -1):
        gr = R + i * 14
        gd.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*gc, int(10 * i)))
    img = Image.alpha_composite(img, glow)

    # Ring back half
    rc = cfg["ring_col"]
    if cfg["ring"]:
        rx = int(R * 1.72); ry = int(R * 0.36); ry_off = int(R * 0.06)
        rback = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rb = ImageDraw.Draw(rback)
        for w in range(14, 0, -1):
            rb.ellipse([cx-rx-w, cy-ry-ry_off-w, cx+rx+w, cy+ry-ry_off+w],
                       outline=(*rc, min(55 + w * 11, 215)), width=2)
        img = Image.alpha_composite(img, rback)

    # Planet body gradient (dark edge → lighter centre)
    draw = ImageDraw.Draw(img)
    bd, bl = cfg["body_dark"], cfg["body_light"]
    for i in range(R, 0, -2):
        t = (R - i) / R
        col = tuple(int(bd[j] + t * (bl[j] - bd[j])) for j in range(3))
        draw.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(*col, 255))

    # Subtle surface bands
    band_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bnd = ImageDraw.Draw(band_img)
    for b in range(-3, 4):
        by = cy + int(b * R * 0.15)
        bw = int(math.sqrt(max(0, R*R - (b * R * 0.15)**2)) * 0.90)
        if bw > 0:
            bnd.line([(cx-bw, by), (cx+bw, by)], fill=(*rc, 16), width=4)
    img = Image.alpha_composite(img, band_img)

    # Ring front arc (sits in front of lower planet)
    if cfg["ring"]:
        rx = int(R * 1.72); ry = int(R * 0.36); ry_off = int(R * 0.06)
        rfront = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rf = ImageDraw.Draw(rfront)
        for w in range(14, 0, -1):
            rf.arc([cx-rx-w, cy-ry-ry_off-w, cx+rx+w, cy+ry-ry_off+w],
                   start=0, end=180, fill=(*rc, min(145 + w * 7, 255)), width=4)
        img = Image.alpha_composite(img, rfront)

    # Sphere highlight (upper-left glossy spot)
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hlx = cx - int(R * 0.27); hly = cy - int(R * 0.27); hlr = int(R * 0.25)
    for i in range(hlr, 0, -2):
        t = 1 - i / hlr
        hd.ellipse([hlx-i, hly-i, hlx+i, hly+i], fill=(255, 245, 200, int(t * 62)))
    img = Image.alpha_composite(img, hl)
    draw = ImageDraw.Draw(img)

    ac = cfg["accent"]; ec = cfg["eye"]

    # Eyes
    eye_y  = cy - int(R * 0.08)
    eye_x  = int(R * 0.31)
    eye_r  = int(R * 0.16)
    for ex in [cx - eye_x, cx + eye_x]:
        draw.ellipse([ex-eye_r, eye_y-eye_r, ex+eye_r, eye_y+eye_r], fill=(242, 234, 212))
    iris_r = int(eye_r * 0.67)
    for ex in [cx - eye_x, cx + eye_x]:
        draw.ellipse([ex-iris_r, eye_y-iris_r, ex+iris_r, eye_y+iris_r], fill=(*ec, 255))
    cl = max(2, int(iris_r * 0.30))
    for ex in [cx - eye_x, cx + eye_x]:
        draw.ellipse([ex-iris_r//3-cl, eye_y-iris_r//3-cl,
                      ex-iris_r//3+cl, eye_y-iris_r//3+cl], fill=(255, 255, 255))

    # Eyebrows
    brow_y  = eye_y - int(eye_r * 1.7)
    brow_hw = int(eye_r * 1.28)
    bw      = max(5, int(R * 0.06))
    expr    = cfg["expr"]
    if expr in ("stern", "fierce"):
        draw.line([(cx-eye_x-brow_hw, brow_y-6), (cx-eye_x+brow_hw//2, brow_y+10)],
                  fill=(*ac, 255), width=bw)
        draw.line([(cx+eye_x-brow_hw//2, brow_y+10), (cx+eye_x+brow_hw, brow_y-6)],
                  fill=(*ac, 255), width=bw)
    elif expr in ("wise", "regal"):
        draw.line([(cx-eye_x-brow_hw, brow_y+4), (cx-eye_x+brow_hw//2, brow_y-3)],
                  fill=(*ac, 255), width=bw)
        draw.line([(cx+eye_x-brow_hw//2, brow_y-3), (cx+eye_x+brow_hw, brow_y+4)],
                  fill=(*ac, 255), width=bw)
    else:
        draw.arc([cx-eye_x-brow_hw, brow_y-6, cx-eye_x+brow_hw, brow_y+8],
                 start=205, end=335, fill=(*ac, 255), width=bw)
        draw.arc([cx+eye_x-brow_hw, brow_y-6, cx+eye_x+brow_hw, brow_y+8],
                 start=205, end=335, fill=(*ac, 255), width=bw)

    # Mouth
    mouth_y  = cy + int(R * 0.42)
    mouth_hw = int(R * 0.28)
    mouth_h  = int(R * 0.12)
    mw2      = max(4, int(R * 0.055))
    if expr in ("stern", "fierce"):
        draw.arc([cx-mouth_hw, mouth_y-mouth_h, cx+mouth_hw, mouth_y+mouth_h],
                 start=198, end=342, fill=(*ac, 255), width=mw2)
    elif expr in ("wise", "regal", "charming"):
        draw.arc([cx-mouth_hw, mouth_y-mouth_h, cx+mouth_hw, mouth_y+mouth_h],
                 start=18, end=162, fill=(*ac, 255), width=mw2)
    else:
        draw.line([(cx-mouth_hw, mouth_y), (cx+mouth_hw, mouth_y)],
                  fill=(*ac, 255), width=mw2)

    return img


# ── Slide renderer ────────────────────────────────────────────────────────────
def render_slide(
    slide_data: dict,
    slide_idx: int,
    total_slides: int,
    brand: str,
    content_type: str,
    bg: Image.Image,
    overlay_only: bool = False,
) -> Image.Image:
    p    = BRANDS[brand]
    W, H = bg.size
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0)) if overlay_only else bg.copy()
    draw = ImageDraw.Draw(img)

    style     = slide_data.get("style", "body")
    headline  = slide_data.get("headline", "")
    subtext   = slide_data.get("subtext", "")
    highlight = slide_data.get("highlight_word", "")

    pad = 80
    mw  = W - 2 * pad

    # ── Font sizing by canvas width ──────────────────────────────────────────
    if W == 1200:  # LinkedIn landscape
        f_lg, f_md, f_sm, f_xs = font(72), font(52), font(40), font(28)
    elif W == 1080 and H == 1080:   # square
        f_lg, f_md, f_sm, f_xs = font(82), font(62), font(46), font(32)
    else:           # 9:16 vertical
        f_lg, f_md, f_sm, f_xs = font(90), font(70), font(54), font(36)

    shd = p["shadow"]

    # ── Vertical start position ──────────────────────────────────────────────
    if H == 1080 or H == 628:
        y_start = H // 3
    else:
        y_start = 560

    y = y_start

    if style == "hook":
        y = draw_text(draw, headline, y, f_lg, p["white"], W, mw, 18, shd) + 30
        hline(draw, y, W, 120, p["accent"]); y += 48
        if subtext:
            y = draw_text(draw, subtext, y, f_md, p["primary"], W, mw, 12, shd)

    elif style == "highlight":
        if headline:
            y = draw_text(draw, headline, y, f_md, p["dim"], W, mw, 12, shd) + 10
        y = draw_text(draw, highlight or subtext, y, f_lg, p["primary"], W, mw, 12, shd) + 30
        hline(draw, y, W, 100, p["secondary"]); y += 40
        if subtext and not highlight:
            pass
        elif subtext:
            y = draw_text(draw, subtext, y, f_sm, p["dim"], W, mw, 10, shd)

    elif style == "quote":
        draw_text(draw, "\u201c", y, f_lg, p["accent"], W, mw, 0, shd)
        y += 20
        y = draw_text(draw, headline, y, f_md, p["white"], W, mw, 14, shd) + 30
        hline(draw, y, W, 140, p["accent"]); y += 45
        if subtext:
            y = draw_text(draw, subtext, y, f_sm, p["dim"], W, mw, 10, shd)

    elif style == "list":
        y = draw_text(draw, headline, y, f_md, p["primary"], W, mw, 14, shd) + 20
        hline(draw, y, W, 180, p["secondary"]); y += 36
        for item in (subtext.split("|") if "|" in subtext else [subtext]):
            y = draw_text(draw, item.strip(), y, f_sm, p["white"], W, mw, 10, shd) + 14

    elif style == "cta":
        y = draw_text(draw, headline, y, f_lg, p["white"], W, mw, 14, shd) + 30
        hline(draw, y, W, 120, p["accent"]); y += 45
        if subtext:
            y = draw_text(draw, subtext, y, f_md, p["primary"], W, mw, 10, shd)

    elif style == "planet_hook":
        planet_name = slide_data.get("planet", "shani")
        p_size = int(W * 0.88)   # planet canvas — fills width, ring still fits
        planet_img = make_planet_character(planet_name, p_size)

        # Subtle nebula glow on slide background behind the planet
        neb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nd  = ImageDraw.Draw(neb)
        nx, ny = W // 2, int(H * 0.37)
        for i in range(14, 0, -1):
            nr = int(p_size * 0.55 * i / 10)
            nd.ellipse([nx-nr, ny-nr, nx+nr, ny+nr],
                       fill=(*p["secondary"][:3], int(7 * i)))
        img_rgba = img.convert("RGBA")
        img_rgba = Image.alpha_composite(img_rgba, neb)

        # Paste planet character centred horizontally, near top
        px = (W - p_size) // 2
        py = int(H * 0.02)
        img_rgba.paste(planet_img, (px, py), planet_img)
        img  = img_rgba if overlay_only else img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        # Headline below the planet — large, no subtext on hook
        text_y = py + p_size + 24
        if headline:
            y = draw_text(draw, headline, text_y, f_lg, p["white"], W, mw, 18, shd) + 20
        if subtext:
            draw_text(draw, subtext, y, f_md, p["primary"], W, mw, 12, shd)

    else:  # body / default
        y = draw_text(draw, headline, y, f_md, p["white"], W, mw, 14, shd) + 16
        if subtext:
            y = draw_text(draw, subtext, y, f_sm, p["dim"], W, mw, 10, shd)

    # Progress dots (carousel only)
    if total_slides > 1 and content_type == "carousel":
        progress_dots(draw, slide_idx, total_slides, W, H, p["primary"])

    return img


# ── Main: generate all visuals for one piece of content ───────────────────────
def generate_visuals(content: dict, output_dir: Path) -> list:
    brand        = content["brand"]
    content_type = content["content_type"]
    visual       = content.get("visual", {})
    slides_data  = visual.get("slides", [])
    fmt_key      = FORMAT_MAP.get(content_type, "1:1")
    W, H         = SIZES[fmt_key]
    output_dir.mkdir(parents=True, exist_ok=True)

    bg = make_background(W, H, brand)

    # If no slides provided by Claude, build a single-slide fallback
    if not slides_data:
        slides_data = [{
            "index": 1,
            "headline": content["copy"].get("hook", ""),
            "subtext":  content["copy"].get("cta", ""),
            "style":    "hook",
            "highlight_word": "",
        }]

    saved_paths = []
    for i, slide in enumerate(slides_data):
        img = render_slide(slide, i, len(slides_data), brand, content_type, bg)
        img = add_logo(img, brand, W, H)
        fname = output_dir / f"slide_{i+1:02d}.png"
        img.save(str(fname))
        saved_paths.append(fname)
        print(f"  🖼  Slide {i+1}/{len(slides_data)} saved → {fname.name}")

    return saved_paths


# ── TrailMaker logo generator ─────────────────────────────────────────────────
def generate_trail_maker_logo(out_path: Path):
    """Generate a simple Red/Black TrailMaker wordmark logo."""
    W, H = 600, 180
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background pill shape
    draw.rounded_rectangle([(0, 0), (W-1, H-1)], radius=20,
                            fill=(10, 10, 10), outline=(204, 31, 31), width=3)

    # "THE" small above
    try:
        f_small = font(30)
        f_big   = font(68)
    except Exception:
        f_small = f_big = ImageFont.load_default()

    draw_text(draw, "THE", 18, f_small, (180, 180, 180), W, W - 40, 4)
    draw_text(draw, "TRAIL MAKER", 52, f_big, (204, 31, 31), W, W - 40, 6)

    # Red underline
    draw.line([(60, 145), (W - 60, 145)], fill=(204, 31, 31), width=3)
    # Tagline
    try:
        f_tag = font(22)
    except Exception:
        f_tag = ImageFont.load_default()
    draw_text(draw, "LEARN  •  BUILD  •  BLAZE", 152, f_tag, (255, 107, 0), W, W - 40, 0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))
    print(f"  ✓ TrailMaker logo created → {out_path.name}")


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logo_path = Path(__file__).parent.parent / "fonts" / "trail_maker_logo.png"
    generate_trail_maker_logo(logo_path)
    print("Logo generated.")
