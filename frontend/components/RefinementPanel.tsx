"use client";

import { useState } from "react";
import { toast } from "sonner";
import { runPlan, type EventConfigInput, type AgentState } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  Loader2,
  Crown,
  MapPin,
  Tag,
  RefreshCw,
} from "lucide-react";

interface RefinementPanelProps {
  onRefined: (newState: AgentState) => void;
}

const QUICK_ACTIONS = [
  {
    label: "More premium sponsors",
    icon: Crown,
    prompt:
      "Focus on finding Gold and Silver tier sponsors from top Fortune 500 companies. Prioritize relevance score above 8.",
    loadingMsg: "Updating sponsors...",
  },
  {
    label: "Only local speakers",
    icon: MapPin,
    prompt:
      "Prioritize speakers who are based in the same region as the event. Avoid international travel costs.",
    loadingMsg: "Filtering speakers...",
  },
  {
    label: "Reduce ticket price",
    icon: Tag,
    prompt:
      "Reduce all ticket tier prices by 20% while maintaining maximum attendance forecasts.",
    loadingMsg: "Recalculating pricing...",
  },
];

export default function RefinementPanel({ onRefined }: RefinementPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("Refining plan...");

  const handleRefine = async (customPrompt?: string, customMsg?: string) => {
    const finalPrompt = customPrompt ?? prompt;
    if (!finalPrompt.trim()) {
      toast.error("Please describe what you'd like to change.");
      return;
    }

    // Load saved config from session
    const stored = sessionStorage.getItem("confmind_config");
    if (!stored) {
      toast.error("No config found. Please go back and re-submit your plan.");
      return;
    }

    const baseConfig = JSON.parse(stored) as EventConfigInput;
    const refinedConfig: EventConfigInput = {
      ...baseConfig,
      refinement_prompt: finalPrompt,
    };

    setLoadingMsg(customMsg ?? "Refining plan...");
    setLoading(true);

    try {
      const result = await runPlan(refinedConfig);
      onRefined(result);
      toast.success("Plan refined successfully!", {
        description: "Results have been updated below.",
      });
      setPrompt("");
    } catch (err) {
      toast.error("Refinement failed.", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-border/50 border-primary/20 relative overflow-hidden">
      {/* Subtle gradient accent */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          Refine Your Plan
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Describe changes in natural language and let the agents re-run with
          your guidance.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Quick action buttons */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Quick actions
          </p>
          <div className="flex flex-wrap gap-2">
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon;
              return (
                <Button
                  key={action.label}
                  variant="outline"
                  size="sm"
                  className="text-xs h-8 gap-1.5 hover:border-primary/40 hover:bg-primary/5"
                  onClick={() => {
                    setPrompt(action.prompt);
                  }}
                  disabled={loading}
                >
                  <Icon className="w-3 h-3" />
                  {action.label}
                </Button>
              );
            })}
          </div>
        </div>

        {/* Textarea */}
        <div>
          <Textarea
            id="refinement-textarea"
            placeholder="Describe your changes... e.g. 'Find sponsors with sustainability focus', 'Add more keynote speakers from Europe', 'Increase VIP tier price by 30%'"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="min-h-[100px] text-sm resize-none bg-muted/20 border-border/50 focus:border-primary/50"
            disabled={loading}
          />
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between">
          {loading && (
            <Badge
              variant="outline"
              className="text-xs gap-1.5 bg-primary/10 text-primary border-primary/30"
            >
              <Loader2 className="w-3 h-3 animate-spin" />
              {loadingMsg}
            </Badge>
          )}
          <div className={`flex gap-2 ${loading ? "" : "ml-auto"}`}>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs gap-1"
              onClick={() => setPrompt("")}
              disabled={loading || !prompt}
            >
              <RefreshCw className="w-3 h-3" />
              Clear
            </Button>
            <Button
              id="submit-refinement-btn"
              size="sm"
              className="gap-1.5 text-xs px-5"
              onClick={() => handleRefine()}
              disabled={loading || !prompt.trim()}
            >
              {loading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Sparkles className="w-3 h-3" />
              )}
              {loading ? "Running agents..." : "Refine Plan"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
