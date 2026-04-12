import asyncio

from backend.memory.postgres_store import save_event
from scraping.etl_pipeline import normalize_event, save_to_csv, save_to_json
from scraping.scrapegraph_runner import run_smart_scraper, run_smart_scraper_list


def main():
    target_urls = [
        ("https://events.linuxfoundation.org/about/calendar/", "generic"),
    ]

    records = []

    for url, source in target_urls:
        print(f"Scraping {url}...")
        try:
            # For "generic" calendar listings, we expect an array of events
            if source == "generic":
                raw_events = run_smart_scraper_list(url, source)
                if not isinstance(raw_events, list):
                    raw_events = [raw_events]
            else:
                raw_events = [run_smart_scraper(url, source)]

            print(f"Found {len(raw_events)} events on the page.")

            for raw_data in raw_events:
                # Normalize and save each individually
                event = normalize_event(raw_data)
                records.append(event.model_dump())
                asyncio.run(save_event(event))
                print(f"✅ Saved event: {event.event_name}")

        except Exception as e:
            print(f"❌ Failed to scrape {url}: {e}")

    if records:
        save_to_json(records, "dataset/events_2025_2026.json")
        save_to_csv(records, "dataset/events_2025_2026.csv")
        print(f"\nDataset generated with {len(records)} records.")


if __name__ == "__main__":
    main()
