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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="border-border/50 bg-card/80">
              <CardContent className="pt-6 pb-6">
                <Skeleton className="h-6 w-40" />
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
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {sponsors.map((sponsor) => (
          <Card
            key={sponsor.name}
            className="border border-border/50 bg-card/80 hover:bg-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
          >
            <CardContent className="pt-6 pb-6 px-5">
              <p className="text-base font-semibold leading-relaxed break-words">{sponsor.name}</p>
              {sponsor.industry && (
                <p className="text-xs text-muted-foreground mt-2">{sponsor.industry}</p>
              )}
              {sponsor.tier && (
                <Badge variant="outline" className="mt-3 text-xs">
                  {sponsor.tier}
                </Badge>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
