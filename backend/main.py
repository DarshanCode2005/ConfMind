import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventConfigInput(BaseModel):
    category: str
    geography: str
    audience_size: int
    budget_usd: int
    event_dates: str


MOCK_STATE = {
    "status": "completed",
    "total_est_revenue": 1400000,
    "break_even_price": 250,
    "sponsors": [
        {
            "name": "TechCorp",
            "tier": "Gold",
            "relevance_score": 9.5,
            "industry": "AI",
            "geo": "Global",
            "website": "https://example.com",
        },
        {
            "name": "Innovate Ltd",
            "tier": "Silver",
            "relevance_score": 8.0,
            "industry": "Cloud",
            "geo": "Europe",
        },
    ],
    "speakers": [
        {
            "name": "Jane Doe",
            "influence_score": 9.8,
            "speaking_experience": 15,
            "topic": "Future of AI",
            "region": "USA",
            "linkedin_url": "https://linkedin.com",
        },
        {
            "name": "John Smith",
            "influence_score": 7.5,
            "speaking_experience": 5,
            "topic": "Scaling Systems",
            "region": "Europe",
        },
    ],
    "venues": [
        {
            "name": "Grand Convention Center",
            "city": "San Francisco",
            "capacity": 5000,
            "score": 9.0,
            "price_range": "$50k - $100k",
        }
    ],
    "ticket_tiers": [
        {"name": "Early Bird", "price": 400, "est_sales": 1000, "revenue": 400000},
        {"name": "General", "price": 600, "est_sales": 1200, "revenue": 720000},
        {"name": "VIP", "price": 1400, "est_sales": 200, "revenue": 280000},
    ],
    "schedule": [
        {"time": "09:00", "topic": "Keynote Opening", "speaker": "Jane Doe", "room": "Main Hall"},
        {"time": "11:00", "topic": "Technical track", "speaker": "John Smith", "room": "Room A"},
    ],
}


@app.post("/api/run-plan")
async def run_plan(config: EventConfigInput):
    # Just return mock state for now to simulate success
    return MOCK_STATE


@app.get("/api/output")
async def get_output():
    return MOCK_STATE


@app.get("/api/agent-status")
async def agent_status(request: Request):
    async def event_generator():
        messages = [
            "[Orchestrator] Starting plan...",
            "[Sponsor Agent] Running...",
            "[Sponsor Agent] Completed finding sponsors",
            "[Speaker Agent] Running...",
            "[Speaker Agent] Completed extracting speakers",
            "[Pricing Agent] Running...",
            "[Pricing Agent] Completed generating ticket tiers",
            "[Orchestrator] Completed",
        ]
        for msg in messages:
            if await request.is_disconnected():
                break
            yield f"data: {msg}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
