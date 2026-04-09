# Dataset Documentation

## Schema

Each row in `events_2025_2026.csv` (and object in `events_2025_2026.json`) matches the `EventSchema` Pydantic model in `backend/models/schemas.py`.

| Column | Type | Notes |
|---|---|---|
| `event_name` | string | required |
| `date` | string | ISO 8601 "YYYY-MM-DD" |
| `city` | string | Venue city |
| `country` | string | ISO 3166-1 alpha-2 (e.g. "IN", "US") |
| `category` | string | "AI" / "Web3" / "ClimateTech" / "Music" / "Sports" |
| `theme` | string | Short event tagline |
| `sponsors` | pipe-separated string (CSV) / list (JSON) | Company names |
| `speakers` | pipe-separated string (CSV) / list (JSON) | Person names |
| `exhibitors` | pipe-separated string (CSV) / list (JSON) | Company names |
| `ticket_price_early` | float | USD |
| `ticket_price_general` | float | USD |
| `ticket_price_vip` | float | USD |
| `estimated_attendance` | integer | — |
| `venue_name` | string | — |
| `venue_capacity` | integer | Max attendees |
| `source_url` | string | URL where data was scraped from |

## Target

- **Minimum**: 100 rows across at least 3 categories and 4 geographies
- **Stretch**: 200 rows

## Sources & Collection Method

All data scraped using `scraping/scrapegraph_runner.py` with the prompts in `scraping/prompts.py`.

| Source | Method | Script |
|---|---|---|
| Eventbrite | `run_smart_scraper(url, "eventbrite")` | `scraping/collect_dataset.py` |
| Luma | `run_smart_scraper(url, "luma")` | `scraping/collect_dataset.py` |
| Cvent | `run_smart_scraper(url, "cvent")` | `scraping/collect_dataset.py` |
| Sessionize | `run_smart_scraper(url, "sessionize")` | `scraping/collect_dataset.py` |
| Eventlocations | `run_smart_scraper(url, "eventlocations")` | `scraping/collect_dataset.py` |

After scraping, all records are normalised via `scraping/etl_pipeline.normalize_event(raw)` which handles:
- Date format → ISO 8601
- Ticket prices → USD (with approximate FX conversion)
- Country names → ISO alpha-2

## Adding Rows Manually

1. Copy the CSV header row and fill in values
2. For list fields (`sponsors`, `speakers`, `exhibitors`), separate values with `|` in CSV
3. Run `python -c "import pandas as pd; df = pd.read_csv('dataset/events_2025_2026.csv'); print(df.dtypes)"` to verify no type errors
