import asyncio

from backend.memory.postgres_store import save_event
from backend.tools.scraper_tool import scrape_event_page
from scraping.etl_pipeline import save_to_csv, save_to_json


def main():
    # Deep Crawler Configuration
    calendar_url = "https://events.linuxfoundation.org/about/calendar/"
    max_deep_scrapes = 58  # Limit for now to avoid massive token usage/time

    records = []

    print(f"--- Deep Scrape Phase 1: Extracting event links from {calendar_url} ---")
    try:
        # 1. Fast, zero-token link extraction via BS4
        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(calendar_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "events.linuxfoundation.org/" in href and not any(
                x in href for x in ["/about/", "/calendar/", "/news/"]
            ):
                if not href.startswith("http"):
                    href = f"https://events.linuxfoundation.org{href}"
                urls.append(href)

        urls = sorted(list(set(urls)))
        print(
            f"Found {len(urls)} total event links. Proceeding to deep scrape the first {min(len(urls), max_deep_scrapes)}."
        )

        import time

        print(
            "\n--- Deep Scrape Phase 2: Extracting rich details from individual pages (Powered by GROQ) ---"
        )
        for i, url in enumerate(urls[:max_deep_scrapes]):
            print(f"[{i + 1}/{max_deep_scrapes}] Deep scraping {url}...")
            try:
                # Add a small delay for good citizenship, even if Groq is fast
                time.sleep(1)

                # Use the detailed event page scraper which extracts prices, speakers, etc.
                event = scrape_event_page(url)

                # Save and persist
                records.append(event.model_dump())
                asyncio.run(save_event(event))
                print(f"   ✅ Successfully deep scraped: {event.event_name}")
                print(
                    f"   💰 Prices: Early: {event.ticket_price_early}, General: {event.ticket_price_general}, VIP: {event.ticket_price_vip}"
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
