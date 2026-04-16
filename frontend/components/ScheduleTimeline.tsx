"use client";

import type { ScheduleEntry } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarClock, Mic, DoorOpen } from "lucide-react";

interface ScheduleTimelineProps {
  schedule?: ScheduleEntry[];
  loading?: boolean;
}

interface NormalizedScheduleEntry {
  time: string;
  room?: string;
  speaker?: string;
  topic: string;
}

const SESSION_COLORS = [
  "border-l-blue-500",
  "border-l-purple-500",
  "border-l-emerald-500",
  "border-l-amber-500",
  "border-l-pink-500",
  "border-l-cyan-500",
];

export default function ScheduleTimeline({
  schedule,
  loading,
}: ScheduleTimelineProps) {
  if (loading) {
    return (
      <Card className="border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-amber-400" />
            Schedule
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="w-16 h-10 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-32" />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!schedule || schedule.length === 0) return null;

  const normalized: NormalizedScheduleEntry[] = schedule.map((entry) => {
    const rawTime =
      typeof entry.time === "string" && entry.time.trim().length > 0
        ? entry.time.trim()
        : "TBD";

    const rawTopic =
      typeof entry.topic === "string" && entry.topic.trim().length > 0
        ? entry.topic.trim()
        : "Session";

    return {
      time: rawTime,
      topic: rawTopic,
      speaker: typeof entry.speaker === "string" ? entry.speaker.trim() || undefined : undefined,
      room: typeof entry.room === "string" ? entry.room.trim() || undefined : undefined,
    };
  });

  // Sort by time, but keep unknown times at the end.
  const sorted = normalized.sort((a, b) => {
    const aHasTime = a.time !== "TBD";
    const bHasTime = b.time !== "TBD";

    if (aHasTime && bHasTime) {
      return a.time.localeCompare(b.time);
    }
    if (aHasTime && !bHasTime) {
      return -1;
    }
    if (!aHasTime && bHasTime) {
      return 1;
    }
    return a.topic.localeCompare(b.topic);
  });

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <CalendarClock className="w-4 h-4 text-amber-400" />
          Event Schedule
          <Badge variant="outline" className="ml-1 text-xs">
            {schedule.length} sessions
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Timeline track */}
          <div className="absolute left-18 top-0 bottom-0 w-px bg-border/40" />

          <div className="space-y-3">
            {sorted.map((entry, idx) => (
              <div key={idx} className="flex gap-4 group">
                {/* Time column */}
                <div className="w-16 shrink-0 text-right">
                  <span className="text-xs font-semibold text-muted-foreground tabular-nums">
                    {entry.time}
                  </span>
                </div>

                {/* Circle on track */}
                <div className="relative flex items-start">
                  <div className="w-2 h-2 rounded-full bg-primary mt-1.5 ring-2 ring-background z-10" />
                </div>

                {/* Content */}
                <div
                  className={`flex-1 mb-1 pl-3 py-2.5 border-l-4 rounded-r-lg bg-muted/20 hover:bg-muted/30 transition-colors pr-4 ${
                    SESSION_COLORS[idx % SESSION_COLORS.length]
                  }`}
                >
                  <p className="text-sm font-semibold leading-tight mb-1">
                    {entry.topic}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    {entry.speaker && (
                      <span className="flex items-center gap-1">
                        <Mic className="w-3 h-3" />
                        {entry.speaker}
                      </span>
                    )}
                    {entry.room && (
                      <span className="flex items-center gap-1">
                        <DoorOpen className="w-3 h-3" />
                        {entry.room}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
