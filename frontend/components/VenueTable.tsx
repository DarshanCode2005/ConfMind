"use client";

import { useState } from "react";
import type { VenueSchema } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  MapPin,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ExternalLink,
} from "lucide-react";

type SortKey = "name" | "city" | "capacity" | "score";
type SortDir = "asc" | "desc";

interface VenueTableProps {
  venues?: VenueSchema[];
  loading?: boolean;
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 8
      ? "bg-emerald-500/10 text-emerald-300 border-emerald-400/30"
      : score >= 6
        ? "bg-blue-500/10 text-blue-300 border-blue-400/30"
        : "bg-slate-500/10 text-slate-300 border-slate-400/30";
  return (
    <Badge variant="outline" className={`text-xs font-semibold ${color}`}>
      {score.toFixed(1)}
    </Badge>
  );
}

function SortIcon({
  col,
  sortKey,
  sortDir,
}: {
  col: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
}) {
  if (col !== sortKey)
    return <ArrowUpDown className="w-3 h-3 text-muted-foreground" />;
  return sortDir === "asc" ? (
    <ArrowUp className="w-3 h-3 text-primary" />
  ) : (
    <ArrowDown className="w-3 h-3 text-primary" />
  );
}

export default function VenueTable({ venues, loading }: VenueTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  if (loading) {
    return (
      <Card className="border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <MapPin className="w-4 h-4 text-blue-400" />
            Venues
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!venues || venues.length === 0) return null;

  const sorted = [...venues].sort((a, b) => {
    let aVal: number | string = 0;
    let bVal: number | string = 0;

    switch (sortKey) {
      case "name":
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case "city":
        aVal = a.city.toLowerCase();
        bVal = b.city.toLowerCase();
        break;
      case "capacity":
        aVal = a.capacity ?? 0;
        bVal = b.capacity ?? 0;
        break;
      case "score":
        aVal = a.score;
        bVal = b.score;
        break;
    }

    if (typeof aVal === "string") {
      return sortDir === "asc"
        ? aVal.localeCompare(bVal as string)
        : (bVal as string).localeCompare(aVal);
    }

    return sortDir === "asc"
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });

  const ColHeader = ({
    label,
    col,
  }: {
    label: string;
    col: SortKey | null;
  }) =>
    col ? (
      <TableHead
        className="cursor-pointer select-none hover:bg-muted/30 transition-colors"
        onClick={() => handleSort(col)}
      >
        <div className="flex items-center gap-1.5">
          {label}
          <SortIcon col={col} sortKey={sortKey} sortDir={sortDir} />
        </div>
      </TableHead>
    ) : (
      <TableHead>{label}</TableHead>
    );

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <MapPin className="w-4 h-4 text-blue-400" />
          Venues
          <Badge variant="outline" className="ml-1 text-xs">
            {venues.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto rounded-b-lg">
          <Table>
            <TableHeader className="bg-muted/20">
              <TableRow>
                <ColHeader label="Venue" col="name" />
                <ColHeader label="City" col="city" />
                <TableHead>Country</TableHead>
                <ColHeader label="Capacity" col="capacity" />
                <TableHead>Price Range</TableHead>
                <TableHead>Past Events</TableHead>
                <ColHeader label="Score" col="score" />
                <TableHead>Map</TableHead>
                <TableHead>Link</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((venue) => (
                <TableRow
                  key={venue.name}
                  className="hover:bg-muted/20 transition-colors"
                >
                  <TableCell className="font-medium text-sm">
                    {venue.name}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {venue.city}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {venue.country || "N/A"}
                  </TableCell>
                  <TableCell className="text-sm tabular-nums">
                    {venue.capacity
                      ? venue.capacity.toLocaleString()
                      : "N/A"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate">
                    {venue.price_range || "N/A"}
                  </TableCell>
                  <TableCell>
                    {venue.past_events && venue.past_events.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {venue.past_events.slice(0, 2).map((e) => (
                          <Badge
                            key={e}
                            variant="outline"
                            className="text-xs px-1.5 py-0"
                          >
                            {e}
                          </Badge>
                        ))}
                        {venue.past_events.length > 2 && (
                          <Badge
                            variant="outline"
                            className="text-xs px-1.5 py-0 text-muted-foreground"
                          >
                            +{venue.past_events.length - 2}
                          </Badge>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-sm">N/A</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <ScoreBadge score={venue.score} />
                  </TableCell>
                  <TableCell>
                    <Dialog>
                      <DialogTrigger 
                          className={`${buttonVariants({ size: "sm", variant: "outline" })} h-7 px-2 text-xs gap-1 whitespace-nowrap`}
                      >
                          <MapPin className="w-3 h-3" />
                          Map
                      </DialogTrigger>
                      <DialogContent className="sm:max-w-[700px]">
                        <DialogHeader>
                          <DialogTitle>{venue.name}</DialogTitle>
                          <DialogDescription>
                            {venue.city}, {venue.country || "N/A"}
                          </DialogDescription>
                        </DialogHeader>
                        <div className="w-full aspect-video rounded-xl overflow-hidden bg-muted/20 border border-border/50">
                          <iframe
                            width="100%"
                            height="100%"
                            style={{ border: 0 }}
                            loading="lazy"
                            allowFullScreen
                            referrerPolicy="no-referrer-when-downgrade"
                            src={`https://maps.google.com/maps?q=${encodeURIComponent(`${venue.name}, ${venue.city}`)}&t=&z=14&ie=UTF8&iwloc=&output=embed`}
                          ></iframe>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </TableCell>
                  <TableCell>
                    {venue.source_url ? (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() =>
                          window.open(venue.source_url, "_blank")
                        }
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Button>
                    ) : (
                      <span className="text-muted-foreground">N/A</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
