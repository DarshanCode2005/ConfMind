"use client";

import type { SponsorSchema } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ExternalLink,
  Download,
  Award,
  Star,
  Building2,
  Globe,
} from "lucide-react";

interface SponsorCardsProps {
  sponsors?: SponsorSchema[];
  loading?: boolean;
}

const TIER_CONFIG: Record<
  string,
  { color: string; icon: string; border: string }
> = {
  Gold: {
    color: "bg-yellow-500/10 text-yellow-300 border-yellow-400/30",
    icon: "🥇",
    border: "border-yellow-400/20",
  },
  Silver: {
    color: "bg-slate-400/10 text-slate-300 border-slate-400/30",
    icon: "🥈",
    border: "border-slate-400/20",
  },
  Bronze: {
    color: "bg-orange-500/10 text-orange-300 border-orange-400/30",
    icon: "🥉",
    border: "border-orange-400/20",
  },
  General: {
    color: "bg-blue-400/10 text-blue-300 border-blue-400/30",
    icon: "🏷️",
    border: "border-blue-400/20",
  },
};

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min((score / 10) * 100, 100);
  const color =
    pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-blue-500" : "bg-slate-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-700`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-semibold tabular-nums w-8 text-right">
        {score.toFixed(1)}
      </span>
    </div>
  );
}

export default function SponsorCards({ sponsors, loading }: SponsorCardsProps) {
  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Award className="w-5 h-5 text-yellow-400" />
          Sponsors
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="border-border/50 bg-card/80">
              <CardContent className="pt-5 pb-5 space-y-3">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-8 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!sponsors || sponsors.length === 0) return null;

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Award className="w-5 h-5 text-yellow-400" />
        Sponsors
        <Badge variant="outline" className="ml-1 text-xs">
          {sponsors.length}
        </Badge>
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sponsors.map((sponsor) => {
          const tier = TIER_CONFIG[sponsor.tier] ?? TIER_CONFIG.General;
          return (
            <Card
              key={sponsor.name}
              className={`border ${tier.border} bg-card/80 hover:bg-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg`}
            >
              <CardHeader className="pb-2 pt-4 px-4">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-sm font-semibold leading-tight">
                    {sponsor.name}
                  </CardTitle>
                  <Badge
                    variant="outline"
                    className={`text-xs shrink-0 ${tier.color}`}
                  >
                    {tier.icon} {sponsor.tier}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4 space-y-3">
                <div className="space-y-1 text-xs text-muted-foreground">
                  {sponsor.industry && (
                    <div className="flex items-center gap-1.5">
                      <Building2 className="w-3 h-3" />
                      {sponsor.industry}
                    </div>
                  )}
                  {sponsor.geo && (
                    <div className="flex items-center gap-1.5">
                      <Globe className="w-3 h-3" />
                      {sponsor.geo}
                    </div>
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <Star className="w-3 h-3 text-yellow-400" />
                    <span className="text-xs text-muted-foreground">
                      Relevance
                    </span>
                  </div>
                  <ScoreBar score={sponsor.relevance_score} />
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 text-xs h-8 gap-1 rounded-lg"
                    onClick={() =>
                      sponsor.website && window.open(sponsor.website, "_blank")
                    }
                    disabled={!sponsor.website}
                  >
                    <ExternalLink className="w-3 h-3" />
                    Website
                  </Button>
                  <Button
                    size="sm"
                    variant="default"
                    className="flex-1 text-xs h-8 gap-1 rounded-lg bg-gradient-to-r from-primary to-cyan-500 text-primary-foreground shadow-md shadow-primary/20"
                    onClick={() =>
                      alert(
                        `Proposal PDF for ${sponsor.name} would download here.`
                      )
                    }
                  >
                    <Download className="w-3 h-3" />
                    Proposal
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
