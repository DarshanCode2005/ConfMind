# Pricing Agent Implementation Notes

Date: 2026-04-11

## Scope Completed

Implemented Pricing & Footfall functionality and tests for:
- `backend/agents/pricing_agent.py`
- `tests/test_pricing_agent.py`

## What Was Added

### 1) New agent: `PricingAgent`

Key behavior:
- Uses historical data from `dataset/events_2025_2026.csv`.
- Loads a pre-trained attendance model from `ATTENDANCE_MODEL_PATH` if available.
- If no saved model is present, trains `AttendancePredictor` from dataset.
- Predicts attendance using:
  - event category
  - derived general ticket price
  - venue city (fallback: geography)
  - venue capacity (fallback: audience size)
- Generates 3 tiers from model utilities:
  - Early Bird
  - General
  - VIP
- Computes break-even price and conversion rates per tier.
- Writes outputs to state:
  - `state["pricing"]` -> `list[TicketTierSchema]`
  - `state["metadata"]["pricing_summary"]` -> structured summary

`pricing_summary` contains:
- `predicted_attendance`
- `optimal_ticket_pricing`:
  - `early_bird`
  - `general`
  - `vip`
- `break_even_price`
- `city_used`
- `size_hint`
- `total_est_revenue`
- `conversion_rates` (per tier)

Error handling:
- Any exception is captured and appended as `pricing_agent: <error>` in `state["errors"]`.

### 2) New tests: `test_pricing_agent.py`

Added two tests:
- `test_pricing_agent_sets_tiers_and_summary`
  - Mocks predictor + CSV read
  - Verifies 3 tiers are written
  - Verifies summary keys and values (attendance, break-even, conversion rates, optimal pricing)
  - Verifies venue city/capacity are used for prediction input
- `test_pricing_agent_logs_errors`
  - Forces predictor init failure
  - Verifies agent logs error and keeps pricing empty

## Verification Performed

Executed in project virtual environment:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_pricing_agent.py tests/test_pricing_model.py -v
```

Result:
- 16 passed
- Includes newly added pricing-agent tests and existing pricing-model regression tests.

## Notes

- This implementation is deterministic and model-driven; it does not call external scraper APIs.
- Agent is compatible with existing orchestrator wiring (`pricing_agent` node already present).
