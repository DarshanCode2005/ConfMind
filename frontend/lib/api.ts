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
  event_name?: string;
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

export interface WhatIfLinearModel {
  slope: number;
  intercept: number;
  valid: boolean;
  sample_count?: number;
}

export interface PricingAnalysisMetadata {
  demand_ratio?: number;
  base_price?: number;
  tier_prices?: Record<string, number>;
  monte_carlo?: Record<string, unknown>;
  break_even?: Record<string, unknown>;
  historical_pairs_count?: number;
  what_if_model?: WhatIfLinearModel;
}

export interface AgentState {
  plan_id?: string;
  status?: string;
  event_config?: EventConfigInput;
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
  metadata?: {
    pricing_analysis?: PricingAnalysisMetadata;
    [key: string]: unknown;
  };
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
 * POST /api/run-plan/async — Start a plan (returns plan_id immediately),
 * then poll /api/output/{plan_id} until agents finish.
 *
 * Uses the fire-and-forget async endpoint to avoid Render's 30-second
 * HTTP proxy timeout that kills the blocking /api/run-plan endpoint.
 */
export async function runPlan(input: EventConfigInput): Promise<AgentState> {
  // Step 1: Fire the plan — backend returns {plan_id, status:"running"} instantly
  const startRes = await fetch(`${BACKEND_URL}/api/run-plan/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!startRes.ok) {
    const text = await startRes.text();
    throw new Error(`runPlan failed to start: ${startRes.status} — ${text}`);
  }

  const { plan_id } = (await startRes.json()) as { plan_id: string; status: string };

  // Return immediately so the dashboard can establish SSE connections using plan_id.
  // The dashboard's existing setInterval will handle polling /api/output/{plan_id}.
  return normalizeAgentState({
    plan_id,
    event_config: input,
    sponsors: [],
    speakers: [],
    venues: [],
    exhibitors: [],
    pricing: [],
    communities: [],
    schedule: [],
    revenue: {},
    gtm_messages: {},
    messages: [],
    errors: [],
  } as unknown as AgentState);
}


export async function getOutput(planId?: string): Promise<AgentState | null> {
  const url = planId
    ? `${BACKEND_URL}/api/output/${encodeURIComponent(planId)}`
    : `${BACKEND_URL}/api/output`;
  const res = await fetch(url, {
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    // Use the specific 404 message from earlier
    if (res.status === 404) throw new Error("Plan not found. It may be expired or invalid.");
    throw new Error(`getOutput failed: ${res.status} — ${text}`);
  }

  const data = (await res.json()) as AgentState & { status?: string, errors?: string[] };
  
  if (data.status === "error") {
      throw new Error(data.errors?.join(" | ") ?? "Pipeline failed");
  }

  if (data.status === "running") {
      return null;
  }

  return normalizeAgentState(data as AgentState);
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

export interface ChatInput {
  session_id: string;
  message: string;
  plan_id?: string;
}

export interface ChatResponse {
  message: string;
}

/**
 * POST /api/chat — Chat with the ConfMind agent.
 */
export async function chat(input: ChatInput): Promise<ChatResponse> {
  const res = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`chat failed: ${res.status} — ${text}`);
  }

  return (await res.json()) as ChatResponse;
}
