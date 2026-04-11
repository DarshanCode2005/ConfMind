"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getOutput, type AgentState } from "@/lib/api";
import type { AgentStatus } from "@/components/AgentGraph";

import AgentLogs from "@/components/AgentLogs";
import AgentGraph from "@/components/AgentGraph";
import SponsorCards from "@/components/SponsorCards";
import SpeakerGrid from "@/components/SpeakerGrid";
import VenueTable from "@/components/VenueTable";
import PricingTiers from "@/components/PricingTiers";
import AttendanceChart from "@/components/AttendanceChart";
import ScheduleTimeline from "@/components/ScheduleTimeline";
import WhatIfPanel from "@/components/WhatIfPanel";
import RefinementPanel from "@/components/RefinementPanel";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, RefreshCw, ArrowLeft, AlertTriangle } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [state, setState] = useState<AgentState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<
    Record<string, AgentStatus>
  >({});

  const fetchOutput = useCallback(async () => {
    try {
      const data = await getOutput();
      setState(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load output.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch — backend may already have results
    fetchOutput();

    // Auto-refresh every 5 seconds while agents are still running
    const interval = setInterval(() => {
      fetchOutput();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchOutput]);

  const handleAgentStatus = useCallback(
    (agent: string, status: "running" | "completed" | "pending") => {
      setAgentStatuses((prev) => ({ ...prev, [agent]: status }));
    },
    []
  );

  const handleRefined = useCallback((newState: AgentState) => {
    setState(newState);
    setLoading(false);
  }, []);

  const hasResults =
    state &&
    (state.sponsors?.length ||
      state.speakers?.length ||
      state.venues?.length ||
      state.ticket_tiers?.length ||
      state.schedule?.length);

  return (
    <div className="min-h-screen bg-background">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-muted-foreground"
              onClick={() => router.push("/")}
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
            <Separator orientation="vertical" className="h-5" />
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              <span className="font-semibold text-sm">ConfMind Dashboard</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {loading && (
              <Badge
                variant="outline"
                className="gap-1.5 text-xs bg-blue-400/10 text-blue-300 border-blue-400/20"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-400" />
                </span>
                Agents Running
              </Badge>
            )}
            {!loading && hasResults && (
              <Badge
                variant="outline"
                className="gap-1.5 text-xs bg-emerald-400/10 text-emerald-300 border-emerald-400/20"
              >
                Plan Ready
              </Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-xs"
              onClick={fetchOutput}
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Error state */}
        {error && !hasResults && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-destructive mt-0.5" />
            <div>
              <p className="font-semibold text-sm text-destructive">
                Failed to load output
              </p>
              <p className="text-xs text-muted-foreground mt-1">{error}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Make sure the FastAPI backend is running at{" "}
                <code className="bg-muted rounded px-1">
                  {process.env.NEXT_PUBLIC_BACKEND_URL ??
                    "http://localhost:8000"}
                </code>
              </p>
            </div>
          </div>
        )}

        {/* ① Agent Logs — LIVE */}
        <section>
          <AgentLogs onAgentStatusChange={handleAgentStatus} />
        </section>

        {/* ② Agent Graph */}
        <section>
          <AgentGraph agentStatuses={agentStatuses} />
        </section>

        {/* ③ Results */}
        <section className="space-y-8">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold">Results</h2>
            {loading && !hasResults && (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                Waiting for agents...
              </Badge>
            )}
          </div>

          {/* Loading skeletons */}
          {loading && !hasResults && (
            <div className="space-y-6">
              {/* Sponsor skeletons */}
              <div>
                <Skeleton className="h-6 w-32 mb-4" />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-44 rounded-xl" />
                  ))}
                </div>
              </div>
              {/* Speaker skeletons */}
              <div>
                <Skeleton className="h-6 w-28 mb-4" />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-52 rounded-xl" />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Sponsors */}
          {((state?.sponsors?.length ?? 0) > 0 || (loading && hasResults)) && (
            <SponsorCards sponsors={state?.sponsors} loading={loading && !state?.sponsors?.length} />
          )}

          {/* Speakers */}
          {((state?.speakers?.length ?? 0) > 0 || (loading && hasResults)) && (
            <SpeakerGrid speakers={state?.speakers} loading={loading && !state?.speakers?.length} />
          )}

          {/* Venue Table */}
          {((state?.venues?.length ?? 0) > 0 || (loading && hasResults)) && (
            <VenueTable venues={state?.venues} loading={loading && !state?.venues?.length} />
          )}

          {/* Pricing + Attendance in a 2-col grid */}
          {(state?.ticket_tiers?.length ?? 0) > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PricingTiers tiers={state?.ticket_tiers} />
              <AttendanceChart tiers={state?.ticket_tiers} />
            </div>
          )}

          {/* Schedule */}
          {(state?.schedule?.length ?? 0) > 0 && (
            <ScheduleTimeline schedule={state?.schedule} />
          )}

          {/* Revenue summary */}
          {state?.total_est_revenue && (
            <div className="flex gap-4 flex-wrap">
              <div className="flex-1 min-w-[180px] bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-5 py-4">
                <p className="text-xs text-muted-foreground">Total Est. Revenue</p>
                <p className="text-2xl font-bold text-emerald-400 tabular-nums">
                  $
                  {state.total_est_revenue >= 1_000_000
                    ? `${(state.total_est_revenue / 1_000_000).toFixed(2)}M`
                    : `${(state.total_est_revenue / 1_000).toFixed(1)}k`}
                </p>
              </div>
              {state.break_even_price != null && (
                <div className="flex-1 min-w-[180px] bg-blue-500/10 border border-blue-500/20 rounded-lg px-5 py-4">
                  <p className="text-xs text-muted-foreground">Break-even Price</p>
                  <p className="text-2xl font-bold text-blue-400 tabular-nums">
                    ${state.break_even_price.toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ④ Simulation + Refinement */}
        <section className="space-y-8">
          <Separator />
          <h2 className="text-xl font-bold">Simulate & Refine</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <WhatIfPanel tiers={state?.ticket_tiers} />
            <RefinementPanel onRefined={handleRefined} />
          </div>
        </section>
      </main>
    </div>
  );
}
