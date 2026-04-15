/**
 * lib/api.ts — Typed API helpers for ConfMind backend.
 *
 * Endpoints:
 *   POST /api/run-plan        → start or refine a plan
 *   GET  /api/agent-status    → SSE stream of agent execution logs
 *   GET  /api/output          → full AgentState JSON
 */

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

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

  const data = (await res.json()) as AgentState;
  return normalizeAgentState(data);
}

/**
 * GET /api/output — Retrieve the full AgentState after agents have completed.
 */
export async function getOutput(planId?: string): Promise<AgentState> {
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
}

/**
 * GET /api/agent-status — Subscribe to SSE stream of agent execution logs.
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
