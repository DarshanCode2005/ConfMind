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
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_16%_10%,hsl(var(--primary)/0.12),transparent_30rem),radial-gradient(circle_at_86%_18%,hsl(var(--secondary)/0.12),transparent_28rem),linear-gradient(180deg,hsl(var(--background)),hsl(var(--muted)/0.46))]" />
      <div className="absolute top-6 right-6">
        <ThemeToggle />
      </div>

      <div className="mb-12 text-center max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-lg border border-primary/25 bg-linear-to-r from-primary/10 via-secondary/15 to-accent px-4 py-1.5 mb-6 shadow-sm">
          <Brain className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-primary">
            AI Powered Conference Planner
          </span>
        </div>
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4 text-foreground">
          Plan your <span className="text-primary">conference</span>
          <br />
          with <span className="text-chart-4">AI agents</span>
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto leading-7">
          8 specialized agents working in parallel to find sponsors, speakers,
          venues, pricing, and revenue opportunities in minutes.
        </p>
      </div>

      <div className="w-full max-w-2xl mb-8">
        <div className="flex items-center justify-between mb-3 gap-2">
          {STEP_META.map((s, i) => {
            const Icon = s.icon;
            const done = i < step;
            const active = i === step;
            return (
              <div key={s.label} className="flex flex-col items-center gap-1">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                    done
                      ? "bg-primary border-primary text-primary-foreground shadow-md shadow-primary/20"
                      : active
                        ? "border-secondary text-foreground bg-secondary/25 shadow-sm"
                        : "border-border bg-card text-muted-foreground"
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                </div>
                <span
                  className={`text-xs font-medium ${active ? "text-primary" : done ? "text-foreground" : "text-muted-foreground"}`}
                >
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
        <div className="relative h-2 bg-muted rounded-full overflow-hidden border border-border/70">
          <div
            className="absolute left-0 top-0 h-full bg-linear-to-r from-primary via-secondary to-chart-4 rounded-full transition-all duration-500"
            style={{ width: `${((step) / (TOTAL_STEPS - 1)) * 100}%` }}
          />
        </div>
      </div>

      <Card className="w-full max-w-2xl border-t-4 border-t-primary bg-card shadow-[0_28px_80px_-38px_rgba(15,23,42,0.62)]">
        <CardContent className="pt-9 pb-9 px-8 md:px-10">
          {step === 0 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                What type of event are you planning?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                Agents will tailor sponsor and speaker searches to this domain.
              </p>
              <div className="grid grid-cols-2 gap-3">
                {CATEGORIES.map((cat) => (
                  <Button
                    key={cat}
                    variant={category === cat ? "default" : "outline"}
                    className={`h-auto py-3 px-4 text-left justify-start transition-all duration-200 rounded-lg border ${
                      category === cat
                        ? "bg-primary text-primary-foreground border-transparent ring-2 ring-secondary/60 ring-offset-2 ring-offset-background shadow-md shadow-primary/20"
                        : "bg-card border-input border-l-primary/60 border-l-4 text-foreground hover:border-primary/60 hover:bg-primary/10"
                    }`}
                    onClick={() => setCategory(cat)}
                  >
                    {cat}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="flex flex-col gap-6">
              <div className="relative z-30">
                <h2 className="text-xl font-semibold mb-2">
                  Where will this event be held?
                </h2>
                <p className="text-muted-foreground text-sm mb-4">
                  Venue agents will search within this region.
                </p>
                <Label className="mb-2 block">Select a country</Label>
                <Select value={geography} onValueChange={handleGeographyChange}>
                  <SelectTrigger
                    id="geography-select"
                    className="w-full h-12 rounded-lg border-input bg-card text-base shadow-sm"
                  >
                    <SelectValue placeholder="Choose a country" />
                  </SelectTrigger>
                  <SelectContent
                    side="bottom"
                    align="start"
                    sideOffset={8}
                    alignItemWithTrigger={false}
                    className="z-100 rounded-lg"
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

              <div className="w-full rounded-lg overflow-hidden border border-border bg-muted/45 relative z-0 shadow-inner">
                <ComposableMap projection="geoMercator" className="w-full" style={{ height: 250 }} projectionConfig={{ scale: 100, center: [0, 20] }}>
                  <Geographies geography={geoUrl}>
                    {({ geographies }) =>
                      geographies.map((geo) => {
                        const geoName = geo.properties.name;
                        // World-atlas json sometimes uses "United States of America"
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
                                fill: isSelected ? "hsl(var(--primary))" : isSelectable ? "hsl(var(--primary) / 0.28)" : "hsl(var(--muted-foreground) / 0.16)",
                                outline: "none",
                                stroke: "hsl(var(--card))",
                                strokeWidth: 0.7,
                                cursor: isSelectable ? "pointer" : "default"
                              },
                              hover: {
                                fill: isSelectable ? "hsl(var(--secondary))" : "hsl(var(--muted-foreground) / 0.16)",
                                outline: "none",
                                stroke: "hsl(var(--card))",
                                strokeWidth: 0.7,
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
                <div className="absolute bottom-2 right-2 flex gap-2">
                  <span className="text-[10px] text-foreground flex items-center gap-1 rounded-lg bg-card px-2 py-1 border border-border shadow-sm">
                    <span className="w-2 h-2 rounded-full bg-primary/40 inline-block"></span> Supported regions
                  </span>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                How many attendees are you targeting?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                Pricing and venue agents use this to calculate capacity and
                revenue tiers.
              </p>
              <div className="flex items-center justify-between mb-4">
                <Label>Audience Size</Label>
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
          )}

          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                What is your total event budget?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                Used to filter venues, plan sponsorship targets, and validate
                break even.
              </p>
              <div className="flex items-center justify-between mb-4">
                <Label>Budget Amount</Label>
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
          )}

          {step === 4 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                When will the event take place?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                The Event Ops agent will build a schedule around this date.
              </p>
              <Label htmlFor="event-date" className="mb-2 block">
                Event date range
              </Label>
              <Input
                id="event-date"
                type="date"
                min={todayInputValue}
                value={eventDates}
                onChange={(e) => handleDateChange(e.target.value)}
                className="h-12 text-base w-full"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Choose today or a future date. Past dates are disabled.
              </p>
              {eventDates && (
                <div className="mt-6 p-4 rounded-lg bg-muted/50 border border-border/50 space-y-2 text-sm">
                  <p className="font-semibold text-foreground mb-3">
                    Ready to launch your plan
                  </p>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Category</span>
                    <span className="font-medium">{category}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Geography</span>
                    <span className="font-medium">{geography}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Audience</span>
                    <span className="font-medium">
                      {audienceSize.toLocaleString()} attendees
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Budget</span>
                    <span className="font-medium">{formatBudget(budgetVal)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Date</span>
                    <span className="font-medium">{eventDates}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between mt-8">
            <Button
              variant="ghost"
              onClick={() => setStep((s) => s - 1)}
              disabled={step === 0}
              className="gap-2 rounded-lg"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>

            {step < TOTAL_STEPS - 1 ? (
              <Button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canAdvance()}
                className="gap-2 px-6 rounded-lg shadow-sm"
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                id="launch-plan-btn"
                onClick={handleSubmit}
                disabled={!canAdvance() || loading}
                className="gap-2 px-8 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground shadow-md shadow-primary/20"
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

      <p className="mt-8 text-xs text-muted-foreground text-center max-w-sm">
        8 specialized agents will run in parallel for sponsor discovery, speaker
        enrichment, venue scoring, pricing optimization, and more.
      </p>
    </div>
  );
}
