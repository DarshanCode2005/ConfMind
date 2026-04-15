"""
dataset_agent/scraly_parser.py

Specialized parser for: https://github.com/scraly/developers-conferences-agenda

This repo has a beautifully structured markdown format — NO LLM needed for
initial extraction. Every entry follows:

    * DD[-DD]: [Conference Name](url) - City[, State] (Country) [optional CFP badge]

This parser:
  1. Fetches the raw README directly
  2. Extracts all conferences via regex (date, name, url, city, country)
  3. Returns a list of partial EventSchema dicts (no speakers/tickets yet)
  4. Those partial records are then passed to agent.py for enrichment

Usage (standalone):
    python scraly_parser.py --output dataset/events_2025_2026.csv

Usage (from agent.py):
    from dataset_agent.scraly_parser import fetch_scraly_events, SCRALY_URL
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SCRALY_URL = "https://github.com/scraly/developers-conferences-agenda"
SCRALY_RAW_README = (
    "https://raw.githubusercontent.com/scraly/developers-conferences-agenda/main/README.md"
)

# ── Regex patterns ────────────────────────────────────────────────────────────────
# Matches: * 5-6: [Name](url) - City, State (Country)
# Also handles: * 5: [...] and multi-day like * 5-6-7:
_ENTRY_RE = re.compile(
    r"^\*\s+"
    r"(?P<day_range>[\d][\d\-]*)"       # e.g. "5", "5-6", "14-17"
    r":\s+"
    r"\[(?P<name>[^\]]+)\]"              # [Conference Name]
    r"\((?P<url>[^)]+)\)"               # (url)
    r"\s+-\s+"
    r"(?P<location>.+?)$",              # City (Country) or City, State (Country)
    re.MULTILINE,
)

# Matches: ### January  or  ## 2026
_MONTH_HEADER_RE = re.compile(r"^###\s+(?P<month>\w+)\s*$", re.MULTILINE)
_YEAR_HEADER_RE  = re.compile(r"^##\s+(?P<year>\d{4})\s*$", re.MULTILINE)

# Country code lookup (standardize to ISO alpha-2)
_COUNTRY_ALIASES: dict[str, str] = {
    "USA": "US", "United States": "US", "UK": "GB", "United Kingdom": "GB",
    "France": "FR", "Germany": "DE", "Netherlands": "NL", "India": "IN",
    "Canada": "CA", "Australia": "AU", "Spain": "ES", "Italy": "IT",
    "Japan": "JP", "Brazil": "BR", "Switzerland": "CH", "Belgium": "BE",
    "Poland": "PL", "Sweden": "SE", "Norway": "NO", "Portugal": "PT",
    "Austria": "AT", "Denmark": "DK", "Finland": "FI", "Singapore": "SG",
    "China": "CN", "South Korea": "KR", "Korea": "KR", "Taiwan": "TW",
    "Mexico": "MX", "Argentina": "AR", "Colombia": "CO", "Chile": "CL",
    "South Africa": "ZA", "Egypt": "EG", "UAE": "AE", "Israel": "IL",
    "Turkey": "TR", "Greece": "GR", "Hungary": "HU", "Romania": "RO",
    "Czech Republic": "CZ", "Czechia": "CZ", "Slovakia": "SK",
    "Croatia": "HR", "Ukraine": "UA", "Russia": "RU",
    "Indonesia": "ID", "Malaysia": "MY", "Thailand": "TH",
    "Vietnam": "VN", "Philippines": "PH", "Nepal": "NP", "Pakistan": "PK",
    "Bangladesh": "BD", "Sri Lanka": "LK",
    "Ireland": "IE", "Iceland": "IS", "Luxembourg": "LU",
    "Online": "ONLINE",
}

_MONTH_NUMS: dict[str, str] = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def _normalize_country(raw: str) -> str:
    """Normalize country name to ISO alpha-2 or return as-is if unknown."""
    raw = raw.strip().strip("()")
    return _COUNTRY_ALIASES.get(raw, raw[:2].upper() if len(raw) > 2 else raw.upper())


def _parse_location(loc_str: str) -> tuple[str, str]:
    """
    Parse 'City, State (Country)' or 'City (Country)' or 'Online' into (city, country).
    Returns ("Online", "ONLINE") for remote events.
    """
    loc_str = loc_str.strip()

    # Strip trailing CFP badge HTML like <a href=...>
    loc_str = re.sub(r"<a\s.*", "", loc_str).strip()

    # Handle fully online events
    if loc_str.lower() in ("online", " online", "remote"):
        return "Online", "ONLINE"
    if re.match(r"^online\s*$", loc_str.strip(), re.IGNORECASE):
        return "Online", "ONLINE"

    # Extract country from parentheses at end: "Berlin (Germany)"
    country_match = re.search(r"\(([^)]+)\)\s*$", loc_str)
    country = ""
    if country_match:
        country = _normalize_country(country_match.group(1))
        loc_str = loc_str[: country_match.start()].strip().rstrip(",").strip()
    
    # loc_str is now "City" or "City, State"
    # Take just the city (before any comma)
    city = loc_str.split(",")[0].strip()
    return city, country


def _make_date(year: int, month_name: str, day_range: str) -> str:
    """
    Convert year + month name + day_range to ISO date of the first day.
    day_range examples: "5", "5-6", "14-17", "31-1" (across months — use first day only)
    """
    month_num = _MONTH_NUMS.get(month_name, "01")
    first_day = day_range.split("-")[0].zfill(2)
    return f"{year}-{month_num}-{first_day}"


def fetch_raw_readme(url: str = SCRALY_RAW_README) -> str:
    """Fetch the raw README markdown text."""
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "ConfMind-Agent/1.0"})
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.error(f"[scraly_parser] Failed to fetch README: {exc}")
        return ""


def parse_conferences(markdown: str) -> list[dict]:
    """
    Parse the full README markdown into a list of partial event dicts.
    Fields populated: event_name, date, city, country, category, source_url.
    Fields left empty (for agent enrichment): speakers, sponsors, ticket_prices, etc.
    """
    events: list[dict] = []
    current_year = 2026
    current_month = "January"

    # Split into lines to track year/month context
    pos = 0
    for line in markdown.split("\n"):
        # Track current year
        ym = _YEAR_HEADER_RE.match(line)
        if ym:
            current_year = int(ym.group("year"))
            continue

        # Track current month
        mm = _MONTH_HEADER_RE.match(line)
        if mm:
            current_month = mm.group("month")
            continue

        # Match conference entries
        em = _ENTRY_RE.match(line)
        if not em:
            continue

        name = em.group("name").strip()
        url  = em.group("url").strip()
        loc  = em.group("location").strip()
        day_range = em.group("day_range").strip()

        city, country = _parse_location(loc)
        date_str = _make_date(current_year, current_month, day_range)

        # Classify category — this repo is primarily dev/tech conferences
        category = _classify_category(name)

        events.append({
            "event_name": name,
            "date": date_str,
            "city": city,
            "country": country,
            "category": category,
            "theme": "",
            "sponsors": [],
            "speakers": [],
            "exhibitors": [],
            "ticket_price_early": 0.0,
            "ticket_price_general": 0.0,
            "ticket_price_vip": 0.0,
            "estimated_attendance": 0,
            "venue_name": "",
            "venue_capacity": 0,
            "source_url": url,
        })

    logger.info(f"[scraly_parser] Parsed {len(events)} conferences from README")
    return events


def _classify_category(name: str) -> str:
    """Heuristic category classifier based on conference name."""
    nl = name.lower()
    if any(w in nl for w in ["music", "concert", "festival", "band", "sound"]):
        return "music"
    if any(w in nl for w in ["sport", "race", "cup", "championship", "marathon", "olympic"]):
        return "sports"
    if any(w in nl for w in ["devops", "cloud", "kubernetes", "docker", "linux", "open source",
                               "python", "java", "js", "javascript", "golang", "rust", "scala",
                               "data", "ai ", "ml ", "machine learning", "deep learning",
                               "security", "infosec", "hack", "ctf", "wordpress", "drupal",
                               "php", "ruby", ".net", "swift", "android", "ios", "mobile",
                               "frontend", "backend", "fullstack", "api", "microservice"]):
        return "tech"
    # Default: conference
    return "conference"


def fetch_scraly_events() -> list[dict]:
    """
    Main public API: fetch and parse the scraly conferences agenda.
    Returns list of partial event dicts ready for enrichment or direct saving.
    """
    logger.info(f"[scraly_parser] Fetching {SCRALY_RAW_README}")
    markdown = fetch_raw_readme()
    if not markdown:
        return []
    return parse_conferences(markdown)


def get_event_urls(events: list[dict]) -> list[str]:
    """Extract unique source URLs from parsed events (for agent enrichment)."""
    seen: set[str] = set()
    urls: list[str] = []
    for ev in events:
        u = ev.get("source_url", "")
        if u and u not in seen and not u.startswith("http") is False:
            seen.add(u)
            urls.append(u)
    return urls


# ── Standalone CLI ────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    p = argparse.ArgumentParser(description="Parse scraly/developers-conferences-agenda into CSV/JSON")
    p.add_argument("--output-csv",  default="dataset/events_2025_2026.csv")
    p.add_argument("--output-json", default="dataset/events_2025_2026.json")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    sys.path.insert(0, str(Path(__file__).parent.parent))

    events = fetch_scraly_events()
    if not events:
        print("No events extracted — check network or README format.")
        sys.exit(1)

    print(f"\nExtracted {len(events)} conferences")
    print(f"Sample:\n  {events[0]}")

    if not args.dry_run:
        try:
            from scraping.etl_pipeline import save_to_csv, save_to_json
        except ImportError:
            import csv, json
            def save_to_csv(recs, path):  # type: ignore
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
                    w.writeheader()
                    for r in recs:
                        w.writerow({k: ("|".join(v) if isinstance(v, list) else v) for k, v in r.items()})
            def save_to_json(recs, path):  # type: ignore
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")

        save_to_csv(events, args.output_csv)
        save_to_json(events, args.output_json)
        print(f"Saved → {args.output_csv}")
        print(f"Saved → {args.output_json}")
    else:
        print("[dry-run] Output not saved.")


if __name__ == "__main__":
    main()
