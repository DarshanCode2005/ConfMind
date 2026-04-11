"use client";

import { useState } from "react";
import type { TicketTierSchema } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Zap, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface WhatIfPanelProps {
  tiers?: TicketTierSchema[];
}

function formatRevenue(rev: number): string {
  if (rev >= 1_000_000) return `$${(rev / 1_000_000).toFixed(2)}M`;
  if (rev >= 1_000) return `$${(rev / 1_000).toFixed(1)}k`;
  return `$${rev.toFixed(0)}`;
}

function DeltaBadge({ delta }: { delta: number }) {
  if (Math.abs(delta) < 1) {
    return (
      <Badge variant="outline" className="gap-1 text-xs text-muted-foreground border-border">
        <Minus className="w-3 h-3" />
        No change
      </Badge>
    );
  }
  const isPositive = delta > 0;
  return (
    <Badge
      variant="outline"
      className={`gap-1 text-xs font-semibold ${
        isPositive
          ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
          : "bg-red-400/10 text-red-400 border-red-400/30"
      }`}
    >
      {isPositive ? (
        <TrendingUp className="w-3 h-3" />
      ) : (
        <TrendingDown className="w-3 h-3" />
      )}
      {isPositive ? "+" : ""}
      {formatRevenue(delta)}
    </Badge>
  );
}

export default function WhatIfPanel({ tiers }: WhatIfPanelProps) {
  const generalTier = tiers?.find((t) => t.name === "General");
  const basePrice = generalTier?.price ?? 200;

  const [price, setPrice] = useState(basePrice);

  if (!tiers || tiers.length === 0) return null;

  // Recalculate all tier revenues based on new general price
  // Tier price multipliers: Early Bird = 0.70x, General = 1.00x, VIP = 2.50x
  const MULTIPLIERS: Record<string, number> = {
    "Early Bird": 0.7,
    General: 1.0,
    VIP: 2.5,
  };

  const adjustedTiers = tiers.map((tier) => ({
    ...tier,
    adjustedPrice: price * (MULTIPLIERS[tier.name] ?? 1.0),
    adjustedRevenue: price * (MULTIPLIERS[tier.name] ?? 1.0) * tier.est_sales,
  }));

  const originalTotal = tiers.reduce((sum, t) => sum + t.revenue, 0);
  const adjustedTotal = adjustedTiers.reduce(
    (sum, t) => sum + t.adjustedRevenue,
    0
  );
  const delta = adjustedTotal - originalTotal;

  const maxPrice = Math.max(basePrice * 3, 1000);
  const minPrice = Math.max(Math.floor(basePrice * 0.3), 10);

  return (
    <Card className="border-border/50 border-primary/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          What-If Simulator
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Adjust the general ticket price to see how it impacts total revenue
          across all tiers.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Slider */}
        <div>
          <div className="flex justify-between items-center mb-3">
            <Label className="text-sm">General Ticket Price</Label>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-primary tabular-nums">
                ${price.toLocaleString()}
              </span>
              {price !== basePrice && (
                <Badge
                  variant="outline"
                  className="text-xs text-muted-foreground"
                >
                  Base: ${basePrice.toLocaleString()}
                </Badge>
              )}
            </div>
          </div>
          <Slider
            id="whatif-slider"
            min={minPrice}
            max={maxPrice}
            step={10}
            value={[price]}
            onValueChange={(v) => { const val = Array.isArray(v) ? v[0] : v; if (typeof val === "number") setPrice(val); }}
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>${minPrice}</span>
            <span>${maxPrice.toLocaleString()}</span>
          </div>
        </div>

        {/* Revenue comparison */}
        <div className="grid grid-cols-3 gap-3">
          {adjustedTiers.map((tier) => {
            const origTier = tiers.find((t) => t.name === tier.name);
            const tierDelta = tier.adjustedRevenue - (origTier?.revenue ?? 0);
            return (
              <div
                key={tier.name}
                className="bg-muted/30 rounded-lg p-3 text-center"
              >
                <p className="text-xs text-muted-foreground mb-1">
                  {tier.name}
                </p>
                <p className="text-lg font-bold tabular-nums">
                  ${tier.adjustedPrice.toFixed(0)}
                </p>
                <p className="text-xs text-emerald-400 font-medium tabular-nums">
                  {formatRevenue(tier.adjustedRevenue)}
                </p>
                {Math.abs(tierDelta) > 0.5 && (
                  <p
                    className={`text-xs tabular-nums mt-0.5 ${
                      tierDelta > 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {tierDelta > 0 ? "+" : ""}
                    {formatRevenue(tierDelta)}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Total delta */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30 border border-border/40">
          <div>
            <p className="text-xs text-muted-foreground">
              Adjusted total revenue
            </p>
            <p className="text-xl font-bold tabular-nums">
              {formatRevenue(adjustedTotal)}
            </p>
          </div>
          <DeltaBadge delta={delta} />
        </div>
      </CardContent>
    </Card>
  );
}
