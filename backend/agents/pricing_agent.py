"""
pricing_agent.py — Pricing & Footfall Agent for ConfMind.

System Prompt:
  "You are the Pricing & Footfall Agent. Use ONLY historical interpolation
   + PredictHQ Features. No ML models."

Sequential (no loop):
  • Step 1: Historical pairs from past_events.
  • Step 2: PredictHQ Features API (target geography + next 6 months)
            → demand_ratio.
  • Step 3: Interpolation using historical price-attendance pairs.
  • Step 4: Tier derivation (p25/p50/p75).
  • Step 5: Monte Carlo (200 iterations, Normal distribution).
  • Step 6: Revenue projection.
  • Step 7: Break-even analysis (use defaults if missing).
  • Step 8: Build exact output dict.

Output exact dict structure with tiers, Monte Carlo results, and revenue.
"""

from __future__ import annotations

import os
import math
import random
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.models.schemas import AgentState, TicketTierSchema

from .base_agent import BaseAgent

# ── Constants ──────────────────────────────────────────────────────────────────

_MONTE_CARLO_ITERATIONS = 200
_DEFAULT_BASE_PRICE = 150.0
_DEFAULT_ATTENDANCE = 500
# Default cost assumptions for break-even
_DEFAULT_VENUE_COST = 10000.0
_DEFAULT_SPEAKER_COST = 5000.0
_DEFAULT_MARKETING_COST = 3000.0
_DEFAULT_MISC_COST = 2000.0


