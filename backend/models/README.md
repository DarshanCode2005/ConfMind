# Models — Internal Documentation

---

## `schemas.py` — Shared Pydantic v2 Models

Single source of truth for all data types flowing through ConfMind.  **Import from here only — never define duplicate models in tool files.**

### Model Reference

#### `SerperResult`
Output of `serper_tool.search_web()`.

| Field | Type | Notes |
|---|---|---|
| `title` | `str` | Page title |
| `url` | `str` | Full URL |
| `snippet` | `str` | Search result snippet |
| `position` | `int` | Rank (≥ 1) |

#### `LinkedInProfile`
Output of `linkedin_tool.get_profile()`.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Full name |
| `headline` | `str` | LinkedIn headline |
| `followers` | `int` | Follower count (≥ 0) |
| `connections` | `int` | Connection count (≥ 0) |
| `recent_posts_count` | `int` | Approximate recent post count |
| `linkedin_url` | `str` | Profile URL |

#### `SponsorSchema`
Company sponsor record.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `name` | `str` | required | Company name |
| `website` | `str` | optional | Company URL |
| `industry` | `str` | optional | e.g. "AI", "Cloud" |
| `geo` | `str` | optional | Country or region |
| `tier` | `str` | `{"Gold","Silver","Bronze","General"}` | Sponsorship tier |
| `relevance_score` | `float` | 0.0–10.0 | Agent-computed relevance |

#### `SpeakerSchema`

| Field | Type | Validation | Notes |
|---|---|---|---|
| `name` | `str` | required | |
| `bio` | `str` | optional | Short biography |
| `linkedin_url` | `str` | optional | Used for enrichment |
| `topic` | `str` | optional | Keynote / talk subject |
| `region` | `str` | optional | Country or city |
| `influence_score` | `float` | 0.0–10.0 | Set by `linkedin_tool.enrich_speakers` |
| `speaking_experience` | `int` | ≥ 0 | Number of past talks |

#### `VenueSchema`

| Field | Type | Validation | Notes |
|---|---|---|---|
| `name` | `str` | required | |
| `city` | `str` | required | |
| `country` | `str` | optional | ISO alpha-2 preferred |
| `capacity` | `int \| None` | ≥ 1 if set | Max attendees |
| `price_range` | `str` | optional | e.g. "$10,000-$20,000/day" |
| `past_events` | `list[str]` | optional | Event names held here |
| `score` | `float` | 0.0–10.0 | Agent-computed fit score |
| `source_url` | `str` | optional | Where data was scraped from |

#### `ExhibitorSchema`

| Field | Type | Validation | Notes |
|---|---|---|---|
| `name` | `str` | required | |
| `cluster` | `str` | optional | "startup" / "enterprise" / "tools" / "individual" |
| `relevance` | `float` | 0.0–10.0 | Topic relevance score |
| `website` | `str` | optional | |

#### `TicketTierSchema`

| Field | Type | Validation | Notes |
|---|---|---|---|
| `name` | `str` | `{"Early Bird","General","VIP"}` | Tier label |
| `price` | `float` | ≥ 0 | USD |
| `est_sales` | `int` | ≥ 0 | Predicted tickets sold |
| `revenue` | `float` | ≥ 0 | `price * est_sales` |

#### `CommunitySchema`

| Field | Type | Notes |
|---|---|---|
| `platform` | `str` | "Discord" / "Slack" / "Reddit" / "Telegram" |
| `name` | `str` | Community display name |
| `size` | `int` | Member count (≥ 0) |
| `niche` | `str` | Topic / domain |
| `invite_url` | `str` | Join link |

#### `EventSchema`
Full event record — output of ETL pipeline, stored in the dataset.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `event_name` | `str` | required | |
| `date` | `str` | optional | ISO 8601 "YYYY-MM-DD" |
| `city` | `str` | optional | |
| `country` | `str` | optional | ISO alpha-2 |
| `category` | `str` | optional | "AI", "Web3", … |
| `theme` | `str` | optional | |
| `sponsors` | `list[str]` | default `[]` | Company names |
| `speakers` | `list[str]` | default `[]` | Person names |
| `exhibitors` | `list[str]` | default `[]` | Company names |
| `ticket_price_early` | `float` | ≥ 0 | USD |
| `ticket_price_general` | `float` | ≥ 0 | USD |
| `ticket_price_vip` | `float` | ≥ 0 | USD |
| `estimated_attendance` | `int` | ≥ 0 | |
| `venue_name` | `str` | optional | |
| `venue_capacity` | `int \| None` | ≥ 1 if set | |
| `source_url` | `str` | optional | Where data originated |

---

## `pricing_model.py` — `AttendancePredictor`

scikit-learn `LinearRegression` wrapped with encoding helpers and tier generation.

### Training Data Requirements

DataFrame must have these columns:

| Column | Type | Notes |
|---|---|---|
| `category` | `str` | Event type (label-encoded) |
| `ticket_price_general` | `float` | USD |
| `city` | `str` | Venue city (label-encoded) |
| `estimated_attendance` | `int` | Target variable |
| `venue_capacity` | `int` | Optional; defaults to 500 if missing |

Minimum viable dataset: ~20 rows (used in tests). Production target: 100+ rows.

### Tier Generation Formula

Given `base_price` (General price) and `total_attendance`:

| Tier | Price multiplier | Attendance split |
|---|---|---|
| Early Bird | 0.70× base | 40% of total |
| General | 1.00× base | 45% of total |
| VIP | 2.50× base | 15% of total |

### Unseen Label Handling

If `predict()` is called with an event type or city not seen during training, `_encode_unseen` falls back to the median label index — preventing KeyErrors while producing a reasonable prediction.

### Persistence

`save(path)` → pickle file.  `load(path)` → new `AttendancePredictor` instance with trained state restored.

> [!NOTE]
> The pickle file embeds the trained `LinearRegression` and both `LabelEncoder` instances.  Re-training is required if the event category or city vocabulary changes significantly.
