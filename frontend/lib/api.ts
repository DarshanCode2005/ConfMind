/**
 * lib/api.ts — Typed API helpers for ConfMind backend.
 *
 * Endpoints:
 *   POST /api/run-plan        → start or refine a plan
 *   GET  /api/agent-status    → SSE stream of agent execution logs
 *   GET  /api/output          → full AgentState JSON
 *
 * Mock Mode: If backend is unavailable, returns mock data automatically.
 * This allows frontend development without a running backend.
 */

import { mockAgentState } from "./mock-data";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";

// ─── Input / Output Types ───────────────────────────────────────────────────

export interface EventConfigInput {
  category: string;
  geography: string;
  audience_size: number;
  budget_usd: number;
  event_dates: string;
  refinement_prompt?: string;
}

export interface SponsorSchema {
  name: string;
  website?: string;
  industry?: string;
  geo?: string;
  tier: "Gold" | "Silver" | "Bronze" | "General";
  relevance_score: number;
}

export interface SpeakerSchema {
  name: string;
  bio?: string;
  linkedin_url?: string;
  topic?: string;
  region?: string;
  influence_score: number;
  speaking_experience: number;
}

export interface VenueSchema {
  name: string;
  city: string;
  country?: string;
  capacity?: number | null;
  price_range?: string;
  past_events?: string[];
  score: number;
  source_url?: string;
}

export interface ExhibitorSchema {
  name: string;
  cluster?: string;
  relevance: number;
  website?: string;
}

export interface TicketTierSchema {
  name: "Early Bird" | "General" | "VIP";
  price: number;
  est_sales: number;
  revenue: number;
}

export interface CommunitySchema {
  platform: string;
  name: string;
  size: number;
  niche?: string;
  invite_url?: string;
}

export interface ScheduleEntry {
  time: string;
  room?: string;
  speaker?: string;
  topic: string;
}

export interface AgentState {
  plan_id?: string;
  status?: string;
  sponsors?: SponsorSchema[];
  speakers?: SpeakerSchema[];
  venues?: VenueSchema[];
  exhibitors?: ExhibitorSchema[];
  pricing?: TicketTierSchema[];
  ticket_tiers?: TicketTierSchema[];
  communities?: CommunitySchema[];
  schedule?: ScheduleEntry[];
  revenue?: {
    total_projected_revenue?: number;
    break_even?: {
      attendance_needed?: number;
    };
  };
  total_est_revenue?: number;
  break_even_price?: number;
  gtm_messages?: Record<string, string>;
  distribution_plan?: string[];
  conflicts?: string[];
  errors?: string[];
  error?: string;
}

// ─── API Helpers ─────────────────────────────────────────────────────────────

function normalizeAgentState(raw: AgentState): AgentState {
  const ticketTiers = raw.ticket_tiers ?? raw.pricing ?? [];
  const totalRevenue =
    raw.total_est_revenue ?? raw.revenue?.total_projected_revenue;

  // Keep backward-compatibility with older backend payloads that expose
  // break-even attendance in nested revenue.break_even.
  const breakEven =
    raw.break_even_price ?? raw.revenue?.break_even?.attendance_needed;

  return {
    ...raw,
    ticket_tiers: ticketTiers,
    total_est_revenue: totalRevenue,
    break_even_price: breakEven,
    error:
      raw.error ??
      (raw.errors && raw.errors.length > 0 ? raw.errors.join(" | ") : undefined),
  };
}

/**
 * POST /api/run-plan — Start or refine a conference plan.
 * Falls back to mock data if backend is unavailable.
 */
