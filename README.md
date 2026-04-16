# CONFMIND — AI-Powered Multi-Agent Event Organizer

**The intelligent, domain-agnostic system that autonomously plans, prices, and executes conferences, music festivals, sports events, and educational conferences.**

![High Prep Logo](https://via.placeholder.com/800x200/0A2540/FFFFFF?text=Pinch+%C3%97+IIT+Roorkee+High+Prep+2026)

**Built for the Pinch × IIT Roorkee High Prep Problem Solving Championship 2026**

**Live Demo** • [GitHub Repo](https://github.com/yourusername/confmind) • [Demo Video](https://youtu.be/placeholder) • [Hosted Platform](https://confmind.streamlit.app)

---

## 📋 Table of Contents
- [Overview](#overview)
- [Problem Statement Alignment](#problem-statement-alignment)
- [Core Challenges & Creative Solutions](#core-challenges--creative-solutions)
- [Multi-Agent Architecture](#multi-agent-architecture)
- [Key Features & Innovations](#key-features--innovations)
- [Technical Stack & Implementation Details](#technical-stack--implementation-details)
- [Data Aggregation Layer & Mandatory Dataset](#data-aggregation-layer--mandatory-dataset)
- [Persistent Chat Agent (Always-On Interface)](#persistent-chat-agent-always-on-interface)
- [Installation & Quick Start](#installation--quick-start)
- [Usage Flow](#usage-flow)
- [Evaluation Criteria Alignment](#evaluation-criteria-alignment)
- [Deliverables Checklist](#deliverables-checklist)
- [Team & Acknowledgments](#team--acknowledgments)

---

## Overview

CONFMIND is a **production-ready, domain-agnostic multi-agent system** that takes three inputs — **event category**, **geography**, and **target audience size/budget** — and autonomously generates a complete event plan: sponsors, speakers, venues, exhibitors, pricing & footfall forecasts, GTM strategy, full schedule, revenue projections, and outreach-ready emails.

It supports **four categories**:
- Sports Events
- Music Festivals
- Technical Conferences (AI/Web3/ClimateTech etc.)
- Educational Conferences

The system is **fully persistent**, features a **RAG-powered always-on Chat Agent**, and dynamically spawns agents based on real-world data density from PredictHQ. It solves the exact pain points outlined in the High Prep problem statement using 2026-native agentic patterns.

---

## Problem Statement Alignment

> “Design and build an AI-powered multi-agent system for conference organization, where each agent specializes in a specific function of the event lifecycle. Given: a conference/event category, a geography, a target audience size.”

CONFMIND directly implements **every required agent** from the problem statement:

1. **Sponsor Agent**
2. **Speaker/Artist Agent**
3. **Exhibitor Agent**
4. **Venue Agent**
5. **Pricing & Footfall Agent**
6. **Community & GTM Agent**
7. **Event Ops / Execution Agent** (highly recommended — fully implemented)
8. **Revenue projection, ticket tier simulation, break-even analysis** (implemented)

**Extra credit achieved:**
- Domain-agnostic architecture (skill files + PredictHQ category mapping)
- Extends beyond conferences to music festivals & sports events
- Mandatory structured 2025-2026 dataset delivered

---

## Core Challenges & Creative Solutions

| Challenge (from Problem Statement)              | Creative Solution Implemented in CONFMIND                                                                 |
|------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| **Data Fragmentation**                         | Hybrid PredictHQ (structured Events + Features API) + Tavily advanced search. Dynamic N web-search agents spawn based on PredictHQ result count (never fixed at 6). |
| **Lack of Historical Intelligence**            | Per-entity ChromaDB RAG + mandatory 2025-2026 dataset as living knowledge base. Agents read/write memory on every pass. |
| **Manual Outreach & Planning**                 | Sponsor Agent generates custom proposals + **Chat Agent autonomously searches sponsor emails and drafts personalized outreach** based on user tone preference. |
| **Pricing & Demand Uncertainty**               | Historical interpolation + PredictHQ demand_ratio + Monte Carlo (200 iterations). No black-box ML — fully transparent and explainable. |
| **Go-to-Market Complexity**                    | GTM Agent focuses on Discord first, uses PredictHQ upcoming-event timing for promotion windows, generates channel-specific message variants. |

**Novelty highlights:**
- Dynamic agent spawning (`N = min(max(3, total//5), 8)`) based on real data density
- Per-entity ChromaDB indexing (one document per sponsor/speaker/venue) — solves “huge data in context” problem
- Persistent LangGraph + always-on Chat Agent with tool-based reruns (specific agents or full replan)
- Skill files make the entire system truly domain-agnostic

---

## Multi-Agent Architecture

**LangGraph Supervisor + Parallel Nodes** (hierarchical yet dynamic)
User Input
↓
Main Orchestrator (Supervisor)
├── PredictHQ Probe → decide N
└── Spawn N parallel Web Search Agents
↓
Skill File → Agent Execution Order
↓
Parallel Tier 1: Sponsor + Speaker + Venue
Sequential Tier 2: Exhibitor → Pricing + GTM → Event Ops → Revenue
↓
Persistent Chat Agent (always available)


**Shared State:** `AgentState` TypedDict (only modified keys returned)  
**Memory:** ChromaDB (persistent) + `_read_memory()` / `_write_memory()` on every pass + Memory Curator (future)

---

## Key Features & Innovations

- **Multi-Agent Orchestration System** — LangGraph with dynamic spawning and persistence
- **Agents communicate and share context** — via shared `AgentState` + ChromaDB
- **Data Aggregation Layer** — PredictHQ primary + Tavily enrichment
- **Real-time web scraping pipelines** — Tavily (advanced depth, structured output)
- **Recommendation Engine + Relevance Scoring** — multi-criteria scoring with LLM-assisted industry/topic match
- **Context-aware suggestions** — every agent reads skill file + past_events + user inputs
- **Search + Ranking Algorithms** — frequency-normalized, geography-aware, influence scoring
- **Predictive Modeling** — transparent historical interpolation + PredictHQ Features API
- **Pricing vs attendance forecasting** — p10/p50/p90 Monte Carlo + demand_ratio
- **User Interface** — Streamlit input + **persistent Chat Agent** (`POST /chat`)
- **Autonomous Outreach** — Chat Agent finds sponsor emails + generates custom emails
- **Multi-agent collaboration visualization** — LangSmith traces available

---

## Technical Stack & Implementation Details

- **Orchestration:** LangGraph (state machine + checkpointer)
- **Persistence:** `AsyncSqliteSaver("checkpoints.db")` + `InMemoryStore`
- **Vector Memory / RAG:** ChromaDB (per-entity documents with rich metadata)
- **APIs:** PredictHQ Events + Features (official Python SDK), Tavily (advanced search)
- **LLM Backend:** OpenRouter (configurable)
- **Frontend:** Streamlit (planning form + live chat)
- **Backend:** FastAPI (`/chat` WebSocket-ready endpoint)
- **Tools:** Strict contracts for Tavily & PredictHQ with retry logic (429 → 3s wait, 401 → fallback)
- **Error Handling:** Partial state continuation, global 300s timeout
- **Memory Management:** Last-10-turn chat history + retrieved docs only (≤3000 tokens)

**Chat Agent Tools (3 only):**
1. `retrieve()` — metadata-filtered RAG
2. `rerun_agents(nodes, param_overrides)` — specific or full replan
3. `get_summary()` — cached 300-word overview

---

## Data Aggregation Layer & Mandatory Dataset

**Mandatory Data Deliverable (fully implemented):**
- Structured JSON + CSV of 2025-2026 events (sports, music, technical, educational)
- Fields: Event name, Location, Category/theme, Sponsors, Speakers, Ticket pricing, Estimated attendance, PHQ rank, predicted spend
- **Sources & Extraction Method** (included in `data/sources.md`):
  - Primary: PredictHQ Events API (structured, verified, historical + future)
  - Enrichment: Tavily advanced search
  - Cleaned & normalized automatically by Web Search Agents
- Dataset is generated on every run and can be exported via Chat Agent

---

## Persistent Chat Agent (Always-On Interface)

The **star feature** — after planning completes, users talk to CONFMIND naturally:

- “Show me the top 3 sponsors and their proposal drafts”
- “Find emails for the top sponsors and draft outreach for a platinum tier”
- “Change geography to Singapore and re-run Pricing Agent”
- “Is this venue realistic for 800 attendees?”

All queries use **per-entity RAG** (never loads full state). Reruns are confirmed once then executed.

---

## Installation & Quick Start

```bash
git clone https://github.com/yourusername/confmind.git
cd confmind
pip install -r requirements.txt

# .env (required)
cp .env.example .env
# Paste: TAVILY_API_KEY, PREDICTHQ_API_KEY, OPENROUTER_API_KEY

streamlit run app.py
