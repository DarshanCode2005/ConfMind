"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { runPlan, type EventConfigInput } from "@/lib/api";
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

const GEOGRAPHIES = [
  { value: "USA", label: "🇺🇸 United States" },
  { value: "Europe", label: "🇪🇺 Europe" },
  { value: "India", label: "🇮🇳 India" },
  { value: "Singapore", label: "🇸🇬 Singapore" },
  { value: "APAC", label: "🌏 Asia-Pacific" },
  { value: "MENA", label: "🌍 Middle East & Africa" },
  { value: "LatAm", label: "🌎 Latin America" },
];

const TOTAL_STEPS = 5;

const STEP_META = [
  { label: "Category", icon: Brain },
  { label: "Geography", icon: Globe },
  { label: "Audience", icon: Users },
  { label: "Budget", icon: DollarSign },
  { label: "Dates", icon: Calendar },
];

function formatBudget(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}k`;
  return `$${val}`;
}

export default function InputWizard() {
  const router = useRouter();

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  const [category, setCategory] = useState("");
  const [geography, setGeography] = useState("");
  const [audienceSize, setAudienceSize] = useState(500);
  const [budgetUsd, setBudgetUsd] = useState(50_000);
  const [eventDates, setEventDates] = useState("");

  const canAdvance = (): boolean => {
    switch (step) {
      case 0:
        return category !== "";
      case 1:
        return geography !== "";
      case 2:
        return audienceSize >= 50;
      case 3:
        return budgetUsd >= 5_000;
      case 4:
        return eventDates !== "";
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    const input: EventConfigInput = {
      category,
      geography,
      audience_size: audienceSize,
      budget_usd: budgetUsd,
      event_dates: eventDates,
    };

    setLoading(true);
    try {
      await runPlan(input);
      // Store config in sessionStorage for refinement panel
      sessionStorage.setItem("confmind_config", JSON.stringify(input));
      router.push("/dashboard");
    } catch (err) {
      toast.error("Failed to start planning. Is the backend running?", {
        description: err instanceof Error ? err.message : String(err),
      });
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-16">
      {/* Header */}
      <div className="mb-12 text-center">
        <div className="inline-flex items-center gap-2 bg-primary/10 border border-primary/20 rounded-full px-4 py-1.5 mb-6">
          <Brain className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-primary">
            AI-Powered Conference Planner
          </span>
        </div>
        <h1 className="text-5xl font-bold tracking-tight mb-3 bg-gradient-to-br from-foreground to-muted-foreground bg-clip-text text-transparent">
          Plan your conference
          <br />
          with AI agents
        </h1>
        <p className="text-muted-foreground text-lg max-w-md mx-auto">
          8 specialized agents working in parallel to find sponsors, speakers,
          venues, and more — in minutes.
        </p>
      </div>

      {/* Step indicator */}
      <div className="w-full max-w-2xl mb-8">
        <div className="flex items-center justify-between mb-3">
          {STEP_META.map((s, i) => {
            const Icon = s.icon;
            const done = i < step;
            const active = i === step;
            return (
              <div key={s.label} className="flex flex-col items-center gap-1">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                    done
                      ? "bg-primary border-primary text-primary-foreground"
                      : active
                        ? "border-primary text-primary bg-primary/10"
                        : "border-border text-muted-foreground"
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
        {/* Progress bar */}
        <div className="relative h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="absolute left-0 top-0 h-full bg-primary rounded-full transition-all duration-500"
            style={{ width: `${((step) / (TOTAL_STEPS - 1)) * 100}%` }}
          />
        </div>
      </div>

      {/* Card */}
      <Card className="w-full max-w-2xl border-border/50 shadow-2xl">
        <CardContent className="pt-8 pb-8 px-8">
          {/* Step 0 — Category */}
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
                    className={`h-auto py-3 px-4 text-left justify-start transition-all duration-200 ${
                      category === cat
                        ? "ring-2 ring-primary ring-offset-2 ring-offset-background"
                        : "hover:border-primary/50"
                    }`}
                    onClick={() => setCategory(cat)}
                  >
                    {cat}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Step 1 — Geography */}
          {step === 1 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                Where will this event be held?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                Venue agents will search within this region.
              </p>
              <Label className="mb-2 block">Select a region</Label>
              <Select value={geography} onValueChange={(v) => { if (v) setGeography(v); }}>
                <SelectTrigger id="geography-select" className="w-full h-12 text-base">
                  <SelectValue placeholder="Choose a region..." />
                </SelectTrigger>
                <SelectContent>
                  {GEOGRAPHIES.map((g) => (
                    <SelectItem key={g.value} value={g.value}>
                      {g.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Step 2 — Audience Size */}
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
                onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v; if (typeof val === "number") setAudienceSize(val); }}
                className="mb-3"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>50</span>
                <span>2,500</span>
                <span>5,000</span>
              </div>
            </div>
          )}

          {/* Step 3 — Budget */}
          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                What is your total event budget?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                Used to filter venues, plan sponsorship targets, and validate
                break-even.
              </p>
              <div className="flex items-center justify-between mb-4">
                <Label>Budget (USD)</Label>
                <span className="text-3xl font-bold text-primary tabular-nums">
                  {formatBudget(budgetUsd)}
                </span>
              </div>
              <Slider
                id="budget-slider"
                min={5_000}
                max={500_000}
                step={5_000}
                value={[budgetUsd]}
                onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v; if (typeof val === "number") setBudgetUsd(val); }}
                className="mb-3"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>$5k</span>
                <span>$250k</span>
                <span>$500k</span>
              </div>
            </div>
          )}

          {/* Step 4 — Dates */}
          {step === 4 && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                When will the event take place?
              </h2>
              <p className="text-muted-foreground text-sm mb-6">
                The Event Ops agent will build a schedule around this date.
              </p>
              <Label htmlFor="event-date" className="mb-2 block">
                Event date / range
              </Label>
              <Input
                id="event-date"
                type="date"
                value={eventDates}
                onChange={(e) => setEventDates(e.target.value)}
                className="h-12 text-base w-full"
              />
              {/* Summary */}
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
                    <span className="font-medium">{formatBudget(budgetUsd)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Date</span>
                    <span className="font-medium">{eventDates}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8">
            <Button
              variant="ghost"
              onClick={() => setStep((s) => s - 1)}
              disabled={step === 0}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>

            {step < TOTAL_STEPS - 1 ? (
              <Button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canAdvance()}
                className="gap-2 px-6"
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                id="launch-plan-btn"
                onClick={handleSubmit}
                disabled={!canAdvance() || loading}
                className="gap-2 px-8 bg-primary hover:bg-primary/90"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Launching agents...
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

      {/* Footer note */}
      <p className="mt-8 text-xs text-muted-foreground text-center max-w-sm">
        8 specialized agents will run in parallel — sponsor discovery, speaker
        enrichment, venue scoring, pricing optimization, and more.
      </p>
    </div>
  );
}
