# Reel Creator — AI-Powered Multi-Brand Content Factory

An automated content generation system that produces daily social media content for multiple brands using the Claude API, renders branded slide images with PIL, and generates MP4 reels with Ken Burns motion effects and neural TTS voiceovers.

Built for Instagram Reels, LinkedIn posts, and LinkedIn carousels — all from a single daily run.

---

## What it does

1. **Generates structured content JSON** — Claude API reads your `MASTER_PROMPT.md` (brand voice, marketing rules, content pillars) and outputs ready-to-use copy: hooks, slide text, voiceover scripts, captions, hashtags.

2. **Renders branded slide images** — PIL draws each slide with your brand palette, typography, and layout. Supports 9:16 (reels), 1:1 (carousels), and 1.91:1 (LinkedIn).

3. **Produces MP4 reels** — MoviePy assembles slides into a video with Ken Burns zoom/pan motion per slide, Microsoft Neural TTS voiceover (via `edge-tts`), and ambient background music per brand mood.

```
Daily run → JSON content → PNG slides → MP4 reel
                                      → LinkedIn post text
                                      → Instagram caption + hashtags
```

---

## Stack

| Layer | Library |
|-------|---------|
| Content generation | [Anthropic Claude API](https://docs.anthropic.com) (`claude-sonnet-4-6`) |
| Slide rendering | Pillow (PIL) |
| Video assembly | MoviePy 1.0.3 |
| TTS voiceover | edge-tts 7.2.7 (Microsoft Neural) |
| Audio | numpy |
| Config | PyYAML |

---

## Project structure

```
├── render_reels.py          # MP4 renderer — Ken Burns + TTS + music
├── ai_render_reels.py       # AI-assisted render variant
├── generate_reel.py         # Legacy single-reel generator
│
├── daily_content/
│   ├── run.py               # Orchestrator — runs all brands for a given date
│   ├── content_gen.py       # Claude API caller — returns structured JSON
│   ├── visual_gen.py        # PIL slide image generator
│   ├── social_post.py       # (Optional) LinkedIn / Instagram posting
│   ├── config.yaml          # API keys + schedule (uses REPLACE_ME placeholders)
│   ├── MASTER_PROMPT.md     # Your brand voices + marketing rules (gitignored)
│   └── MASTER_PROMPT.example.md  # Template — copy and customise
│
├── Knowledge/
│   └── marketing_expert_knowledge.md  # Optional marketing reference
│
├── fonts/
│   └── Cinzel-Bold.ttf      # Font (SIL Open Font License)
│
└── output/
    └── YYYY-MM-DD/
        └── {brand}/
            └── {content_type}/
                ├── {brand}_{content_type}_content.json
                ├── slide_01.png … slide_N.png
                └── {brand}_{content_type}.mp4
```

---

## Setup

### 1. Install dependencies

```bash
pip install anthropic moviepy Pillow numpy pyyaml edge-tts requests
brew install ffmpeg   # macOS
```

### 2. Configure

```bash
cp daily_content/MASTER_PROMPT.example.md daily_content/MASTER_PROMPT.md
cp daily_content/config.yaml daily_content/config.yaml
```

Edit `config.yaml` — replace all `REPLACE_ME` values:

```yaml
anthropic:
  api_key: "sk-ant-YOUR_KEY_HERE"

brands:
  your_brand:
    enabled: true
    platform: instagram
```

Edit `MASTER_PROMPT.md` — define your brand voice, content pillars, and CTA rules per brand. See `MASTER_PROMPT.example.md` for the full structure.

### 3. Run

```bash
# Generate content for today (all brands)
python3 daily_content/run.py

# Specific date
python3 daily_content/run.py --date 2026-03-16

# Specific brand only
python3 daily_content/run.py --date 2026-03-16 --brand your_brand

# Render reels (after content JSON is generated)
python3 render_reels.py --date 2026-03-16 --brand your_brand
```

---

## How the content system works

### MASTER_PROMPT.md

The single file that defines everything about your brands. For each brand it specifies:

- **Channel goal** — the one outcome every post must serve (get clients / grow followers / attract inbound)
- **Audience** — who they are, awareness level, what they feel
- **Voice** — tone, language, style rules
- **Content pillars** — what to post each day of the week
- **CTA rules** — when to sell hard, when to educate, when to just engage
- **Hook formulas** — platform-native patterns that work for that audience

Claude reads this file on every run and generates content that is brand-consistent without any additional context.

### Schedule (config.yaml)

Maps each brand to a list of content types per day of the week:

```yaml
schedule:
  your_instagram_brand:
    0: [reel, carousel]    # Monday
    1: [reel]              # Tuesday
    3: [reel, carousel]    # Thursday

  your_linkedin_brand:
    0: [linkedin_post]     # Monday
    3: [linkedin_carousel] # Thursday — PDF carousel
```

### Output JSON structure

Every piece of content outputs a JSON file with:

- `copy` — hook, body paragraphs, CTA, caption, hashtags
- `visual.slides` — headline, subtext, style, and highlight word per slide
- `visual.voiceover` — full spoken script for TTS or avatar tools (Synthesia, HeyGen, ElevenLabs)
- `post_meta` — best posting time, content pillar, production notes

---

## Rendering reels

`render_reels.py` takes the output JSON + slide PNGs and produces an MP4:

- **Ken Burns motion** — each slide gets a distinct slow zoom/pan pattern (configurable per slide index)
- **Slide timing** — hook slide ≤ 3.5s (urgency gap), CTA slide longest (12s+)
- **TTS voiceover** — `edge-tts` with Microsoft Neural voices (50+ languages, 300+ voices)
- **Ambient music** — brand mood drives music style (mystical / energetic / corporate)

### Supported voices (examples)

| Brand type | Voice | Style |
|-----------|-------|-------|
| Hindi spiritual | `hi-IN-SwaraNeural` | Warm, feminine |
| British professional | `en-GB-RyanNeural` | Confident, male |
| Corporate | `en-GB-SoniaNeural` | Authoritative, female |
| US casual | `en-US-GuyNeural` | Conversational, male |

Any [edge-tts supported voice](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support) works.

---

## Using with AI avatar tools

The `visual.voiceover` field in every output JSON is a clean, production-ready script. Feed it directly into:

- **Synthesia** — paste as teleprompter script for your avatar
- **HeyGen** — avatar video generation
- **ElevenLabs** — voice clone synthesis (drop-in replacement for edge-tts)

---

## Multi-brand example

The system is designed to run multiple brands in one daily pass — Instagram reels for one brand, LinkedIn posts for another, all from the same `run.py` call. Each brand has its own voice, palette, platform, schedule, and CTA logic defined in `MASTER_PROMPT.md`.

---

## Requirements

```
Python 3.9+
anthropic>=0.84
moviepy==1.0.3
Pillow>=11.0
numpy
pyyaml
edge-tts>=7.0
requests
ffmpeg (system — install via brew or apt)
```

---

## License

MIT
