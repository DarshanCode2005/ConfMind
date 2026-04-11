/**
 * lib/api.ts — Typed API helpers for ConfMind backend.
 *
 * Endpoints:
 *   POST /api/run-plan        → start or refine a plan
 *   GET  /api/agent-status    → SSE stream of agent execution logs
 *   GET  /api/output          → full AgentState JSON
 */

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

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
  status?: string;
  sponsors?: SponsorSchema[];
  speakers?: SpeakerSchema[];
  venues?: VenueSchema[];
  exhibitors?: ExhibitorSchema[];
  ticket_tiers?: TicketTierSchema[];
  communities?: CommunitySchema[];
  schedule?: ScheduleEntry[];
  total_est_revenue?: number;
  break_even_price?: number;
  gtm_messages?: Record<string, string>;
  distribution_plan?: string[];
  conflicts?: string[];
  error?: string;
}

// ─── API Helpers ─────────────────────────────────────────────────────────────

/**
 * POST /api/run-plan — Start or refine a conference plan.
 */
export async function runPlan(input: EventConfigInput): Promise<AgentState> {
  const res = await fetch(`${BACKEND_URL}/api/run-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`runPlan failed: ${res.status} — ${text}`);
  }

  return res.json() as Promise<AgentState>;
}

/**
 * GET /api/output — Retrieve the full AgentState after agents have completed.
 */
export async function getOutput(): Promise<AgentState> {
  const res = await fetch(`${BACKEND_URL}/api/output`, {
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`getOutput failed: ${res.status} — ${text}`);
  }

  return res.json() as Promise<AgentState>;
}

/**
 * GET /api/agent-status — Subscribe to SSE stream of agent execution logs.
 *
 * @param onMessage   Called with each new log line from the backend.
 * @param onError     Called when the EventSource errors.
 * @returns           Cleanup function — call this to close the EventSource.
 */
export function subscribeToAgentStatus(
  onMessage: (line: string) => void,
  onError?: (e: Event) => void
): () => void {
  const es = new EventSource(`${BACKEND_URL}/api/agent-status`);

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