export async function runPlan(input: EventConfigInput): Promise<AgentState> {
  // Use mock data if explicitly enabled or if backend is not available
  if (USE_MOCK_DATA) {
    if (typeof window !== "undefined") {
      console.log("📊 Using mock data (NEXT_PUBLIC_USE_MOCK_DATA=true)");
    }
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 500));
    return normalizeAgentState(mockAgentState);
  }

  try {
    const res = await fetch(`${BACKEND_URL}/api/run-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`runPlan failed: ${res.status} — ${text}`);
    }

    const data = (await res.json()) as AgentState;
    return normalizeAgentState(data);
  } catch (error) {
    // Fall back to mock data if backend is unavailable
    if (typeof window !== "undefined") {
      console.log(
        "⚠️  Backend unavailable, using mock data for development",
        error
      );
    }
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 500));
    return normalizeAgentState(mockAgentState);
  }
}

/**
 * GET /api/output — Retrieve the full AgentState after agents have completed.
 * Falls back to mock data if backend is unavailable.
 */
export async function getOutput(planId?: string): Promise<AgentState> {
  // Use mock data if explicitly enabled
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    return normalizeAgentState(mockAgentState);
  }

  try {
    const url = planId
      ? `${BACKEND_URL}/api/output/${encodeURIComponent(planId)}`
      : `${BACKEND_URL}/api/output`;
    const res = await fetch(url, {
      cache: "no-store",
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`getOutput failed: ${res.status} — ${text}`);
    }

    const data = (await res.json()) as AgentState;
    return normalizeAgentState(data);
  } catch (error) {
    // Fall back to mock data if backend is unavailable
    if (typeof window !== "undefined") {
      console.log(
        "⚠️  Backend unavailable, returning mock data for development",
        error
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
    return normalizeAgentState(mockAgentState);
  }
}

/**
 * GET /api/agent-status — Subscribe to SSE stream of agent execution logs.
 * When backend is unavailable, simulates realistic agent execution logs.
 *
 * @param onMessage   Called with each new log line from the backend.
 * @param onError     Called when the EventSource errors.
 * @returns           Cleanup function — call this to close the EventSource.
 */
export function subscribeToAgentStatus(
  planId: string | undefined,
  onMessage: (line: string) => void,
  onError?: (e: Event) => void
): () => void {
  // If using mock data, simulate agent execution logs
  if (USE_MOCK_DATA) {
    const mockLogs = [
      JSON.stringify({ agent: "sponsor_agent", status: "RUNNING" }),
      "sponsor_agent: Found 12 potential sponsors",
      JSON.stringify({ agent: "sponsor_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "speaker_agent", status: "RUNNING" }),
      "speaker_agent: Enriching 8 speaker profiles from LinkedIn",
      JSON.stringify({ agent: "speaker_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "venue_agent", status: "RUNNING" }),
      "venue_agent: Scoring 15 venues based on capacity and location",
      JSON.stringify({ agent: "venue_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "exhibitor_agent", status: "RUNNING" }),
      "exhibitor_agent: Identified 10 relevant exhibitor opportunities",
      JSON.stringify({ agent: "exhibitor_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "pricing_agent", status: "RUNNING" }),
      "pricing_agent: Calculated ticket pricing with break-even analysis",
      JSON.stringify({ agent: "pricing_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "community_gtm_agent", status: "RUNNING" }),
      "community_gtm_agent: Scanning 50+ Discord/Slack communities",
      "community_gtm_agent: Generated platform-specific GTM messages",
      JSON.stringify({ agent: "community_gtm_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "event_ops_agent", status: "RUNNING" }),
      "event_ops_agent: Building event schedule with 2-day agenda",
      JSON.stringify({ agent: "event_ops_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "revenue_agent", status: "RUNNING" }),
      "revenue_agent: Projecting $928k total revenue",
      JSON.stringify({ agent: "revenue_agent", status: "COMPLETED" }),
      JSON.stringify({ agent: "__all__", status: "COMPLETED" }),
    ];

    let logIndex = 0;
    const interval = setInterval(() => {
      if (logIndex < mockLogs.length) {
        onMessage(mockLogs[logIndex]);
        logIndex++;
      } else {
        clearInterval(interval);
      }
    }, 300); // Send a log every 300ms

    return () => clearInterval(interval);
  }

  // Real backend: use EventSource for SSE
  const url = planId
    ? `${BACKEND_URL}/api/agent-status?plan_id=${encodeURIComponent(planId)}`
    : `${BACKEND_URL}/api/agent-status`;
  const es = new EventSource(url);

  es.onmessage = (event) => {
    if (event.data) {
      onMessage(event.data as string);
    }
  };

  es.onerror = (e) => {
    onError?.(e);
    // Close on error so we don't silently retry forever.
    es.close();
  };

  return () => es.close();
}
