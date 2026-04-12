import asyncio

from backend.memory.postgres_store import save_event
from backend.tools.scraper_tool import scrape_event_page
from scraping.etl_pipeline import save_to_csv, save_to_json
from scraping.scrapegraph_runner import run_smart_scraper_list


def main():
    # Deep Crawler Configuration
    calendar_url = "https://events.linuxfoundation.org/about/calendar/"
    max_deep_scrapes = 3  # Limit for now to avoid massive token usage/time

    records = []

    print(f"--- Deep Scrape Phase 1: Extracting event links from {calendar_url} ---")
    try:
        # Bypass LLM for link extraction to avoid rate limits on Phase 1

        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(calendar_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        urls = []
        # Target common event link patterns
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "events.linuxfoundation.org/" in href and not any(
                x in href for x in ["/about/", "/calendar/", "/news/"]
            ):
                if not href.startswith("http"):
                    # Handle relative paths if any (LF usually uses absolute, but safe to check)
                    href = (
                        f"https://events.linuxfoundation.org{href}"
                        if href.startswith("/")
                        else href
                    )
                urls.append(href)

        # Fallback to LLM if regex fails
        if not urls:
            print("Regex found nothing, trying LLM fallback...")
            event_links = run_smart_scraper_list(calendar_url, "calendar_links")
            for item in event_links:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    # Try common URL keys or any value that looks like a URL
                    val = item.get("url") or next(
                        (v for v in item.values() if isinstance(v, str) and v.startswith("http")),
                        None,
                    )
                    if val:
                        urls.append(val)

        # deduplicate and filter
        urls = sorted(list(set(urls)))
        print(
            f"Found {len(urls)} total event links. Proceeding to deep scrape the first {min(len(urls), max_deep_scrapes)}."
        )

        import time

        print("\n--- Deep Scrape Phase 2: Extracting rich details from individual pages ---")
        for i, url in enumerate(urls[:max_deep_scrapes]):
            print(f"[{i + 1}/{max_deep_scrapes}] Deep scraping {url}...")
            try:
                # Add a larger delay to avoid token-bucket rate limiting
                time.sleep(10)

                # Use the detailed event page scraper which extracts prices, speakers, etc.
                event = scrape_event_page(url)

                # Normalize and save
                records.append(event.model_dump())
                asyncio.run(save_event(event))
                print(f"   ✅ Successfully deep scraped: {event.event_name}")
                print(
                    f"   💰 Prices: Early: {event.ticket_price_early}, General: {event.ticket_price_general}"
                )

            except Exception as e:
                print(f"   ❌ Failed to deep scrape {url}: {e}")

    except Exception as e:
        print(f"❌ Failed to extract calendar links: {e}")
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted! Saving progress...")

    if records:
        save_to_json(records, "dataset/events_2025_2026.json")
        save_to_csv(records, "dataset/events_2025_2026.csv")
        print(f"\nDeep Dataset generated with {len(records)} high-fidelity records.")


if __name__ == "__main__":
    main()
