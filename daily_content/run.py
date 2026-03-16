#!/usr/bin/env python3
"""
run.py — Daily Content Generator Orchestrator

Usage:
  python3 run.py                          # all brands, today
  python3 run.py --brand vedic_blueprint
  python3 run.py --brand trail_maker --date 2026-03-10
  python3 run.py --topic "Why Agentforce is not a chatbot"
  python3 run.py --post                   # generate AND post
  python3 run.py --dry-run
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from content_gen import generate_content, get_content_types, save_content
from visual_gen  import generate_visuals, generate_trail_maker_logo
from social_post import post_content

BASE_DIR   = Path(__file__).parent
CFG_PATH   = BASE_DIR / "config.yaml"
ALL_BRANDS = ["vedic_blueprint", "cloudezee", "trail_maker", "himanshu"]


def load_config():
    with open(CFG_PATH) as f:
        return yaml.safe_load(f)


def get_output_dir(cfg, date, brand, content_type):
    base = Path(cfg["output"].get("base_dir", "../output"))
    if not base.is_absolute():
        base = BASE_DIR / base
    return base / date.strftime("%Y-%m-%d") / brand / content_type


def ensure_trail_maker_logo():
    logo_path = BASE_DIR.parent / "fonts" / "trail_maker_logo.png"
    if not logo_path.exists():
        generate_trail_maker_logo(logo_path)


def print_caption(content):
    caption  = content["copy"].get("caption", "")
    hashtags = " ".join(content["copy"].get("hashtags", []))
    ct       = content["content_type"].upper()
    print(f"\n  {'─'*50}")
    print(f"  CAPTION ({ct}):")
    print(f"  {'─'*50}")
    for line in caption.split("\n"):
        print(f"  {line}")
    if hashtags:
        print(f"\n  {hashtags}")
    print(f"  {'─'*50}")


def run_single(brand, content_type, date, cfg, topic=None, do_post=False):
    output_dir = get_output_dir(cfg, date, brand, content_type)
    print(f"\n  [{brand.upper()}  →  {content_type}]")
    try:
        content     = generate_content(brand, content_type, date, topic, cfg)
        if cfg["output"].get("save_json", True):
            save_content(content, output_dir)
        print(f"  Hook: {content['copy'].get('hook', '')[:72]}")

        image_paths = generate_visuals(content, output_dir)

        video_path = output_dir / f"{brand}_reel.mp4"
        if not video_path.exists():
            video_path = None

        if do_post and cfg.get("posting", {}).get("auto_post", False):
            post_content(content, image_paths, cfg, video_path)
        else:
            print_caption(content)

        return True
    except Exception as e:
        print(f"\n  ERROR — {brand}/{content_type}: {e}")
        traceback.print_exc()
        return False


def run_brand(brand, date, cfg, topic=None, do_post=False):
    brand_cfg = cfg.get("brands", {}).get(brand, {})
    if not brand_cfg.get("enabled", True):
        print(f"\n  Skipping {brand} (disabled in config).")
        return {}
    types   = get_content_types(brand, date, cfg)
    results = {}
    for ct in types:
        if ct:  # skip empty entries (e.g. himanshu has no post on Mon/Sun)
            results[ct] = run_single(brand, ct, date, cfg, topic, do_post)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand",   choices=ALL_BRANDS + ["all"], default="all",
                        help="Brand: vedic_blueprint | cloudezee | trail_maker | himanshu | all")
    parser.add_argument("--date",    default=None)
    parser.add_argument("--topic",   default=None)
    parser.add_argument("--post",    action="store_true")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    if args.dry_run:
        cfg.setdefault("posting", {})["dry_run"] = True

    if args.date:
        try:
            run_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date: {args.date}")
            sys.exit(1)
    else:
        run_date = datetime.today()

    brands = ALL_BRANDS if args.brand == "all" else [args.brand]
    ensure_trail_maker_logo()

    print(f"\n  Daily Content Generator  |  {run_date.strftime('%A, %d %b %Y')}")
    print("\n  Schedule today:")
    for b in brands:
        types = get_content_types(b, run_date, cfg)
        print(f"    {b:22s} -> {' + '.join(types)}")

    all_results = {}
    for brand in brands:
        all_results[brand] = run_brand(brand, run_date, cfg, args.topic, args.post)

    print(f"\n{'='*54}\n  SUMMARY\n{'='*54}")
    for brand, type_results in all_results.items():
        for ct, ok in type_results.items():
            print(f"  {'OK' if ok else 'FAIL'}  {brand} / {ct}")
    print(f"{'='*54}\n")


if __name__ == "__main__":
    main()
