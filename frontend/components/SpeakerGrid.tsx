"use client";

import type { SpeakerSchema } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Mic, ExternalLink, MapPin, BookOpen, Star } from "lucide-react";

interface SpeakerGridProps {
  speakers?: SpeakerSchema[];
  loading?: boolean;
}

function InfluenceBar({ score }: { score: number }) {
  const pct = Math.min((score / 10) * 100, 100);
  const color =
    pct >= 80 ? "bg-purple-500" : pct >= 60 ? "bg-indigo-500" : "bg-slate-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-700`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-semibold tabular-nums">
        {score.toFixed(1)}
      </span>
    </div>
  );
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

const AVATAR_COLORS = [
  "from-purple-500 to-indigo-600",
  "from-blue-500 to-cyan-600",
  "from-emerald-500 to-teal-600",
  "from-orange-500 to-red-600",
  "from-pink-500 to-rose-600",
];

export default function SpeakerGrid({ speakers, loading }: SpeakerGridProps) {
  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Mic className="w-5 h-5 text-purple-400" />
          Speakers
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
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

  if (!speakers || speakers.length === 0) return null;

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Mic className="w-5 h-5 text-purple-400" />
        Speakers
        <Badge variant="outline" className="ml-1 text-xs">
          {speakers.length}
        </Badge>
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {speakers.map((speaker) => (
          <Card
            key={speaker.name}
            className="border-border/50 hover:border-primary/30 transition-all duration-200 bg-card/80 hover:-translate-y-0.5 hover:shadow-lg"
          >
            <CardContent className="pt-6 pb-6 px-5">
              <p className="font-semibold text-base leading-relaxed break-words">{speaker.name}</p>
              {speaker.topic && (
                <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{speaker.topic}</p>
              )}
              {speaker.region && (
                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  {speaker.region}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
