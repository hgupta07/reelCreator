"""
content_gen.py
--------------
Calls Claude API with the MASTER_PROMPT and brand/date context.
Returns structured JSON content ready for visual generation and posting.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import anthropic
import yaml


# ── Config ────────────────────────────────────────────────────────────────────
CFG_PATH    = Path(__file__).parent / "config.yaml"
PROMPT_PATH = Path(__file__).parent / "MASTER_PROMPT.md"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def _load_config():
    with open(CFG_PATH) as f:
        return yaml.safe_load(f)

def _load_master_prompt():
    return PROMPT_PATH.read_text()

# ── Schedule — returns LIST of content types for the day ─────────────────────
def get_content_types(brand: str, date: datetime, cfg: dict) -> list:
    """Return list of content types for this brand/day. Always a list."""
    dow      = date.weekday()          # 0=Mon … 6=Sun
    schedule = cfg.get("schedule", {}).get(brand, {})
    value    = schedule.get(dow, ["single_post"])
    return value if isinstance(value, list) else [value]

# ── Build the per-run prompt ──────────────────────────────────────────────────
def build_prompt(brand: str, date: datetime, content_type: str,
                 topic_override=None) -> str:
    day_name = DAYS[date.weekday()]
    date_str = date.strftime("%Y-%m-%d")
    return f"""Generate daily social media content with these parameters:

brand: {brand}
date: {date_str}
day_of_week: {day_name}
content_type: {content_type}
topic_override: {topic_override or "None — follow the content calendar"}

Follow the MASTER PROMPT instructions exactly. Return ONLY valid JSON."""

# ── Call Claude for ONE content type ─────────────────────────────────────────
def generate_content(
    brand: str,
    content_type: str,
    date=None,
    topic_override=None,
    cfg=None,
) -> dict:
    if date is None:
        date = datetime.today()
    if cfg is None:
        cfg = _load_config()

    master_prompt = _load_master_prompt()
    user_prompt   = build_prompt(brand, date, content_type, topic_override)

    api_key = cfg["anthropic"]["api_key"]
    model   = cfg["anthropic"].get("model", "claude-sonnet-4-6")

    client = anthropic.Anthropic(api_key=api_key)
    print(f"  🤖 Claude → {brand} / {content_type}...")

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=master_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    json_match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    json_str   = json_match.group(1).strip() if json_match else raw

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}\n  Raw:\n{raw[:400]}")
        raise

    return result

# ── Generate ALL content types for a brand/day ───────────────────────────────
def generate_all_for_day(brand: str, date=None, topic_override=None, cfg=None) -> list:
    """Returns a list of content dicts — one per content type scheduled today."""
    if date is None:
        date = datetime.today()
    if cfg is None:
        cfg = _load_config()
    types   = get_content_types(brand, date, cfg)
    results = []
    for ct in types:
        result = generate_content(brand, ct, date, topic_override, cfg)
        results.append(result)
    return results

# ── Save to output folder ─────────────────────────────────────────────────────
def save_content(content: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    brand        = content.get("brand", "unknown")
    content_type = content.get("content_type", "post")
    fname        = output_dir / f"{brand}_{content_type}_content.json"
    with open(fname, "w") as f:
        json.dump(content, f, indent=2)
    print(f"  💾 Saved → {fname.name}")
    return fname


# ── CLI quick-test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    brand = sys.argv[1] if len(sys.argv) > 1 else "vedic_blueprint"
    cfg   = _load_config()
    types = get_content_types(brand, datetime.today(), cfg)
    print(f"Today's schedule for {brand}: {types}")
