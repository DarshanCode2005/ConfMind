"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { type EventConfigInput } from "@/lib/api";
import {
  Brain,
  Globe,
  Users,
  DollarSign,
  Calendar,
  ArrowRight,
  ArrowLeft,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { ALL_COUNTRIES } from "@/lib/countries";

const CATEGORIES = [
  "AI & Machine Learning",
  "Web3 & Blockchain",
  "ClimateTech",
  "SaaS & Enterprise",
  "Music & Entertainment",
  "Sports & Fitness",
  "HealthTech",
  "Fintech",
];

const TOTAL_STEPS = 5;

const STEP_META = [
  { label: "Category", icon: Brain },
  { label: "Geography", icon: Globe },
  { label: "Audience", icon: Users },
  { label: "Budget", icon: DollarSign },
  { label: "Dates", icon: Calendar },
];

const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

function getTodayInputValue(): string {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

export default function InputWizard() {
  const router = useRouter();
  const todayInputValue = getTodayInputValue();

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  const [category, setCategory] = useState("");
  const [geography, setGeography] = useState("");
  const [currencySymbol, setCurrencySymbol] = useState("$");
  const [audienceSize, setAudienceSize] = useState(500);
  const [budgetVal, setBudgetVal] = useState(50_000);
  const [eventDates, setEventDates] = useState("");

  const formatBudget = (val: number): string => {
    if (val >= 1_000_000) return `${currencySymbol}${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `${currencySymbol}${(val / 1_000).toFixed(0)}k`;
    return `${currencySymbol}${val.toLocaleString()}`;
  };

  const handleGeographyChange = (val: string | null) => {
    if (!val) return;
    setGeography(val);
    const selected = ALL_COUNTRIES.find((c) => c.value === val);
    setCurrencySymbol(selected?.symbol ?? "$USD");
  };

  const handleDateChange = (nextDate: string) => {
    if (nextDate && nextDate < todayInputValue) {
      setEventDates("");
      toast.error("Please choose today or a future date.", {
        description: "Past dates cannot be used for a new conference plan.",
      });
      return;
    }

    setEventDates(nextDate);
  };

  const canAdvance = (): boolean => {
    switch (step) {
      case 0:
        return category !== "";
      case 1:
        return geography !== "";
      case 2:
        return audienceSize >= 50;
      case 3:
        return budgetVal >= 5_000;
      case 4:
        return eventDates !== "" && eventDates >= todayInputValue;
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    if (eventDates < todayInputValue) {
      toast.error("Please choose today or a future date.");
      return;
    }

    const input: EventConfigInput = {
      category,
      geography,
      audience_size: audienceSize,
      budget_usd: budgetVal,
      event_dates: eventDates,
    };

    setLoading(true);
    try {
      sessionStorage.setItem("confmind_config", JSON.stringify(input));
      sessionStorage.removeItem("confmind_plan_id");
      sessionStorage.setItem("confmind_run_on_dashboard", "1");
      router.push("/dashboard");
    } catch (err) {
      toast.error("Failed to prepare plan launch.", {
        description: err instanceof Error ? err.message : String(err),
      });
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-16 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_14%_12%,hsl(var(--primary)/0.18),transparent_24rem),radial-gradient(circle_at_86%_18%,hsl(var(--secondary)/0.16),transparent_26rem),linear-gradient(180deg,hsl(var(--background)),hsl(var(--muted)/0.55))]" />
      <div className="absolute top-6 right-6">
        <ThemeToggle />
      </div>

      <div className="mb-10 text-center max-w-3xl space-y-5">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary shadow-sm shadow-primary/10">
          <Brain className="w-4 h-4" />
          AI Conference Setup
        </div>
        <div>
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-foreground">
            Start your conference plan with a clean, modern setup
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Answer a few guided questions and launch your AI-driven event plan with sponsors, speakers, venues, pricing, and GTM recommendations.
          </p>
        </div>
      </div>

      <div className="w-full max-w-3xl mb-8 rounded-[2rem] border border-border/70 bg-card/90 p-5 shadow-2xl shadow-slate-900/5 backdrop-blur-xl">
        <div className="flex flex-col gap-4 rounded-3xl bg-muted/80 p-5 shadow-inner shadow-black/5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">
              Step {step + 1} of {TOTAL_STEPS}
            </p>
            <h2 className="text-xl font-semibold text-foreground">
              {STEP_META[step].label}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm">
              {(() => {
                const StepIcon = STEP_META[step].icon;
                return <StepIcon className="h-5 w-5" />;
              })()}
            </span>
            <span className="text-sm font-medium text-foreground">
              {STEP_META[step].label}
            </span>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-5">
          {STEP_META.map((s, i) => {
            const progress = i < step ? "bg-primary text-primary-foreground" : i === step ? "bg-secondary text-secondary-foreground" : "bg-muted text-muted-foreground";
            return (
              <div key={s.label} className={`rounded-3xl border border-border/60 px-3 py-4 text-center text-[11px] font-semibold uppercase tracking-[0.2em] ${progress}`}>
                {s.label}
              </div>
            );
          })}
        </div>
      </div>

      <Card className="w-full max-w-3xl border border-border/80 bg-card/95 shadow-[0_28px_80px_-38px_rgba(15,23,42,0.6)]">
        <CardContent className="pt-10 pb-10 px-8 md:px-10">
          {step === 0 && (
            <div className="space-y-6">
              <div className="space-y-2">
                <p className="text-sm uppercase tracking-[0.32em] text-muted-foreground">
                  Choose your event focus
                </p>
                <h3 className="text-2xl font-semibold text-foreground">
                  What kind of conference is this?
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">
                  The agents will optimize sponsor, speaker, and venue searches for this theme.
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setCategory(cat)}
                    className={`group relative rounded-[1.75rem] border p-5 text-left transition-all duration-200 shadow-sm ${
                      category === cat
                        ? "border-primary bg-primary/10 text-primary shadow-primary/10"
                        : "border-border bg-card hover:border-primary/60 hover:bg-primary/5 text-foreground"
                    }`}
                  >
                    <span className="block text-base font-semibold mb-2">{cat}</span>
                    <span className="text-sm leading-6 text-muted-foreground">
                      Tailor the event experience with this focus area.
                    </span>
                    <span className={`pointer-events-none absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl border ${category === cat ? "border-primary bg-primary text-primary-foreground" : "border-border bg-muted text-muted-foreground"}`}>
                      {category === cat ? <CheckCircle2 className="h-4 w-4" /> : <Brain className="h-4 w-4" />}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-6">
              <div className="space-y-2">
                <p className="text-sm uppercase tracking-[0.32em] text-muted-foreground">
                  Choose a location
                </p>
                <h3 className="text-2xl font-semibold text-foreground">
                  Which geography should the agents focus on?
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">
                  Select your target country to narrow venue and local community searches.
                </p>
              </div>
              <div className="space-y-4">
                <Label className="mb-2 block text-sm font-medium text-foreground">Select a country</Label>
                <Select value={geography} onValueChange={handleGeographyChange}>
                  <SelectTrigger
                    id="geography-select"
                    className="w-full h-14 rounded-3xl border border-border bg-background px-4 text-base shadow-sm"
                  >
                    <SelectValue placeholder="Choose a country" />
                  </SelectTrigger>
                  <SelectContent
                    side="bottom"
                    align="start"
                    sideOffset={8}
                    alignItemWithTrigger={false}
                    className="z-50 rounded-3xl border border-border bg-card shadow-lg"
                    style={{ maxHeight: 300 }}
                  >
                    {ALL_COUNTRIES.map((g) => (
                      <SelectItem key={g.value} value={g.value}>
                        {g.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="overflow-hidden rounded-[1.75rem] border border-border/60 bg-muted/70 shadow-inner">
                <ComposableMap projection="geoMercator" className="w-full" style={{ height: 280 }} projectionConfig={{ scale: 100, center: [0, 20] }}>
                  <Geographies geography={geoUrl}>
                    {({ geographies }) =>
                      geographies.map((geo) => {
                        const geoName = geo.properties.name;
                        const isSelected = geography === geoName || (geography === "United States" && geoName === "United States of America");
                        const isSelectable = ALL_COUNTRIES.some(c => c.value === geoName || (c.value === "United States" && geoName === "United States of America"));

                        return (
                          <Geography
                            key={geo.rsmKey}
                            geography={geo}
                            onClick={() => {
                              if (isSelectable) {
                                const targetVal = geoName === "United States of America" ? "United States" : geoName;
                                handleGeographyChange(targetVal);
                              }
                            }}
                            style={{
                              default: {
                                fill: isSelected ? "hsl(var(--primary))" : isSelectable ? "hsl(var(--primary) / 0.28)" : "hsl(var(--muted-foreground) / 0.18)",
                                outline: "none",
                                stroke: "hsl(var(--border))",
                                strokeWidth: 0.6,
                                cursor: isSelectable ? "pointer" : "default"
                              },
                              hover: {
                                fill: isSelectable ? "hsl(var(--secondary))" : "hsl(var(--muted-foreground) / 0.18)",
                                outline: "none",
                                stroke: "hsl(var(--border))",
                                strokeWidth: 0.6,
                                cursor: isSelectable ? "pointer" : "default"
                              },
                              pressed: {
                                fill: "hsl(var(--primary))",
                                outline: "none"
                              }
                            }}
                          />
                        );
                      })
                    }
                  </Geographies>
                </ComposableMap>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <div className="space-y-2">
                <p className="text-sm uppercase tracking-[0.32em] text-muted-foreground">
                  Audience sizing
                </p>
                <h3 className="text-2xl font-semibold text-foreground">
                  How many attendees do you expect?
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">
                  This helps agents design sponsorship value, venue capacity, and pricing tiers.
                </p>
              </div>
              <div className="rounded-[1.75rem] border border-border/60 bg-muted/60 p-6 shadow-sm">
                <div className="flex items-center justify-between gap-4 mb-5">
                  <Label className="text-sm">Audience size</Label>
                  <span className="text-3xl font-bold text-primary tabular-nums">
                    {audienceSize.toLocaleString()}
                  </span>
                </div>
                <Slider
                  id="audience-slider"
                  min={50}
                  max={5000}
                  step={50}
                  value={[audienceSize]}
                  onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v as number; if (typeof val === "number") setAudienceSize(val); }}
                  className="mb-3"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>50</span>
                  <span>2,500</span>
                  <span>5,000</span>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6">
              <div className="space-y-2">
                <p className="text-sm uppercase tracking-[0.32em] text-muted-foreground">
                  Budget planning
                </p>
                <h3 className="text-2xl font-semibold text-foreground">
                  What is your total event budget?
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">
                  This helps define sponsorship targets, venue tiers, and revenue forecasts.
                </p>
              </div>
              <div className="rounded-[1.75rem] border border-border/60 bg-muted/60 p-6 shadow-sm">
                <div className="flex items-center justify-between gap-4 mb-5">
                  <Label className="text-sm">Budget amount</Label>
                  <span className="text-3xl font-bold text-primary tabular-nums">
                    {formatBudget(budgetVal)}
                  </span>
                </div>
                <Slider
                  id="budget-slider"
                  min={5_000}
                  max={500_000}
                  step={5_000}
                  value={[budgetVal]}
                  onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v as number; if (typeof val === "number") setBudgetVal(val); }}
                  className="mb-3"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{formatBudget(5_000)}</span>
                  <span>{formatBudget(250_000)}</span>
                  <span>{formatBudget(500_000)}</span>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  Budget values follow the selected country currency.
                </p>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6">
              <div className="space-y-2">
                <p className="text-sm uppercase tracking-[0.32em] text-muted-foreground">
                  Schedule kickoff
                </p>
                <h3 className="text-2xl font-semibold text-foreground">
                  When will your conference happen?
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">
                  The event ops agent uses this to create a realistic agenda and timeline.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-[1fr_auto] items-end">
                <div>
                  <Label htmlFor="event-date" className="mb-2 block text-sm font-medium text-foreground">
                    Event date range
                  </Label>
                  <Input
                    id="event-date"
                    type="date"
                    min={todayInputValue}
                    value={eventDates}
                    onChange={(e) => handleDateChange(e.target.value)}
                    className="h-14 text-base w-full rounded-3xl border border-border bg-background px-4"
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    Choose today or a future date. Past dates are disabled.
                  </p>
                </div>
                {eventDates && (
                  <div className="rounded-[1.75rem] border border-border/60 bg-muted/55 p-4 shadow-sm">
                    <p className="text-sm font-semibold text-foreground mb-3">
                      Plan summary
                    </p>
                    <div className="space-y-2 text-sm text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Category</span>
                        <span className="text-foreground font-medium">{category}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Geography</span>
                        <span className="text-foreground font-medium">{geography}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Audience</span>
                        <span className="text-foreground font-medium">{audienceSize.toLocaleString()} attendees</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Budget</span>
                        <span className="text-foreground font-medium">{formatBudget(budgetVal)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Date</span>
                        <span className="text-foreground font-medium">{eventDates}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Button
              variant="ghost"
              onClick={() => setStep((s) => s - 1)}
              disabled={step === 0}
              className="gap-2 rounded-3xl px-5 py-3"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>

            {step < TOTAL_STEPS - 1 ? (
              <Button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canAdvance()}
                className="gap-2 rounded-3xl px-6 py-3 shadow-sm"
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                id="launch-plan-btn"
                onClick={handleSubmit}
                disabled={!canAdvance() || loading}
                className="gap-2 rounded-3xl px-8 py-3 bg-primary text-primary-foreground shadow-md shadow-primary/30 hover:bg-primary/90"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Launching agents
                  </>
                ) : (
                  <>
                    Launch AI Agents
                    <Brain className="w-4 h-4" />
                  </>
                )}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <p className="mt-8 max-w-2xl text-center text-sm leading-6 text-muted-foreground">
        8 specialized agents will run in parallel for sponsor discovery, speaker enrichment, venue scoring,
        pricing optimization, and revenue planning.
      </p>
    </div>
  );
}
