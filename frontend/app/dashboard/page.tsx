"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getOutput, runPlan, type AgentState, type EventConfigInput } from "@/lib/api";
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
import { ThemeToggle } from "@/components/ThemeToggle";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, RefreshCw, ArrowLeft, AlertTriangle } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const launchStartedRef = useRef(false);
  const [state, setState] = useState<AgentState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<
    Record<string, AgentStatus>
  >({});

  const fetchOutput = useCallback(async () => {
    if (!planId) {
      return;
    }

    try {
      const data = await getOutput(planId);
      setState(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load output.");
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    if (launchStartedRef.current) {
      return;
    }
    launchStartedRef.current = true;

    const maybeLaunch = async () => {
      const storedPlanId = sessionStorage.getItem("confmind_plan_id");
      const launchOnDashboard = sessionStorage.getItem("confmind_run_on_dashboard") === "1";
      const storedConfig = sessionStorage.getItem("confmind_config");

      if (launchOnDashboard && storedConfig) {
        let parsedConfig: EventConfigInput;
        try {
          parsedConfig = JSON.parse(storedConfig) as EventConfigInput;
        } catch {
          setLoading(false);
          setError("Saved event config is invalid. Please start a new plan.");
          sessionStorage.removeItem("confmind_run_on_dashboard");
          return;
        }

        setLoading(true);
        setError(null);
        setState(null);
        setPlanId(null);
        setAgentStatuses({ orchestrator: "running" });
        sessionStorage.removeItem("confmind_run_on_dashboard");

        try {
          const result = await runPlan(parsedConfig);
          setState(result);
          if (result.plan_id) {
            sessionStorage.setItem("confmind_plan_id", result.plan_id);
            setPlanId(result.plan_id);
          }
          setError(null);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to run plan.");
        } finally {
          setLoading(false);
        }
        return;
      }

      if (!storedPlanId) {
        setLoading(false);
        setError("No saved plan found. Start a new plan from the home page.");
        return;
      }

      setPlanId(storedPlanId);
    };

    void maybeLaunch();
  }, []);

  useEffect(() => {
    if (!planId) {
      return;
    }

    // Initial fetch — backend may already have results
    fetchOutput();

    // Auto-refresh every 5 seconds while agents are still running
    const interval = setInterval(() => {
      fetchOutput();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchOutput, planId]);

  const handleAgentStatus = useCallback(
    (agent: string, status: "running" | "completed" | "pending") => {
      setAgentStatuses((prev) => ({ ...prev, [agent]: status }));
    },
    []
  );

  const handleRefined = useCallback((newState: AgentState) => {
    setState(newState);
    if (newState.plan_id) {
      sessionStorage.setItem("confmind_plan_id", newState.plan_id);
      setPlanId(newState.plan_id);
    }
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
    <div className="min-h-screen relative max-w-[100vw] overflow-x-hidden pt-18">
      <header className="fixed top-0 left-0 right-0 z-30 border-b border-border/60 bg-background/75 backdrop-blur-xl shadow-sm">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight bg-linear-to-br from-slate-900 via-indigo-700 to-cyan-600 dark:from-white dark:via-indigo-200 dark:to-cyan-300 bg-clip-text text-transparent">
              Event Dashboard
            </h1>
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
                className="gap-1.5 text-xs bg-primary/10 text-primary border-primary/20"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
                </span>
                Agents Running
              </Badge>
            )}
            {!loading && hasResults && (
              <Badge
                variant="outline"
                className="gap-1.5 text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border-emerald-500/20"
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
            <ThemeToggle />
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

        {/* Agent Logs */}
        <section>
          <AgentLogs planId={planId ?? undefined} onAgentStatusChange={handleAgentStatus} />
        </section>

        {/* Agent Graph */}
        <section>
          <AgentGraph agentStatuses={agentStatuses} />
        </section>

        {/* Results */}
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
              <div className="flex-1 min-w-45 bg-card/80 border border-border/60 rounded-xl px-5 py-4 shadow-sm">
                <p className="text-xs text-muted-foreground">Total Est. Revenue</p>
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-300 tabular-nums">
                  $
                  {state.total_est_revenue >= 1_000_000
                    ? `${(state.total_est_revenue / 1_000_000).toFixed(2)}M`
                    : `${(state.total_est_revenue / 1_000).toFixed(1)}k`}
                </p>
              </div>
              {state.break_even_price != null && (
                <div className="flex-1 min-w-45 bg-card/80 border border-border/60 rounded-xl px-5 py-4 shadow-sm">
                  <p className="text-xs text-muted-foreground">Break-even Price</p>
                  <p className="text-2xl font-bold text-primary tabular-nums">
                    ${state.break_even_price.toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Simulation and Refinement */}
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