class PricingAgent(BaseAgent):
    """Predicts attendance and generates ticket pricing using historical
    interpolation + PredictHQ Features. NO ML models per spec.

    Sources:
        1. past_events for historical price-attendance pairs
        2. PredictHQ Features API for demand_ratio
        3. Monte Carlo simulation for confidence intervals

    Output:
        state["pricing"] — list of TicketTierSchema with Monte Carlo backing
        state["metadata"] — pricing_analysis key with full analysis dict
    """

    name: str = "pricing_agent"

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the Pricing & Footfall Agent for ConfMind.\n\n"
                    "CRITICAL RULES:\n"
                    "1. Use ONLY historical interpolation + PredictHQ Features.\n"
                    "2. NO machine learning models — pure statistical methods only.\n"
                    "3. Tier derivation uses percentiles: p25 (Early Bird), "
                    "p50 (General), p75 (VIP).\n"
                    "4. Monte Carlo: 200 iterations, Normal distribution.\n"
                    "5. Revenue = sum(tier_price × estimated_sales) for all tiers.\n"
                    "6. Break-even: use default costs if not available from state.\n"
                    "7. All prices in USD.\n"
                    "8. NEVER hallucinate pricing data.",
                ),
                ("human", "{input}"),
            ]
        )

    # ── Step 1: Historical pairs ──────────────────────────────────────────

    def _extract_historical_pairs(
        self, past_events: list[dict]
    ) -> list[dict[str, Any]]:
        """Extract price-attendance pairs from past_events."""
        pairs = []
        for event in past_events:
            attendance = event.get("attendance_estimate")
            pricing = event.get("pricing", {})

            if not attendance:
                continue

            if isinstance(pricing, dict):
                for tier_name in ["early_bird", "general", "vip"]:
                    price = pricing.get(tier_name)
                    if price and isinstance(price, (int, float)):
                        pairs.append({
                            "attendance": int(attendance),
                            "price": float(price),
                            "tier": tier_name,
                            "event": event.get("name", "unknown"),
                        })

        self._log_info(f"Extracted {len(pairs)} historical price-attendance pairs")
        return pairs

    # ── Step 2: PredictHQ Features API ────────────────────────────────────

    def _fetch_demand_ratio(self, geography: str, category: str) -> float:
        """Fetch demand ratio from PredictHQ Features API.

        POST /v1/features/ with minimum fields:
        phq_attendance_conferences, phq_attendance_sports,
        phq_spend_conferences, phq_rank_public_holidays.
        """
        try:
            from predicthq import Client  # type: ignore[import-untyped]
        except ImportError:
            self._log_info("PredictHQ SDK not installed — using default demand ratio")
            return 1.0

        api_key = os.getenv("PREDICTHQ_API_KEY", "")
        if not api_key:
            self._log_info("PREDICTHQ_API_KEY not set — using default demand ratio")
            return 1.0

        try:
            phq = Client(access_token=api_key)

            # Map category to PHQ attendance feature
            cat_map = {
                "conferences": "phq_attendance_conferences",
                "sports": "phq_attendance_sports",
                "concerts": "phq_attendance_concerts",
                "festivals": "phq_attendance_festivals",
                "expos": "phq_attendance_expos",
            }
            attendance_feature = cat_map.get(category.lower(), "phq_attendance_conferences")

            # Try to get features — use API directly if SDK method unavailable
            import requests
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            payload = {
                "active": {
                    "gte": "2025-01-01",
                    "lte": "2025-12-31",
                },
                "location": {
                    "place_id": geography,
                },
                "phq_attendance_conferences": True,
                "phq_spend_conferences": True,
                "phq_rank_public_holidays": True,
            }

            response = requests.post(
                "https://api.predicthq.com/v1/features/",
                headers=headers,
                json=payload,
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                # Calculate demand ratio from response
                results = data.get("results", [])
                if results:
                    # Simplified demand ratio calculation
                    attendance_sum = sum(
                        r.get("phq_attendance_conferences", {}).get("stats", {}).get("sum", 0)
                        for r in results
                    )
                    if attendance_sum > 0:
                        ratio = min(2.0, attendance_sum / 10000)
                        self._log_info(f"PredictHQ demand ratio: {ratio:.2f}")
                        return ratio

            self._log_info("PredictHQ Features returned no usable data — using default")
            return 1.0

        except Exception as e:
            self._log_info(f"PredictHQ Features failed: {e} — using default demand ratio")
            return 1.0

    # ── Step 3: Interpolation ─────────────────────────────────────────────

    def _interpolate_base_price(
        self, pairs: list[dict], target_attendance: int, demand_ratio: float
    ) -> float:
        """Interpolate base price from historical pairs adjusted by demand."""
        if not pairs:
            return _DEFAULT_BASE_PRICE * demand_ratio

        # Filter to general tier for base price
        general_pairs = [p for p in pairs if p["tier"] == "general"]
        if not general_pairs:
            general_pairs = pairs

        # Sort by attendance difference from target
        general_pairs.sort(key=lambda p: abs(p["attendance"] - target_attendance))

        # Weighted interpolation using closest matches
        weights = []
        prices = []
        for i, p in enumerate(general_pairs[:5]):
            dist = max(1, abs(p["attendance"] - target_attendance))
            weight = 1.0 / dist
            weights.append(weight)
            prices.append(p["price"])

        if weights:
            total_weight = sum(weights)
            base_price = sum(w * p for w, p in zip(weights, prices)) / total_weight
        else:
            base_price = _DEFAULT_BASE_PRICE

        # Apply demand ratio adjustment
        adjusted = base_price * demand_ratio
        self._log_info(f"Interpolated base price: ${base_price:.2f} → adjusted: ${adjusted:.2f}")
        return adjusted

    # ── Step 4: Tier derivation ──────────────────────────────────────────

    def _derive_tiers(self, base_price: float) -> dict[str, float]:
        """Derive tier prices using percentile-based multipliers.

        p25 → Early Bird (cheaper)
        p50 → General (base)
        p75 → VIP (premium)
        """
        return {
            "Early Bird": round(base_price * 0.65, 2),   # p25
            "General": round(base_price, 2),               # p50
            "VIP": round(base_price * 2.5, 2),             # p75
        }

    def _fit_what_if_model(self, tiers: list[TicketTierSchema]) -> dict[str, Any]:
        """Fit a simple linear regression model y = intercept + slope*x.

        x = ticket price, y = estimated sales.
        """
        points = [
            (float(tier.price), float(tier.est_sales))
            for tier in tiers
            if tier.price >= 0 and tier.est_sales >= 0
        ]

        if len(points) < 2:
            return {
                "slope": 0.0,
                "intercept": 0.0,
                "valid": False,
                "sample_count": len(points),
            }

        n = len(points)
        mean_x = sum(p[0] for p in points) / n
        mean_y = sum(p[1] for p in points) / n

        numerator = 0.0
        denominator = 0.0
        for x, y in points:
            dx = x - mean_x
            dy = y - mean_y
            numerator += dx * dy
            denominator += dx * dx

        if denominator == 0:
            return {
                "slope": 0.0,
                "intercept": round(mean_y, 6),
                "valid": False,
                "sample_count": len(points),
            }

        slope = numerator / denominator
        intercept = mean_y - slope * mean_x

        return {
            "slope": round(slope, 6),
            "intercept": round(intercept, 6),
            "valid": math.isfinite(slope) and math.isfinite(intercept),
            "sample_count": len(points),
        }

    # ── Step 5: Monte Carlo ──────────────────────────────────────────────

    def _monte_carlo_simulation(
        self,
        base_attendance: int,
        tier_prices: dict[str, float],
        demand_ratio: float,
    ) -> dict[str, Any]:
        """Run Monte Carlo simulation (200 iters, Normal dist).

        Simulates attendance and revenue with random variation.
        """
        random.seed(42)  # Reproducible results

        # Distribution parameters
        mean_attendance = base_attendance * demand_ratio
        std_attendance = mean_attendance * 0.15  # 15% standard deviation

        # Tier allocation (typical split)
        tier_splits = {
            "Early Bird": 0.30,
            "General": 0.50,
            "VIP": 0.20,
        }

        attendance_results = []
        revenue_results = []

        for _ in range(_MONTE_CARLO_ITERATIONS):
            # Simulate attendance
            sim_attendance = max(50, int(random.gauss(mean_attendance, std_attendance)))
            attendance_results.append(sim_attendance)

            # Calculate revenue for this iteration
            iter_revenue = 0.0
            for tier_name, split in tier_splits.items():
                tier_sales = int(sim_attendance * split)
                tier_price = tier_prices.get(tier_name, 0)
                iter_revenue += tier_sales * tier_price
            revenue_results.append(iter_revenue)

        # Statistics
        attendance_results.sort()
        revenue_results.sort()

        mc_results = {
            "iterations": _MONTE_CARLO_ITERATIONS,
            "attendance": {
                "mean": int(sum(attendance_results) / len(attendance_results)),
                "p10": attendance_results[int(len(attendance_results) * 0.1)],
                "p50": attendance_results[int(len(attendance_results) * 0.5)],
                "p90": attendance_results[int(len(attendance_results) * 0.9)],
                "std_dev": round(
                    math.sqrt(
                        sum((x - sum(attendance_results) / len(attendance_results)) ** 2
                            for x in attendance_results) / len(attendance_results)
                    ), 2
                ),
            },
            "revenue": {
                "mean": round(sum(revenue_results) / len(revenue_results), 2),
                "p10": round(revenue_results[int(len(revenue_results) * 0.1)], 2),
                "p50": round(revenue_results[int(len(revenue_results) * 0.5)], 2),
                "p90": round(revenue_results[int(len(revenue_results) * 0.9)], 2),
            },
        }

        self._log_info(
            f"Monte Carlo: attendance mean={mc_results['attendance']['mean']}, "
            f"revenue mean=${mc_results['revenue']['mean']:.0f}"
        )
        return mc_results

    # ── Step 7: Break-even ────────────────────────────────────────────────

    def _break_even_analysis(
        self,
        tier_prices: dict[str, float],
        budget: float,
    ) -> dict[str, Any]:
        """Calculate break-even attendance needed to cover costs."""
        total_fixed_costs = budget if budget > 0 else (
            _DEFAULT_VENUE_COST + _DEFAULT_SPEAKER_COST
            + _DEFAULT_MARKETING_COST + _DEFAULT_MISC_COST
        )

        # Weighted average ticket price
        tier_weights = {"Early Bird": 0.30, "General": 0.50, "VIP": 0.20}
        avg_price = sum(
            tier_prices.get(name, 0) * weight
            for name, weight in tier_weights.items()
        )

        break_even_attendance = (
            math.ceil(total_fixed_costs / avg_price) if avg_price > 0 else 0
        )

        return {
            "total_fixed_costs": round(total_fixed_costs, 2),
            "avg_ticket_price": round(avg_price, 2),
            "break_even_attendance": break_even_attendance,
        }

    # ── Main run ──────────────────────────────────────────────────────────

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the 8-step pricing pipeline (sequential, no loop)."""
        self._current_pass = 0
        self._log_info("Starting pricing & footfall analysis...")

        try:
            cfg = state["event_config"]
            category = cfg.category
            geography = cfg.geography
            target_audience = cfg.audience_size
            budget = cfg.budget_usd
            past_events = state.get("past_events", [])

            # ── Step 1: Historical pairs ──────────────────────────────────
            with self._pass_context(
                "Step 1: Historical pairs", state,
                f"pricing history for {category}"
            ):
                pairs = self._extract_historical_pairs(past_events)

            # ── Step 2: PredictHQ Features → demand_ratio ─────────────────
            with self._pass_context(
                "Step 2: PredictHQ Features", state,
                f"demand ratio for {geography}"
            ):
                demand_ratio = self._fetch_demand_ratio(geography, category)

            # ── Step 3: Interpolation ─────────────────────────────────────
            with self._pass_context(
                "Step 3: Price interpolation", state,
                f"base price for {target_audience} attendees"
            ):
                base_price = self._interpolate_base_price(pairs, target_audience, demand_ratio)

            # ── Step 4: Tier derivation ───────────────────────────────────
            with self._pass_context(
                "Step 4: Tier derivation", state,
                f"pricing tiers from base ${base_price:.2f}"
            ):
                tier_prices = self._derive_tiers(base_price)

            # ── Step 5: Monte Carlo ───────────────────────────────────────
            with self._pass_context(
                "Step 5: Monte Carlo simulation", state,
                f"Monte Carlo for {target_audience} attendees"
            ):
                mc_results = self._monte_carlo_simulation(
                    target_audience, tier_prices, demand_ratio
                )

            # ── Step 6: Revenue projection ────────────────────────────────
            # Use Monte Carlo p50 for expected attendance
            expected_attendance = mc_results["attendance"]["p50"]
            tier_splits = {"Early Bird": 0.30, "General": 0.50, "VIP": 0.20}

            tiers = []
            for tier_name, split in tier_splits.items():
                est_sales = int(expected_attendance * split)
                price = tier_prices[tier_name]
                revenue = round(est_sales * price, 2)
                tiers.append(TicketTierSchema(
                    name=tier_name,
                    price=price,
                    est_sales=est_sales,
                    revenue=revenue,
                ))

            what_if_model = self._fit_what_if_model(tiers)

            # ── Step 7: Break-even ────────────────────────────────────────
            with self._pass_context(
                "Step 7: Break-even analysis", state,
                f"break-even for budget ${budget:.0f}"
            ):
                break_even = self._break_even_analysis(tier_prices, budget)

            # ── Step 8: Build output ──────────────────────────────────────
            pricing_analysis = {
                "demand_ratio": round(demand_ratio, 4),
                "base_price": round(base_price, 2),
                "tier_prices": tier_prices,
                "monte_carlo": mc_results,
                "break_even": break_even,
                "historical_pairs_count": len(pairs),
                "what_if_model": what_if_model,
            }

            # Write to memory
            docs = [
                f"Pricing: {category} in {geography} | "
                f"Base: ${base_price:.2f} | Demand: {demand_ratio:.2f}"
            ]
            meta = [{"category": category, "geography": geography, "base_price": base_price}]
            self._write_memory(docs, meta, collection="events")

            # Chat Agent Indexing Contract
            run_id = state.get("metadata", {}).get("run_id", "unknown")
            tier_texts = []
            for t in tiers:
                tier_texts.append(f"{t.name} tier is ${t.price} with {t.est_sales} estimated sales.")
            
            pricing_doc = (
                f"Pricing Analysis: {', '.join(tier_texts)} "
                f"Demand ratio is {demand_ratio:.2f}. Base price is ${base_price:.2f}. "
                f"Expected attendance: {expected_attendance}. Break-even attendance: {break_even.get('break_even_attendance')}."
            )
            self.index_to_chroma(
                [pricing_doc], 
                "chat_index", 
                [{"agent": "pricing", "run_id": run_id, "category": category, "geography": geography}]
            )

            self._log_info(
                f"Completed — Base: ${base_price:.2f}, "
                f"Tiers: EB=${tiers[0].price}, G=${tiers[1].price}, VIP=${tiers[2].price}"
            )

            return {
                "pricing": tiers,
                "metadata": {"pricing_analysis": pricing_analysis},
            }

        except Exception as exc:
            return self._log_error(state, f"PricingAgent failed: {exc}")
