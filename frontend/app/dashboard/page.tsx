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

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, RefreshCw, AlertTriangle, Sparkles, Megaphone, Layers } from "lucide-react";

export default function DashboardPage() {
  const launchStartedRef = useRef(false);
  const [state, setState] = useState<AgentState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<
    Record<string, AgentStatus>
  >({});

  const summaryCount = (value?: number | null) => value ?? 0;
  const gtmCount = Object.keys(state?.gtm_messages ?? {}).length;

  const hasResults = Boolean(
    state &&
      (state.sponsors?.length ||
        state.speakers?.length ||
        state.venues?.length ||
        state.ticket_tiers?.length ||
        state.schedule?.length ||
        state.exhibitors?.length ||
        state.communities?.length ||
        gtmCount ||
        state.distribution_plan?.length ||
        state.total_est_revenue != null ||
        state.break_even_price != null)
  );

  const renderSummaryCard = (
    title: string,
    value: string | number,
    icon: ReactNode,
    accent?: string
  ) => (
    <div className="rounded-[1.8rem] border border-border/60 bg-card/80 p-5 shadow-xl shadow-black/5 transition-all hover:-translate-y-0.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`grid place-items-center rounded-2xl p-3 ${accent ?? "bg-primary/10 text-primary"}`}>
            {icon}
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
              {title}
            </p>
            <p className="text-2xl font-semibold tracking-tight">{value}</p>
          </div>
        </div>
      </div>
    </div>
  );

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

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-500 selection:bg-primary/20 selection:text-primary">
      <main className="max-w-7xl mx-auto px-6 py-10 space-y-10">
        <section className="rounded-[2rem] border border-border/60 bg-card/80 p-8 shadow-2xl shadow-black/5 backdrop-blur-xl">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
                MMU Dashboard
              </p>
              <h1 className="text-4xl font-heading tracking-tight text-foreground">
                Conference results in one central view
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                This dashboard surfaces the latest backend outputs, including GTM agent recommendations,
                exhibitor opportunities, venue insights, pricing, and schedule suggestions.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button variant="outline" className="gap-2" onClick={fetchOutput}>
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
              <ThemeToggle />
            </div>
          </div>

          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {renderSummaryCard(
              "Sponsors",
              summaryCount(state?.sponsors?.length),
              <Sparkles className="h-5 w-5" />, 
              "bg-amber-500/10 text-amber-500"
            )}
            {renderSummaryCard(
              "Speakers",
              summaryCount(state?.speakers?.length),
              <Brain className="h-5 w-5" />,
              "bg-cyan-500/10 text-cyan-500"
            )}
            {renderSummaryCard(
              "Exhibitors",
              summaryCount(state?.exhibitors?.length),
              <Layers className="h-5 w-5" />,
              "bg-violet-500/10 text-violet-500"
            )}
            {renderSummaryCard(
              "GTM Plans",
              Object.keys(state?.gtm_messages ?? {}).length || 0,
              <Megaphone className="h-5 w-5" />,
              "bg-emerald-500/10 text-emerald-500"
            )}
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

        <section className="grid gap-6 xl:grid-cols-[1.7fr_0.95fr]">
          <div className="space-y-6">
            <AgentLogs planId={planId ?? undefined} onAgentStatusChange={handleAgentStatus} />
            <AgentGraph agentStatuses={agentStatuses} />
          </div>
          <div className="space-y-6">
            <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                    Live GTM insight
                  </p>
                  <h3 className="text-xl font-semibold">GTM Messages</h3>
                </div>
                <Badge variant="outline" className="text-xs">
                  {Object.keys(state?.gtm_messages ?? {}).length || 0}
                </Badge>
              </div>
              {state?.gtm_messages ? (
                <div className="space-y-3">
                  {Object.entries(state?.gtm_messages ?? {}).map(([key, message]) => (
                    <div key={key} className="rounded-3xl border border-border/50 bg-muted/30 p-4">
                      <p className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
                        {key}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-foreground">
                        {message}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">GTM results will appear here once the agent completes.</p>
              )}
            </div>
          </div>
        </section>

        <section className="space-y-8">
          <div className="grid gap-6 lg:grid-cols-3">
            {((state?.sponsors?.length ?? 0) > 0 || (loading && hasResults)) && (
              <SponsorCards sponsors={state?.sponsors} loading={loading && !state?.sponsors?.length} />
            )}

            {((state?.speakers?.length ?? 0) > 0 || (loading && hasResults)) && (
              <SpeakerGrid speakers={state?.speakers} loading={loading && !state?.speakers?.length} />
            )}
          </div>

          {(state?.exhibitors?.length ?? 0) > 0 && (
            <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Exhibitor Agent</p>
                  <h3 className="text-xl font-semibold">Exhibitor opportunities</h3>
                </div>
                <Badge variant="outline" className="text-xs">
                  {state?.exhibitors?.length ?? 0}
                </Badge>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {state?.exhibitors?.map((exhibitor) => (
                  <div key={exhibitor.name} className="rounded-2xl border border-border/40 bg-muted/30 p-4 hover:bg-muted/40 transition-colors">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <p className="font-semibold text-foreground text-sm leading-tight break-words flex-1">{exhibitor.name}</p>
                      <Badge variant="outline" className="text-[11px] shrink-0">
                        {exhibitor.relevance?.toFixed?.(1) ?? exhibitor.relevance}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mb-3">
                      {exhibitor.cluster ?? 'Cluster unknown'}
                    </p>
                    {exhibitor.website && (
                      <a
                        href={exhibitor.website}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 underline"
                      >
                        Visit website
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {((state?.venues?.length ?? 0) > 0 || (loading && hasResults)) && (
            <VenueTable venues={state?.venues} loading={loading && !state?.venues?.length} />
          )}
        </section>

        <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-6">
            {(state?.ticket_tiers?.length ?? 0) > 0 && (
              <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Pricing</p>
                    <h3 className="text-xl font-semibold">Ticket tiers</h3>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {state?.ticket_tiers?.length ?? 0}
                  </Badge>
                </div>
                <PricingTiers tiers={state?.ticket_tiers} />
              </div>
            )}

            {(state?.schedule?.length ?? 0) > 0 && (
              <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Event ops</p>
                    <h3 className="text-xl font-semibold">Schedule</h3>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {state?.schedule?.length ?? 0}
                  </Badge>
                </div>
                <ScheduleTimeline schedule={state?.schedule} />
              </div>
            )}
          </div>

          <div className="space-y-6">
            {(state?.communities?.length ?? 0) > 0 && (
              <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Community GTM</p>
                    <h3 className="text-xl font-semibold">Community channels</h3>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {state?.communities?.length ?? 0}
                  </Badge>
                </div>
                <div className="space-y-3">
                  {state?.communities?.map((community) => (
                    <div key={`${community.platform}-${community.name}`} className="rounded-3xl border border-border/40 bg-muted/30 p-4">
                      <p className="text-sm font-semibold text-foreground">{community.name}</p>
                      <p className="text-sm text-muted-foreground">{community.platform} • {community.size?.toLocaleString() ?? community.size} members</p>
                      {community.invite_url && (
                        <a href={community.invite_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-sm text-primary underline">
                          Join
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(state?.distribution_plan?.length ?? 0) > 0 && (
              <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Channel plan</p>
                    <h3 className="text-xl font-semibold">Distribution plan</h3>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {state?.distribution_plan?.length ?? 0}
                  </Badge>
                </div>
                <ul className="space-y-3">
                  {state?.distribution_plan?.map((item, index) => (
                    <li key={`${item}-${index}`} className="rounded-3xl bg-muted/30 p-4 text-sm leading-6 text-foreground">
                      <span className="font-semibold text-primary">{index + 1}.</span> {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(state?.conflicts?.length ?? 0) > 0 && (
              <div className="rounded-[2rem] border border-border/60 bg-card/80 p-6 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Validation</p>
                    <h3 className="text-xl font-semibold">Conflicts</h3>
                  </div>
                  <Badge variant="outline" className="text-xs text-destructive">
                    {state?.conflicts?.length ?? 0}
                  </Badge>
                </div>
                <div className="space-y-3 text-sm text-foreground">
                  {state?.conflicts?.map((conflict, index) => (
                    <div key={`${conflict}-${index}`} className="rounded-3xl bg-muted/30 p-4 border border-border/40">
                      {conflict}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="space-y-8">
          <Separator />
          <div className="grid gap-6 lg:grid-cols-2">
            <WhatIfPanel tiers={state?.ticket_tiers} />
            <RefinementPanel onRefined={handleRefined} />
          </div>
        </section>
      </main>
    </div>
  );
}
