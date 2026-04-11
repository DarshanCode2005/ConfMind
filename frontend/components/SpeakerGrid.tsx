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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="border-border/50">
              <CardContent className="pt-5 pb-4 space-y-3">
                <div className="flex items-center gap-3">
                  <Skeleton className="w-11 h-11 rounded-full" />
                  <div className="space-y-1.5 flex-1">
                    <Skeleton className="h-4 w-28" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                </div>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {speakers.map((speaker, idx) => {
          const gradClass = AVATAR_COLORS[idx % AVATAR_COLORS.length];
          return (
            <Card
              key={speaker.name}
              className="border-border/50 hover:border-purple-400/30 transition-colors bg-card/50"
            >
              <CardContent className="pt-4 pb-4 px-4 space-y-3">
                {/* Avatar + Name */}
                <div className="flex items-center gap-3">
                  <div
                    className={`w-11 h-11 rounded-full bg-gradient-to-br ${gradClass} flex items-center justify-center text-white font-bold text-sm shrink-0`}
                  >
                    {getInitials(speaker.name)}
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-sm truncate">
                      {speaker.name}
                    </p>
                    {speaker.region && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                        <MapPin className="w-2.5 h-2.5 shrink-0" />
                        {speaker.region}
                      </p>
                    )}
                  </div>
                </div>

                {/* Topic */}
                {speaker.topic && (
                  <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
                    <BookOpen className="w-3 h-3 mt-0.5 shrink-0" />
                    <span className="line-clamp-2">{speaker.topic}</span>
                  </div>
                )}

                {/* Bio */}
                {speaker.bio && (
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {speaker.bio}
                  </p>
                )}

                {/* Influence score */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <Star className="w-3 h-3 text-purple-400" />
                    <span className="text-xs text-muted-foreground">
                      Influence
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {speaker.speaking_experience} talks
                    </span>
                  </div>
                  <InfluenceBar score={speaker.influence_score} />
                </div>

                {/* LinkedIn */}
                {speaker.linkedin_url && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-xs h-7 gap-1.5 text-blue-400 border-blue-400/30 hover:bg-blue-400/10"
                    onClick={() =>
                      window.open(speaker.linkedin_url, "_blank")
                    }
                  >
                    <ExternalLink className="w-3 h-3" />
                    View LinkedIn
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
