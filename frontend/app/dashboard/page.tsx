"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
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
import ChatWidget from "@/components/ChatWidget";
import { MOCK_AGENT_STATE } from "@/lib/mock-data";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, RefreshCw, ArrowLeft, AlertTriangle, TrendingUp, Users, Target, FlaskConical } from "lucide-react";

export default function DashboardPage() {
  const launchStartedRef = useRef(false);
  const [state, setState] = useState<AgentState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [agentStatuses, setAgentStatuses] = useState<
    Record<string, AgentStatus>
  >({});

  const handleDemoMode = () => {
    setIsDemoMode(true);
    setState(MOCK_AGENT_STATE);
    setLoading(false);
    setError(null);
    setPlanId("demo-mode-active");
    
    // Set all nodes to completed for the graph
    const demoStatuses: Record<string, AgentStatus> = {
      phq_probe: "completed",
      web_search_1: "completed",
      web_search_2: "completed",
      web_search_3: "completed",
      shared_memory: "completed",
      sponsor: "completed",
      speaker: "completed",
      venue: "completed",
      exhibitor: "completed",
      pricing: "completed",
      gtm: "completed",
      eventops: "completed",
      revenue: "completed"
    };
    setAgentStatuses(demoStatuses);
  };

  const fetchOutput = useCallback(async () => {
    if (!planId) {
      return;
    }

    try {
      const data = await getOutput(planId);
      if (data !== null) {
        setState(data);
      }
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
        setAgentStatuses({ phq_probe: "running" }); // Start with the first node
        sessionStorage.removeItem("confmind_run_on_dashboard");

        try {
          const result = await runPlan(parsedConfig);
          setState(result);
          const id = result.plan_id ?? null;
          if (id) {
            sessionStorage.setItem("confmind_plan_id", id);
            setPlanId(id);
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
    (agent: string, status: "pending" | "running" | "completed") => {
      setAgentStatuses((prev) => ({ ...prev, [agent]: status }));
    },
    []
  );

  const summaryCount = (value?: number | null) => value ?? 0;
  const gtmCount = Object.keys(state?.gtm_messages ?? {}).length;

  const handleRefined = useCallback((newState: AgentState) => {
    setState(newState);
    if (newState.plan_id) {
      sessionStorage.setItem("confmind_plan_id", newState.plan_id);
      setPlanId(newState.plan_id);
    }
    setLoading(false);
  }, []);

  const renderSummaryCard = (
    label: string,
    value: number,
    icon: ReactNode,
    badgeStyle: string
  ) => (
    <div className="rounded-3xl border border-border/60 bg-muted/70 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold">{value}</p>
        </div>
        <div className={`inline-flex h-11 w-11 items-center justify-center rounded-3xl ${badgeStyle}`}>
          {icon}
        </div>
      </div>
    </div>
  );

  const hasResults =
    state &&
    (state.sponsors?.length ||
      state.speakers?.length ||
      state.venues?.length ||
      state.ticket_tiers?.length ||
      state.schedule?.length ||
      state.exhibitors?.length ||
      state.communities?.length ||
      gtmCount ||
      state.distribution_plan?.length);

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20 selection:text-primary">
      <main className="max-w-7xl mx-auto px-6 py-10 space-y-10">
        <section className="rounded-[2rem] border border-border/60 bg-card/80 p-8 shadow-2xl shadow-black/5 backdrop-blur-xl">
          <div className="grid gap-8 xl:grid-cols-[1.9fr_1fr]">
            <div className="space-y-5">
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Command Center
              </p>
              <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
                Conference orchestration in one unified workspace
              </h1>
              <p className="max-w-3xl text-sm leading-7 text-muted-foreground">
                Monitor agent execution, review sponsor and speaker recommendations, and surface GTM and exhibitor intelligence in a clean dashboard layout.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="outline" className="text-xs">Plan ID: {planId ?? "N/A"}</Badge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDemoMode}
                  className="text-xs h-7 gap-1.5 bg-violet-500/10 hover:bg-violet-500/20 border-violet-500/30 text-violet-400"
                >
                  <FlaskConical className="w-3.5 h-3.5" />
                  Load Demo Data
                </Button>
                <ThemeToggle />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {renderSummaryCard(
                "Sponsors",
                summaryCount(state?.sponsors?.length),
                <Target className="h-5 w-5" />,
                "bg-amber-500/10 text-amber-500"
              )}
              {renderSummaryCard(
                "Speakers",
                summaryCount(state?.speakers?.length),
                <Users className="h-5 w-5" />,
                "bg-cyan-500/10 text-cyan-500"
              )}
              {renderSummaryCard(
                "Exhibitors",
                summaryCount(state?.exhibitors?.length),
                <TrendingUp className="h-5 w-5" />,
                "bg-violet-500/10 text-violet-500"
              )}
              {renderSummaryCard(
                "GTM",
                gtmCount,
                <Brain className="h-5 w-5" />,
                "bg-emerald-500/10 text-emerald-500"
              )}
            </div>
          </div>
        </section>

        {error && !hasResults && (
          <div className="rounded-[1.8rem] border border-destructive/30 bg-destructive/10 p-5 shadow-sm">
            <div className="flex gap-4 items-start">
              <AlertTriangle className="w-5 h-5 text-destructive mt-0.5" />
              <div>
                <p className="font-semibold text-sm text-destructive">Failed to load output</p>
                <p className="text-sm text-muted-foreground mt-2">{error}</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Confirm backend is available at{' '}
                  <code className="rounded bg-muted px-1 py-0.5">
                    {process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'}
                  </code>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Execution Layer */}
        <section className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
          <AgentLogs planId={planId ?? undefined} onAgentStatusChange={handleAgentStatus} />
          <AgentGraph agentStatuses={agentStatuses} />
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
          {/* ROI & Revenue Center */}
          <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm overflow-hidden relative group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <TrendingUp className="w-20 h-20" />
            </div>
            <div className="mb-6">
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Revenue Agent</p>
              <h3 className="text-xl font-semibold">ROI Analysis</h3>
            </div>
            <div className="space-y-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Total Est. Revenue</p>
                <p className="text-3xl font-bold text-emerald-500">
                  ${(state?.total_est_revenue ?? state?.revenue?.total_projected_revenue ?? 0).toLocaleString()}
                </p>
              </div>
              <Separator className="bg-border/40" />
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Break-even Att.</p>
                  <p className="text-lg font-semibold">{state?.break_even_price ?? state?.revenue?.break_even?.attendance_needed ?? "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Target Margin</p>
                  <p className="text-lg font-semibold text-cyan-500">32.4%</p>
                </div>
              </div>
            </div>
          </div>

          {/* Live GTM */}
          <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Live GTM</p>
                <h3 className="text-xl font-semibold">GTM Messaging</h3>
              </div>
              <Badge variant="outline" className="text-xs">
                {gtmCount}
              </Badge>
            </div>
            {state?.gtm_messages && gtmCount > 0 ? (
              <div className="space-y-3 max-h-[160px] overflow-y-auto pr-2 custom-scrollbar">
                {Object.entries(state.gtm_messages).map(([platform, message]) => (
                  <div key={platform} className="rounded-2xl border border-border/50 bg-muted/30 p-3">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-muted-foreground">{platform}</p>
                    <p className="mt-1 text-xs leading-5 text-foreground line-clamp-2">{message}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">GTM recommendations will appear here once the agent completes.</p>
            )}
          </div>
        </section>

        {/* Discovery Sections */}
        <section className="space-y-10">
          {(state?.speakers?.length ?? 0) > 0 && (
            <SpeakerGrid speakers={state?.speakers} loading={loading} />
          )}

          {(state?.sponsors?.length ?? 0) > 0 && (
            <SponsorCards sponsors={state?.sponsors} loading={loading} />
          )}

          {(state?.venues?.length ?? 0) > 0 && (
            <VenueTable venues={state?.venues} loading={loading} />
          )}
        </section>

        {/* Intelligence Grid */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Exhibitor Opportunities */}
          {(state?.exhibitors?.length ?? 0) > 0 && (
            <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Exhibitor Agent</p>
                  <h3 className="text-xl font-semibold">Exhibitors</h3>
                </div>
                <Badge variant="outline" className="text-xs">
                  {state?.exhibitors?.length}
                </Badge>
              </div>
              <div className="space-y-3">
                {state?.exhibitors?.slice(0, 4).map((exhibitor) => (
                  <div key={exhibitor.name} className="flex items-center justify-between p-3 rounded-2xl border border-border/40 bg-muted/30">
                    <div>
                      <p className="text-sm font-medium">{exhibitor.name}</p>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{exhibitor.cluster}</p>
                    </div>
                    <Badge variant="outline" className="text-[10px]">
                      {exhibitor.relevance?.toFixed?.(1) ?? exhibitor.relevance}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Community Channels */}
          {(state?.communities?.length ?? 0) > 0 && (
            <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Community GTM</p>
                  <h3 className="text-xl font-semibold">Channels</h3>
                </div>
                <Badge variant="outline" className="text-xs">
                  {state?.communities?.length}
                </Badge>
              </div>
              <div className="space-y-3">
                {state?.communities?.slice(0, 4).map((community) => (
                  <div key={`${community.platform}-${community.name}`} className="p-3 rounded-2xl border border-border/40 bg-muted/30">
                    <p className="text-sm font-medium">{community.name}</p>
                    <p className="text-[10px] text-muted-foreground">{community.platform} • {community.size.toLocaleString()} members</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Full Width Sections: Simulaton, Pricing & Schedule */}
        <section className="space-y-10">
          {state && (
            <WhatIfPanel 
              tiers={state.ticket_tiers} 
              demandModel={state.metadata?.pricing_analysis?.what_if_model} 
            />
          )}

          {(state?.ticket_tiers?.length ?? 0) > 0 && (
            <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
              <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Pricing Strategy</p>
                  <h3 className="text-2xl font-bold">Ticket Tiers & Packaging</h3>
                </div>
                <Badge variant="outline" className="text-sm px-3">
                  {state?.ticket_tiers?.length} Tiers Defined
                </Badge>
              </div>
              <PricingTiers tiers={state?.ticket_tiers} />
            </div>
          )}

          {(state?.schedule?.length ?? 0) > 0 && (
            <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
              <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Event Operations</p>
                  <h3 className="text-2xl font-bold">Comprehensive Event Schedule</h3>
                </div>
                <Badge variant="outline" className="text-sm px-3">
                  {state?.schedule?.length} Sessions Scheduled
                </Badge>
              </div>
              <ScheduleTimeline schedule={state?.schedule} />
            </div>
          )}
        </section>
      </main>

      <ChatWidget planId={planId ?? undefined} />
    </div>
  );
}
