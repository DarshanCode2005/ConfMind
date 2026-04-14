"""
dataset_agent/tools.py
Web search, GitHub link extraction, and page fetching utilities.
No LangChain dependency — pure requests + BeautifulSoup.
"""
from __future__ import annotations

import re
import time
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

logger = logging.getLogger(__name__)

# ── HTTP session with sensible defaults ─────────────────────────────────────────
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})
_TIMEOUT = 20  # seconds


def fetch_page(url: str, retries: int = 3, backoff: float = 2.0) -> tuple[str, int]:
    """
    Fetch a web page with retries and exponential backoff.

    Returns:
        (html_text, status_code)  — html_text is "" on failure
    """
    for attempt in range(retries):
        try:
            resp = _SESSION.get(url, timeout=_TIMEOUT)
            return resp.text, resp.status_code
        except requests.RequestException as exc:
            wait = backoff ** attempt
            logger.warning(f"[fetch_page] attempt {attempt+1} failed for {url}: {exc}. Retrying in {wait}s")
            time.sleep(wait)
    return "", 0


def extract_text(html: str, max_chars: int = 12_000) -> str:
    """
    Strip HTML to clean readable text, limited to max_chars to stay within context.
    Preserves paragraph structure for better LLM comprehension.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style/nav noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "li", "h1", "h2", "h3"])]
    text = "\n".join(p for p in paragraphs if len(p) > 20)
    return text[:max_chars]


# ── GitHub awesome-list link extractor ─────────────────────────────────────────

def fetch_github_links(github_url: str) -> list[str]:
    """
    Given a GitHub URL (repo page or raw README), extract all external http(s) links.
    Handles:
      - github.com/user/repo  → fetches raw README.md
      - raw.githubusercontent.com/... → fetches directly
      - Any page with markdown/HTML links
    """
    # Convert blob/tree GitHub URLs to raw content URLs for READMEs
    raw_url = _github_to_raw(github_url)
    html, status = fetch_page(raw_url)
    if status == 0 or not html:
        logger.error(f"[fetch_github_links] Could not fetch {raw_url}")
        return []

    links: list[str] = []

    # Markdown links: [text](url)
    md_links = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', html)
    links.extend(md_links)

    # HTML anchor tags (if the response is HTML)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if href.startswith("http"):
            links.append(href)
        elif href.startswith("/"):
            # Relative GitHub links — skip (they're internal)
            pass

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for link in links:
        link = link.strip().rstrip(")")
        if link not in seen and _is_event_url(link):
            seen.add(link)
            unique.append(link)

    logger.info(f"[fetch_github_links] Found {len(unique)} event URLs from {github_url}")
    return unique


def _github_to_raw(url: str) -> str:
    """Convert github.com repo URL to raw README content URL."""
    # Already raw
    if "raw.githubusercontent.com" in url:
        return url
    # github.com/user/repo → raw README
    match = re.match(r'https?://github\.com/([^/]+/[^/]+)/?$', url)
    if match:
        slug = match.group(1)
        return f"https://raw.githubusercontent.com/{slug}/main/README.md"
    # github.com/user/repo/blob/main/file.md
    url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


def _is_event_url(url: str) -> bool:
    """
    Heuristic filter — skip GitHub-internal, CDN, and obviously non-event URLs.
    """
    skip_domains = {
        "github.com", "shields.io", "travis-ci.org", "badge.fury.io",
        "coveralls.io", "img.shields.io", "google.com/search",
    }
    parsed = urlparse(url)
    domain = parsed.netloc.lstrip("www.")
    return domain not in skip_domains and bool(parsed.scheme)


# ── DuckDuckGo web search ────────────────────────────────────────────────────────

def web_search(query: str, num_results: int = 5, delay: float = 1.5) -> list[dict]:
    """
    Search the web via DuckDuckGo (no API key required).

    Returns:
        list of {title, href, body} dicts
    """
    time.sleep(delay)  # polite delay between searches
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        return results
    except Exception as exc:
        logger.warning(f"[web_search] DuckDuckGo search failed for '{query}': {exc}")
        return []


def search_and_fetch(query: str, num_results: int = 3, delay: float = 1.5) -> list[dict]:
    """
    Search DuckDuckGo, then fetch and extract text from each result page.

    Returns:
        list of {url, title, text} dicts
    """
    results = web_search(query, num_results=num_results, delay=delay)
    pages: list[dict] = []
    for r in results:
        url = r.get("href", "")
        if not url:
            continue
        html, status = fetch_page(url)
        if status == 200 and html:
            text = extract_text(html)
            pages.append({"url": url, "title": r.get("title", ""), "text": text})
        time.sleep(delay)
    return pages


# ── Search template helpers ──────────────────────────────────────────────────────

SEARCH_TEMPLATES = {
    "general": "{event_name} {year} conference official site",
    "speakers": "{event_name} {year} speakers list schedule",
    "tickets": "{event_name} {year} tickets registration price",
    "sponsors": "{event_name} {year} sponsors exhibitors",
    "hub": "{event_name} {year} site:sessionize.com OR site:eventbrite.com OR site:luma.com OR site:cvent.com",
    "canonical": "{event_name} {year} official schedule json csv dataset",
    "sessionize": "{event_name} site:sessionize.com",
    "eventbrite": "{event_name} site:eventbrite.com",
    "luma": "{event_name} site:lu.ma",
}


def build_search_queries(event_name: str, year: int = 2025, templates: Optional[list[str]] = None) -> list[str]:
    """
    Build a list of search queries for a given event name using SEARCH_TEMPLATES.
    """
    keys = templates or list(SEARCH_TEMPLATES.keys())
    return [
        SEARCH_TEMPLATES[k].format(event_name=event_name, year=year)
        for k in keys
        if k in SEARCH_TEMPLATES
    ]
