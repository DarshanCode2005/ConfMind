"""
dataset_agent/agent.py
Main entry point for the ConfMind Dataset Agent.

Usage:
    python agent.py --github-url <url> [OPTIONS]

Options:
    --github-url      GitHub URL containing a list of event URLs (required)
    --model           Ollama model name (default: confmind-gemma4)
    --epochs          Number of exploration epochs before switching to exploitation (default: 3)
    --sample-size     URLs to sample per exploration epoch (default: 5)
    --categories      Comma-separated event categories to collect (default: conference,tech,music,sports)
    --delay           Seconds to sleep between web requests (default: 2.0)
    --output-csv      Output CSV path (default: dataset/events_2025_2026.csv)
    --output-json     Output JSON path (default: dataset/events_2025_2026.json)
    --dry-run         Run without writing output files
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

import colorlog
import ollama
import pandas as pd
from pydantic import ValidationError

# ── Make sure the ConfMind root is importable ────────────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dataset_agent.memory import (
    add_failed_site,
    add_note,
    add_strategy,
    format_memory_for_prompt,
    load_memory,
    save_memory,
)
from dataset_agent.tools import (
    build_search_queries,
    fetch_github_links,
    fetch_page,
    extract_text,
    search_and_fetch,
    web_search,
)
from dataset_agent.scraly_parser import (
    fetch_scraly_events,
    get_event_urls,
    SCRALY_URL,
)

# Attempt to reuse the existing ETL helpers from the main project
try:
    from scraping.etl_pipeline import save_to_csv, save_to_json
except ImportError:
    # Fallback if running outside the project root
    def save_to_csv(records, path):  # type: ignore[misc]
        import csv, json as _json
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if not records:
            return
        fieldnames = list(records[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                row = {k: ("|".join(v) if isinstance(v, list) else v) for k, v in r.items()}
                writer.writerow(row)

    def save_to_json(records, path):  # type: ignore[misc]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Logging setup ────────────────────────────────────────────────────────────────

def _setup_logging(level: int = logging.INFO) -> None:
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s: %(message)s",
        log_colors={
            "DEBUG": "cyan", "INFO": "green", "WARNING": "yellow",
            "ERROR": "red", "CRITICAL": "bold_red",
        },
    ))
    logging.basicConfig(level=level, handlers=[handler])


logger = logging.getLogger("dataset_agent")


# ── Ollama helpers ───────────────────────────────────────────────────────────────

def call_model(model: str, prompt: str, timeout: int = 180) -> str:
    """Send a prompt to the local Ollama model and return the response text."""
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": -1},
        )
        return response["message"]["content"].strip()
    except Exception as exc:
        logger.error(f"[ollama] Model call failed: {exc}")
        return ""


def parse_json_from_response(text: str) -> list[dict] | dict | None:
    """
    Extract the first valid JSON object or array from model output.
    Handles cases where the model wraps JSON in markdown code fences.
    """
    import re
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    text = text.strip()

    # Find the first [ or {
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        idx = text.find(start_char)
        if idx != -1:
            try:
                return json.loads(text[idx:])
            except json.JSONDecodeError:
                pass

    logger.debug(f"[parse_json] Could not parse JSON from: {text[:200]}")
    return None


# ── Exploration phase ────────────────────────────────────────────────────────────

EXPLORATION_PROMPT = """\
{memory_block}

## Your Task — SOURCE DISCOVERY MODE

You are identifying the best canonical data sources for this event:
  {event_url}

Here is text fetched from the candidate URL and search results:
---
{page_text}
---

Identify 2-3 candidate sources for this event.
Rate each source 0.0-1.0 based on its "Data Density" (how many EventSchema fields it can populate).

Return a JSON array of source objects:
[
  {{
    "strategy": "Found canonical page at [domain]",
    "score": 0.0,
    "fields_found": ["field1", "field2"],
    "notes": "Domain [domain] is excellent for [event_type] data because [reason]",
    "recommended_search_templates": ["{{event_name}} site:[domain]"],
    "extracted_event": {{...}}
  }}
]
"""

EXPLOITATION_PROMPT = """\
{memory_block}

## Your Task — DATA EXTRACTION MODE

Extract complete event data for:
  {event_url}

Primary source text:
---
{page_text}
---

Supplementary source text:
---
{search_text}
---

