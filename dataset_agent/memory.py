"""
dataset_agent/memory.py
Persistent learnings store — reads/writes dataset_agent/memory.json.

The memory accumulates across epochs so each new exploration run
builds on what the previous one learned.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_FILE = Path(__file__).parent / "memory.json"

_DEFAULT: dict[str, Any] = {
    "epoch": 0,
    "total_events_found": 0,
    "strategies": [],          # list of strategy dicts, sorted by score desc
    "failed_sites": [],        # domains/URLs that consistently return nothing
    "best_search_templates": [],  # top-performing query templates
    "notes": [],               # free-form takeaways
}


# ── I/O ─────────────────────────────────────────────────────────────────────────

def load_memory() -> dict[str, Any]:
    """Load memory.json, returning defaults if the file doesn't exist yet."""
    if MEMORY_FILE.exists():
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            # Merge with defaults to handle new keys added in later versions
            merged = {**_DEFAULT, **data}
            return merged
        except json.JSONDecodeError as exc:
            logger.warning(f"[memory] Corrupt memory.json, starting fresh: {exc}")
    return _DEFAULT.copy()


def save_memory(mem: dict[str, Any]) -> None:
    """Persist the memory dict to disk."""
    MEMORY_FILE.write_text(
        json.dumps(mem, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug(f"[memory] Saved memory (epoch={mem.get('epoch', '?')}, strategies={len(mem.get('strategies', []))})")


# ── Strategy management ─────────────────────────────────────────────────────────

def add_strategy(
    mem: dict[str, Any],
    approach: str,
    score: float,
    fields_found: list[str],
    notes: str,
    search_templates: list[str] | None = None,
) -> dict[str, Any]:
    """
    Add or update a strategy entry in memory.
    If the same approach already exists, we keep the higher score.
    Strategies are kept sorted by score descending.
    """
    existing = {s["approach"]: s for s in mem["strategies"]}

    if approach in existing:
        prev = existing[approach]
        # Update only if the new score is better
        if score > prev["score"]:
            prev["score"] = score
            prev["fields_found"] = list(set(prev["fields_found"]) | set(fields_found))
            prev["notes"] = notes
    else:
        entry: dict[str, Any] = {
            "approach": approach,
            "score": score,
            "fields_found": fields_found,
            "notes": notes,
        }
        if search_templates:
            entry["search_templates"] = search_templates
        mem["strategies"].append(entry)

    # Keep sorted by score descending
    mem["strategies"].sort(key=lambda s: s["score"], reverse=True)

    # Bubble up best search templates into the top-level list
    if search_templates:
        for t in search_templates:
            if t not in mem["best_search_templates"]:
                mem["best_search_templates"].append(t)

    return mem


def add_failed_site(mem: dict[str, Any], url_or_domain: str) -> dict[str, Any]:
    """Record a site that consistently returns no useful data."""
    from urllib.parse import urlparse
    domain = urlparse(url_or_domain).netloc or url_or_domain
    if domain not in mem["failed_sites"]:
        mem["failed_sites"].append(domain)
    return mem


def add_note(mem: dict[str, Any], note: str) -> dict[str, Any]:
    """Append a free-form learning note."""
    if note not in mem["notes"]:
        mem["notes"].append(note)
    return mem


def get_top_strategies(mem: dict[str, Any], n: int = 5) -> list[dict[str, Any]]:
    """Return the top-n strategies sorted by score."""
    return mem["strategies"][:n]


def format_memory_for_prompt(mem: dict[str, Any]) -> str:
    """
    Render the memory into a compact text block to inject into the LLM prompt.
    Keeps tokens low by only including the most useful info.
    """
    top = get_top_strategies(mem, n=5)
    lines: list[str] = [
        f"=== ACCUMULATED MEMORY (Epoch {mem['epoch']}) ===",
        f"Total events collected so far: {mem['total_events_found']}",
        "",
        "TOP STRATEGIES (by success score):",
    ]
    for i, s in enumerate(top, 1):
        lines.append(f"{i}. [{s['score']:.2f}] {s['approach']}")
        lines.append(f"   Fields found: {', '.join(s['fields_found'])}")
        lines.append(f"   Notes: {s['notes']}")

    if mem["best_search_templates"]:
        lines.append("")
        lines.append("BEST SEARCH TEMPLATES:")
        for t in mem["best_search_templates"][:8]:
            lines.append(f"  - {t}")

    if mem["failed_sites"]:
        lines.append("")
        lines.append("SITES TO AVOID (consistently empty):")
        lines.append("  " + ", ".join(mem["failed_sites"][:10]))

    if mem["notes"]:
        lines.append("")
        lines.append("NOTES:")
        for note in mem["notes"][-5:]:   # last 5 notes
            lines.append(f"  - {note}")

    lines.append("=== END OF MEMORY ===")
    return "\n".join(lines)
