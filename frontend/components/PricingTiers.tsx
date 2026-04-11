"use client";

import type { TicketTierSchema } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Ticket, TrendingUp, Users } from "lucide-react";

interface PricingTiersProps {
  tiers?: TicketTierSchema[];
  loading?: boolean;
}

const TIER_CONFIG: Record<
  string,
  {
    gradient: string;
    badge: string;
    highlight: boolean;
    icon: string;
    description: string;
  }
> = {
  "Early Bird": {
    gradient: "from-blue-900/50 to-indigo-900/50",
    badge: "bg-blue-400/10 text-blue-300 border-blue-400/30",
    highlight: false,
    icon: "🐦",
    description: "Limited early access pricing",
  },
  General: {
    gradient: "from-primary/10 to-primary/5",
    badge: "bg-primary/10 text-primary border-primary/30",
    highlight: true,
    icon: "🎟️",
    description: "Standard admission",
  },
  VIP: {
    gradient: "from-yellow-900/40 to-amber-900/30",
    badge: "bg-yellow-400/10 text-yellow-300 border-yellow-400/30",
    highlight: false,
    icon: "⭐",
    description: "Premium all-access pass",
  },
};

function formatRevenue(rev: number): string {
  if (rev >= 1_000_000) return `$${(rev / 1_000_000).toFixed(2)}M`;
  if (rev >= 1_000) return `$${(rev / 1_000).toFixed(1)}k`;
  return `$${rev.toFixed(0)}`;
}

export default function PricingTiers({ tiers, loading }: PricingTiersProps) {
  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Ticket className="w-5 h-5 text-emerald-400" />
          Ticket Pricing
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="border-border/50">
              <CardContent className="pt-6 pb-6 space-y-4">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-10 w-20" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!tiers || tiers.length === 0) return null;

  const totalRevenue = tiers.reduce((sum, t) => sum + t.revenue, 0);

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Ticket className="w-5 h-5 text-emerald-400" />
        Ticket Pricing Tiers
        <span className="ml-auto text-sm font-normal text-muted-foreground flex items-center gap-1">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Total:{" "}
          <span className="font-semibold text-emerald-400">
            {formatRevenue(totalRevenue)}
          </span>
        </span>
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {tiers.map((tier) => {
          const config = TIER_CONFIG[tier.name] ?? {
            gradient: "from-muted to-muted/50",
            badge: "",
            highlight: false,
            icon: "🎫",
            description: "",
          };
          return (
            <Card
              key={tier.name}
              className={`relative overflow-hidden border ${
                config.highlight
                  ? "border-primary/40 shadow-lg shadow-primary/10"
                  : "border-border/50"
              }`}
            >
              {/* Gradient bg */}
              <div
                className={`absolute inset-0 bg-gradient-to-br ${config.gradient} pointer-events-none`}
              />
              {config.highlight && (
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-primary to-transparent" />
              )}
              <CardHeader className="relative pb-2 pt-5">
                <div className="flex items-center justify-between">
                  <span className="text-xl">{config.icon}</span>
                  <Badge variant="outline" className={`text-xs ${config.badge}`}>
                    {tier.name}
                  </Badge>
                </div>
                <CardTitle className="text-2xl font-bold mt-2">
                  ${tier.price.toLocaleString()}
                  <span className="text-sm font-normal text-muted-foreground ml-1">
                    / ticket
                  </span>
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {config.description}
                </p>
              </CardHeader>
              <CardContent className="relative space-y-3 pb-5">
                <div className="h-px bg-border/40" />
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5" />
                      Est. Sales
                    </span>
                    <span className="font-semibold tabular-nums">
                      {tier.est_sales.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5" />
                      Revenue
                    </span>
                    <span className="font-bold text-emerald-400 tabular-nums">
                      {formatRevenue(tier.revenue)}
                    </span>
                  </div>
                </div>
                {/* Revenue share bar */}
                {totalRevenue > 0 && (
                  <div>
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>Revenue share</span>
                      <span>{((tier.revenue / totalRevenue) * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full transition-all duration-700"
                        style={{
                          width: `${(tier.revenue / totalRevenue) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
