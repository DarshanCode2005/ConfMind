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
    <div className="min-h-screen bg-background">
      {/* Top Bar */}
      <div className="fixed top-0 left-0 right-0 h-16 border-b border-border/60 bg-card/50 flex items-center justify-between px-8 z-50">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Brain className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h2 className="font-bold text-sm">ConfMind</h2>
          </div>
        </div>
        <ThemeToggle />
      </div>

      {/* Main Content */}
      <main className="min-h-screen flex flex-col items-center justify-center px-8 py-16 pt-28">
        {/* Header Section */}
        <section className="rounded-[2rem] border border-border/60 bg-card/80 p-8 shadow-sm max-w-4xl w-full mb-12">
          <div className="grid gap-8 xl:grid-cols-[1fr_auto]">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground mb-2">
                Setup Wizard
              </p>
              <h1 className="text-4xl font-bold tracking-tight mb-2">
                Conference Configuration
              </h1>
              <p className="text-muted-foreground text-sm max-w-md leading-6">
                Define your event parameters. 8 specialized AI agents will search for sponsors, speakers, venues, and optimize pricing.
              </p>
            </div>
            {/* Progress indicator */}
            <div className="flex flex-col items-end justify-start gap-3">
              <div className="text-right">
                <p className="text-sm font-medium text-foreground">{step + 1} of {TOTAL_STEPS}</p>
                <p className="text-xs text-muted-foreground">Steps</p>
              </div>
              <div className="w-24 h-24 rounded-full border-4 border-primary/20 flex items-center justify-center bg-primary/5">
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary">{Math.round(((step + 1) / TOTAL_STEPS) * 100)}%</p>
                  <p className="text-[10px] text-muted-foreground">Complete</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Step Icons */}
        <div className="w-full max-w-4xl mb-8">
          <div className="flex items-center justify-between gap-2">
            {STEP_META.map((s, i) => {
              const Icon = s.icon;
              const done = i < step;
              const active = i === step;
              return (
                <div key={s.label} className="flex flex-col items-center gap-2 flex-1">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                      done
                        ? "bg-primary border-primary text-primary-foreground"
                        : active
                          ? "border-secondary bg-secondary/25 text-foreground"
                          : "border-border bg-card text-muted-foreground"
                    }`}
                  >
                    {done ? (
                      <CheckCircle2 className="w-5 h-5" />
                    ) : (
                      <Icon className="w-5 h-5" />
                    )}
                  </div>
                  <span className={`text-xs font-medium text-center ${active ? "text-primary" : done ? "text-foreground" : "text-muted-foreground"}`}>
                    {s.label}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="relative h-1 bg-muted rounded-full overflow-hidden border border-border/40 mt-4">
            <div
              className="absolute left-0 top-0 h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: `${((step) / (TOTAL_STEPS - 1)) * 100}%` }}
            />
          </div>
        </div>

        {/* Form Card */}
        <Card className="w-full max-w-4xl bg-card/80 border-border/60 shadow-sm">
          <CardContent className="pt-8 pb-8 px-8">
          {step === 0 && (
            <div>
              <h2 className="text-2xl font-semibold mb-2">
                What type of event are you planning?
              </h2>
              <p className="text-muted-foreground text-sm mb-8">
                Agents will tailor sponsor and speaker searches to this domain.
              </p>
              <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategory(cat)}
                    className={`h-auto py-4 px-4 text-left rounded-lg border-2 transition-all duration-200 ${
                      category === cat
                        ? "bg-primary/10 border-primary text-primary font-semibold"
                        : "bg-card border-border/40 text-foreground hover:border-primary/60 hover:bg-muted/50"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="flex flex-col gap-6">
              <div className="relative z-30">
                <h2 className="text-2xl font-semibold mb-2">
                  Where will this event be held?
                </h2>
                <p className="text-muted-foreground text-sm mb-6">
                  Venue agents will search within this region.
                </p>
                <Label className="mb-3 block text-sm font-medium">Select a country</Label>
                <Select value={geography} onValueChange={handleGeographyChange}>
                  <SelectTrigger
                    id="geography-select"
                    className="w-full h-12 rounded-lg border-border bg-muted/30 text-base"
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

              <div className="w-full rounded-lg overflow-hidden border border-border/60 bg-muted/20 relative z-0">
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
              <h2 className="text-2xl font-semibold mb-2">
                How many attendees are you targeting?
              </h2>
              <p className="text-muted-foreground text-sm mb-8">
                Pricing and venue agents use this to calculate capacity and revenue tiers.
              </p>
              <div className="rounded-xl border border-border/60 bg-muted/30 p-6 mb-6">
                <div className="flex items-center justify-between">
                  <Label className="text-sm text-muted-foreground">Audience Size</Label>
                  <span className="text-4xl font-bold text-primary tabular-nums">
                    {audienceSize.toLocaleString()}
                  </span>
                </div>
              </div>
              <Slider
                id="audience-slider"
                min={50}
                max={5000}
                step={50}
                value={[audienceSize]}
                onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v as number; if (typeof val === "number") setAudienceSize(val); }}
                className="mb-4"
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
              <h2 className="text-2xl font-semibold mb-2">
                What is your total event budget?
              </h2>
              <p className="text-muted-foreground text-sm mb-8">
                Used to filter venues, plan sponsorship targets, and validate break even.
              </p>
              <div className="rounded-xl border border-border/60 bg-muted/30 p-6 mb-6">
                <div className="flex items-center justify-between">
                  <Label className="text-sm text-muted-foreground">Budget Amount</Label>
                  <span className="text-4xl font-bold text-primary tabular-nums">
                    {formatBudget(budgetVal)}
                  </span>
                </div>
              </div>
              <Slider
                id="budget-slider"
                min={5_000}
                max={500_000}
                step={5_000}
                value={[budgetVal]}
                onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v as number; if (typeof val === "number") setBudgetVal(val); }}
                className="mb-4"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{formatBudget(5_000)}</span>
                <span>{formatBudget(250_000)}</span>
                <span>{formatBudget(500_000)}</span>
              </div>
              <p className="mt-4 text-xs text-muted-foreground">
                Budget values follow the selected country currency.
              </p>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-2xl font-semibold mb-2">
                When will the event take place?
              </h2>
              <p className="text-muted-foreground text-sm mb-8">
                The Event Ops agent will build a schedule around this date.
              </p>
              <Label htmlFor="event-date" className="block text-sm mb-3 font-medium">
                Event date
              </Label>
              <Input
                id="event-date"
                type="date"
                min={todayInputValue}
                value={eventDates}
                onChange={(e) => handleDateChange(e.target.value)}
                className="h-12 text-base w-full mb-6 rounded-lg"
              />
              <p className="text-xs text-muted-foreground mb-6">
                Choose today or a future date. Past dates are disabled.
              </p>
              {eventDates && (
                <div className="rounded-xl border border-border/60 bg-muted/30 p-6">
                  <p className="font-semibold text-foreground mb-4 flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-primary" />
                    Ready to launch your plan
                  </p>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Category</p>
                      <p className="font-medium text-foreground">{category}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Geography</p>
                      <p className="font-medium text-foreground">{geography}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Audience</p>
                      <p className="font-medium text-foreground">{audienceSize.toLocaleString()} attendees</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Budget</p>
                      <p className="font-medium text-foreground">{formatBudget(budgetVal)}</p>
                    </div>
                    <div className="col-span-2">
                      <p className="text-muted-foreground text-xs mb-1">Event Date</p>
                      <p className="font-medium text-foreground">{new Date(eventDates).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between mt-8 gap-4">
            <Button
              variant="outline"
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
                className="gap-2 px-6 rounded-lg"
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                id="launch-plan-btn"
                onClick={handleSubmit}
                disabled={!canAdvance() || loading}
                className="gap-2 px-8 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Launching...
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
    </main>
    </div>
  );
}