Use the top-performing sources from memory.
Return ONLY a JSON array of complete EventSchema objects. No commentary.
"""


def exploration_epoch(
    model: str,
    urls: list[str],
    sample_size: int,
    delay: float,
    mem: dict,
) -> dict:
    """
    Run one exploration epoch: sample URLs, try strategies, update memory.
    Returns the updated memory dict.
    """
    sampled = random.sample(urls, min(sample_size, len(urls)))
    logger.info(f"[explore] Epoch {mem['epoch']+1} — sampling {len(sampled)} URLs")

    for url in sampled:
        logger.info(f"[explore] URL: {url}")
        html, status = fetch_page(url)
        if status != 200 or not html:
            logger.warning(f"[explore] Could not fetch {url}, skipping")
            mem = add_failed_site(mem, url)
            time.sleep(delay)
            continue

        page_text = extract_text(html, max_chars=6000)
        memory_block = format_memory_for_prompt(mem)

        prompt = EXPLORATION_PROMPT.format(
            memory_block=memory_block,
            event_url=url,
            page_text=page_text,
        )

        logger.info(f"[explore] Calling model for exploration...")
        raw_response = call_model(model, prompt)

        if not raw_response:
            logger.warning(f"[explore] Empty model response for {url}")
            time.sleep(delay)
            continue

        parsed = parse_json_from_response(raw_response)
        if not isinstance(parsed, list):
            logger.warning(f"[explore] Could not parse learning array from model response")
            time.sleep(delay)
            continue

        for learning in parsed:
            if not isinstance(learning, dict):
                continue
            approach = learning.get("strategy", "")
            score = float(learning.get("score", 0))
            fields = learning.get("fields_found", [])
            notes = learning.get("notes", "")
            templates = learning.get("recommended_search_templates", [])

            if approach:
                mem = add_strategy(mem, approach, score, fields, notes, templates)
                logger.info(f"[explore] Strategy recorded: score={score:.2f} | {approach[:60]}")

        time.sleep(delay)

    mem["epoch"] = mem.get("epoch", 0) + 1
    save_memory(mem)
    return mem


# ── Exploitation phase ────────────────────────────────────────────────────────────

def exploitation_run(
    model: str,
    urls: list[str],
    delay: float,
    mem: dict,
    categories: list[str],
) -> list[dict]:
    """
    Extract events from all URLs using best strategies from memory.
    Returns a flat list of validated event dicts.
    """
    all_events: list[dict] = []
    memory_block = format_memory_for_prompt(mem)
    top_templates = mem.get("best_search_templates", [])[:5]

    for i, url in enumerate(urls):
        logger.info(f"[exploit] [{i+1}/{len(urls)}] {url}")
        html, status = fetch_page(url)
        page_text = extract_text(html, max_chars=5000) if (status == 200 and html) else ""

        # Do supplementary web searches using best templates
        event_name_guess = _guess_event_name(url)
        search_text = ""
        if top_templates and event_name_guess:
            queries = [t.format(event_name=event_name_guess, year=2025) for t in top_templates[:3]]
        else:
            queries = build_search_queries(event_name_guess or "", templates=["general", "speakers", "tickets"])

        for q in queries[:2]:
            results = web_search(q, num_results=3, delay=delay)
            for r in results:
                search_text += f"\n[{r.get('title','')}] {r.get('body', r.get('href',''))}"
            search_text = search_text[:3000]
            time.sleep(delay)

        prompt = EXPLOITATION_PROMPT.format(
            memory_block=memory_block,
            event_url=url,
            page_text=page_text,
            search_text=search_text,
        )

        raw_response = call_model(model, prompt)
        if not raw_response:
            time.sleep(delay)
            continue

        parsed = parse_json_from_response(raw_response)
        events = parsed if isinstance(parsed, list) else ([parsed] if isinstance(parsed, dict) else [])

        for ev in events:
            if not isinstance(ev, dict) or not ev.get("event_name"):
                continue
            # Enforce category filter
            ev_cat = ev.get("category", "").lower().strip()
            if categories and ev_cat not in [c.lower() for c in categories]:
                ev["category"] = _infer_category(ev, categories)
            # Set source_url if not set by model
            if not ev.get("source_url"):
                ev["source_url"] = url
            all_events.append(ev)
            logger.info(f"[exploit]  ✓ Extracted: {ev['event_name']} | {ev.get('city','')} | {ev.get('date','')}")

        mem["total_events_found"] = mem.get("total_events_found", 0) + len(events)
        save_memory(mem)
        time.sleep(delay)

    return all_events


def _guess_event_name(url: str) -> str:
    """Best-effort event name from URL path segments."""
    from urllib.parse import urlparse
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p and not p.startswith("#")]
    if parts:
        return parts[-1].replace("-", " ").replace("_", " ").title()
    return ""


def _infer_category(ev: dict, valid_categories: list[str]) -> str:
    """Guess category from theme/event_name if model returned wrong value."""
    text = (ev.get("event_name", "") + " " + ev.get("theme", "")).lower()
    if any(w in text for w in ["concert", "music", "festival", "band", "tour"]):
        return "music"
    if any(w in text for w in ["championship", "tournament", "race", "league", "sport"]):
        return "sports"
    if any(w in text for w in ["summit", "conference", "conf", "symposium", "forum"]):
        return "conference"
    if any(w in text for w in ["tech", "devops", "cloud", "ai", "ml", "hack"]):
        return "tech"
    return valid_categories[0] if valid_categories else "conference"


# ── Output helpers ────────────────────────────────────────────────────────────────

def deduplicate(events: list[dict]) -> list[dict]:
    """Remove duplicate events by (event_name, city)."""
    seen: set[tuple] = set()
    unique: list[dict] = []
    for ev in events:
        key = (ev.get("event_name", "").lower().strip(), ev.get("city", "").lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    return unique


def merge_with_existing(new_events: list[dict], csv_path: Path) -> list[dict]:
    """Merge new events with any existing CSV, avoiding duplicates."""
    if not csv_path.exists():
        return new_events
    try:
        existing_df = pd.read_csv(csv_path)
        existing = existing_df.to_dict(orient="records")
        for ev in existing:
            for list_col in ["sponsors", "speakers", "exhibitors"]:
                val = ev.get(list_col, "")
                ev[list_col] = str(val).split("|") if isinstance(val, str) and val else []
        combined = existing + new_events
        return deduplicate(combined)
    except Exception as exc:
        logger.warning(f"[merge] Could not read existing CSV: {exc}")
        return new_events


# ── CLI entry point ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ConfMind Dataset Agent — builds event seed dataset using Gemma4/Ollama")
    p.add_argument("--github-url", required=True, help="GitHub URL listing event links")
    p.add_argument("--model", default="confmind-gemma4", help="Ollama model name")
    p.add_argument("--epochs", type=int, default=3, help="Exploration epochs before exploitation")
    p.add_argument("--sample-size", type=int, default=5, help="URLs sampled per exploration epoch")
    p.add_argument("--categories", default="conference,tech,music,sports", help="Comma-separated category filter")
    p.add_argument("--delay", type=float, default=2.0, help="Seconds between web requests")
    p.add_argument("--output-csv", default=str(_ROOT / "dataset" / "events_2025_2026.csv"))
    p.add_argument("--output-json", default=str(_ROOT / "dataset" / "events_2025_2026.json"))
    p.add_argument("--dry-run", action="store_true", help="Skip writing output files")
    p.add_argument("--no-enrich", action="store_true", help="Skip agent enrichment (parse only, no Ollama calls)")
    p.add_argument("--limit", type=int, default=0, help="Limit total URLs to process (0 = all)")
    p.add_argument("--verbose", action="store_true", help="Debug logging")
    return p.parse_args()


_SCRALY_DOMAINS = {"scraly", "developers-conferences-agenda"}


def _is_scraly_url(url: str) -> bool:
    return any(d in url for d in _SCRALY_DOMAINS)


def main() -> None:
    args = parse_args()
    _setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    categories = [c.strip().lower() for c in args.categories.split(",")]
    output_csv = Path(args.output_csv)
    output_json = Path(args.output_json)

    logger.info(f"=== ConfMind Dataset Agent ===")
    logger.info(f"Model      : {args.model}")
    logger.info(f"GitHub URL : {args.github_url}")
    logger.info(f"Epochs     : {args.epochs}")
    logger.info(f"Categories : {categories}")
    logger.info(f"Delay      : {args.delay}s")

    # 1️⃣  Load persistent memory
    mem = load_memory()
    logger.info(f"Memory loaded (epoch={mem['epoch']}, strategies={len(mem['strategies'])})")

    # 2️⃣  SOURCE DETECTION — scraly vs generic GitHub
    base_events: list[dict] = []
    all_urls: list[str] = []

    if _is_scraly_url(args.github_url):
        # ── SCRALY PATH: parse structured README directly ────────────────────────
        logger.info("\n🔍 Detected scraly/developers-conferences-agenda — using direct parser")
        base_events = fetch_scraly_events()
        logger.info(f"Direct parse extracted {len(base_events)} conferences")
        # Get the conference website URLs for enrichment
        all_urls = get_event_urls(base_events)
        logger.info(f"Will enrich {len(all_urls)} conference URLs for speakers/tickets/sponsors")
    else:
        # ── GENERIC PATH: extract links from GitHub README ───────────────────────
        logger.info("Fetching event URLs from GitHub...")
        all_urls = fetch_github_links(args.github_url)
        if not all_urls:
            logger.error("No event URLs found. Check the GitHub URL and try again.")
            sys.exit(1)
        logger.info(f"Found {len(all_urls)} event URLs")

    # ── Limit URLs if requested ──────────────────────────────────────────────────
    if args.limit > 0:
        logger.info(f"Limiting to first {args.limit} URLs for this run")
        all_urls = all_urls[:args.limit]
        # Also filter base_events to match if they exist
        if base_events:
            url_set = set(all_urls)
            base_events = [ev for ev in base_events if ev.get("source_url") in url_set]


    # 3️⃣  EXPLORATION PHASE (learn best enrichment strategies)
    if args.epochs > 0 and not args.no_enrich:
        logger.info(f"\n{'='*50}")
        logger.info(f"EXPLORATION PHASE: {args.epochs} epoch(s), {args.sample_size} URLs/epoch")
        logger.info(f"{'='*50}")
        for epoch_num in range(args.epochs):
            logger.info(f"\n── Epoch {epoch_num + 1}/{args.epochs} ──")
            mem = exploration_epoch(
                model=args.model,
                urls=all_urls,
                sample_size=args.sample_size,
                delay=args.delay,
                mem=mem,
            )
            logger.info(f"Memory updated: {len(mem['strategies'])} strategies, epoch={mem['epoch']}")

        if mem["strategies"]:
            logger.info("\nTop strategies learned:")
            for s in mem["strategies"][:3]:
                logger.info(f"  [{s['score']:.2f}] {s['approach']}")

    # 4️⃣  EXPLOITATION / ENRICHMENT PHASE
    if args.no_enrich:
        logger.info("\n[--no-enrich] Skipping agent enrichment — using parsed data only")
        enriched_events = []
    else:
        logger.info(f"\n{'='*50}")
        logger.info(f"ENRICHMENT PHASE: enriching {len(all_urls)} URLs for speakers/tickets/sponsors")
        logger.info(f"{'='*50}\n")
        enriched_events = exploitation_run(
            model=args.model,
            urls=all_urls,
            delay=args.delay,
            mem=mem,
            categories=categories,
        )
        logger.info(f"\nEnrichment returned {len(enriched_events)} records")

    # 5️⃣  MERGE: base_events (parsed) + enriched_events (agent-found)
    #   For scraly: merge enriched fields back into base_events by source_url
    if base_events and enriched_events:
        enriched_by_url = {ev["source_url"]: ev for ev in enriched_events if ev.get("source_url")}
        for base_ev in base_events:
            url = base_ev.get("source_url", "")
            if url in enriched_by_url:
                enr = enriched_by_url[url]
                # Merge enriched fields into base record (base wins for name/date/city/country)
                for field in ["speakers", "sponsors", "exhibitors",
                               "ticket_price_early", "ticket_price_general", "ticket_price_vip",
                               "estimated_attendance", "venue_name", "venue_capacity", "theme"]:
                    if enr.get(field):
                        base_ev[field] = enr[field]
        all_events = base_events
    elif base_events:
        all_events = base_events
    else:
        all_events = enriched_events

    # 6️⃣  Merge & deduplicate with existing dataset
    all_events = merge_with_existing(all_events, output_csv)
    all_events = deduplicate(all_events)
    logger.info(f"Final dataset: {len(all_events)} unique events")

    # 7️⃣  Save
    if not args.dry_run:
        save_to_csv(all_events, str(output_csv))
        save_to_json(all_events, str(output_json))
        logger.info(f"Saved → {output_csv}")
        logger.info(f"Saved → {output_json}")
    else:
        logger.info("[dry-run] Output not saved.")

    logger.info("\n✅ Dataset agent run complete!")


if __name__ == "__main__":
    main()

