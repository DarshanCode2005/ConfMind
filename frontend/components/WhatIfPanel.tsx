"use client";

import { useEffect, useMemo, useState } from "react";
import type { TicketTierSchema } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Minus, RotateCcw, TrendingDown, TrendingUp, Users, Zap } from "lucide-react";

interface WhatIfPanelProps {
  tiers?: TicketTierSchema[];
}

function formatRevenue(rev: number): string {
  if (rev >= 1_000_000) return `$${(rev / 1_000_000).toFixed(2)}M`;
  if (rev >= 1_000) return `$${(rev / 1_000).toFixed(1)}k`;
  return `$${rev.toFixed(0)}`;
}

function formatSignedPercent(value: number): string {
  if (value === 0) return "0%";
  return `${value > 0 ? "+" : ""}${value}%`;
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

const MULTIPLIERS: Record<string, number> = {
  "Early Bird": 0.7,
  General: 1.0,
  VIP: 2.5,
};

export default function WhatIfPanel({ tiers }: WhatIfPanelProps) {
  const generalTier = tiers?.find((t) => t.name === "General");
  const basePrice = generalTier?.price ?? 200;

  const [price, setPrice] = useState(basePrice);
  const [attendanceShift, setAttendanceShift] = useState(0);

  useEffect(() => {
    setPrice(basePrice);
    setAttendanceShift(0);
  }, [basePrice]);

  const scenario = useMemo(() => {
    if (!tiers || tiers.length === 0) {
      return null;
    }

    const safeBasePrice = Math.max(basePrice, 1);
    const priceChangePercent = (price - safeBasePrice) / safeBasePrice;
    const attendanceManualMultiplier = 1 + attendanceShift / 100;
    const demandMultiplier = Math.min(
      Math.max(1 - priceChangePercent * 0.45, 0.55),
      1.65
    );
    const finalAttendanceMultiplier = Math.max(
      demandMultiplier * attendanceManualMultiplier,
      0
    );

    const adjustedTiers = tiers.map((tier) => {
      const adjustedPrice = Math.round((price * (MULTIPLIERS[tier.name] ?? 1.0)) / 5) * 5;
      const adjustedSales = Math.max(
        0,
        Math.round(tier.est_sales * finalAttendanceMultiplier)
      );
      const adjustedRevenue = adjustedPrice * adjustedSales;
      const revenueDelta = adjustedRevenue - tier.revenue;
      const salesDelta = adjustedSales - tier.est_sales;

      return {
        ...tier,
        adjustedPrice,
        adjustedRevenue,
        adjustedSales,
        revenueDelta,
        salesDelta,
      };
    });

    const originalTotal = tiers.reduce((sum, tier) => sum + tier.revenue, 0);
    const adjustedTotal = adjustedTiers.reduce(
      (sum, tier) => sum + tier.adjustedRevenue,
      0
    );
    const originalAttendance = tiers.reduce((sum, tier) => sum + tier.est_sales, 0);
    const adjustedAttendance = adjustedTiers.reduce(
      (sum, tier) => sum + tier.adjustedSales,
      0
    );

    return {
      adjustedAttendance,
      adjustedTiers,
      adjustedTotal,
      attendanceDelta: adjustedAttendance - originalAttendance,
      demandImpactPercent: Math.round((demandMultiplier - 1) * 100),
      originalAttendance,
      originalTotal,
    };
  }, [attendanceShift, basePrice, price, tiers]);

  if (!tiers || tiers.length === 0 || !scenario) return null;

  const delta = scenario.adjustedTotal - scenario.originalTotal;
  const priceDeltaPercent = Math.round(((price - basePrice) / Math.max(basePrice, 1)) * 100);
  const hasChanges = price !== basePrice || attendanceShift !== 0;

  const maxPrice = Math.max(basePrice * 3, 1000);
  const minPrice = Math.max(Math.floor(basePrice * 0.3), 10);

  const handleReset = () => {
    setPrice(basePrice);
    setAttendanceShift(0);
  };

  return (
    <Card className="border-primary/20 bg-card/85">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="w-4 h-4 text-secondary" />
              What-If Simulator
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Adjust price and expected demand to compare revenue scenarios.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            disabled={!hasChanges}
            className="gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border border-border/50 bg-muted/35 p-3">
            <p className="text-xs text-muted-foreground">Scenario Revenue</p>
            <p className="text-xl font-bold tabular-nums">
              {formatRevenue(scenario.adjustedTotal)}
            </p>
            <DeltaBadge delta={delta} />
          </div>
          <div className="rounded-xl border border-border/50 bg-muted/35 p-3">
            <p className="text-xs text-muted-foreground">Attendance</p>
            <p className="text-xl font-bold tabular-nums">
              {scenario.adjustedAttendance.toLocaleString()}
            </p>
            <p
              className={`text-xs tabular-nums ${
                scenario.attendanceDelta >= 0 ? "text-emerald-500" : "text-red-500"
              }`}
            >
              {scenario.attendanceDelta >= 0 ? "+" : ""}
              {scenario.attendanceDelta.toLocaleString()} attendees
            </p>
          </div>
          <div className="rounded-xl border border-border/50 bg-muted/35 p-3">
            <p className="text-xs text-muted-foreground">Demand Impact</p>
            <p className="text-xl font-bold tabular-nums">
              {formatSignedPercent(scenario.demandImpactPercent)}
            </p>
            <p className="text-xs text-muted-foreground">
              From price movement
            </p>
          </div>
        </div>

        <div>
          <div className="flex justify-between items-center mb-3 gap-4">
            <Label className="text-sm">General Ticket Price</Label>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-primary tabular-nums">
                ${price.toLocaleString()}
              </span>
              <Badge variant="outline" className="text-xs text-muted-foreground">
                {formatSignedPercent(priceDeltaPercent)}
              </Badge>
            </div>
          </div>
          <Slider
            id="whatif-price-slider"
            min={minPrice}
            max={maxPrice}
            step={10}
            value={[price]}
            onValueChange={(v) => {
              const val = Array.isArray(v) ? v[0] : v;
              if (typeof val === "number") setPrice(val);
            }}
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>${minPrice}</span>
            <span>Base: ${basePrice.toLocaleString()}</span>
            <span>${maxPrice.toLocaleString()}</span>
          </div>
        </div>

        <div>
          <div className="flex justify-between items-center mb-3 gap-4">
            <Label className="text-sm flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-primary" />
              Attendance Optimism
            </Label>
            <span className="text-2xl font-bold text-primary tabular-nums">
              {formatSignedPercent(attendanceShift)}
            </span>
          </div>
          <Slider
            id="whatif-attendance-slider"
            min={-40}
            max={60}
            step={5}
            value={[attendanceShift]}
            onValueChange={(v) => {
              const val = Array.isArray(v) ? v[0] : v;
              if (typeof val === "number") setAttendanceShift(val);
            }}
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>Conservative</span>
            <span>Expected</span>
            <span>Optimistic</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {scenario.adjustedTiers.map((tier) => (
            <div
              key={tier.name}
              className="bg-muted/30 rounded-xl p-3 border border-border/50"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-xs font-semibold text-foreground">
                  {tier.name}
                </p>
                <Badge variant="outline" className="text-[10px] text-muted-foreground">
                  ${tier.adjustedPrice.toLocaleString()}
                </Badge>
              </div>
              <p className="text-lg font-bold tabular-nums">
                {formatRevenue(tier.adjustedRevenue)}
              </p>
              <p className="text-xs text-muted-foreground tabular-nums">
                {tier.adjustedSales.toLocaleString()} tickets
              </p>
              <div className="mt-2 flex items-center justify-between text-xs tabular-nums">
                <span
                  className={tier.revenueDelta >= 0 ? "text-emerald-500" : "text-red-500"}
                >
                  {tier.revenueDelta >= 0 ? "+" : ""}
                  {formatRevenue(tier.revenueDelta)}
                </span>
                <span
                  className={tier.salesDelta >= 0 ? "text-emerald-500" : "text-red-500"}
                >
                  {tier.salesDelta >= 0 ? "+" : ""}
                  {tier.salesDelta}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-lg bg-primary/8 border border-primary/20 p-3 text-xs text-muted-foreground">
          This simulator applies a simple price-demand response: higher ticket
          prices reduce expected sales, while lower prices can increase demand.
          Use the attendance slider to model market confidence or campaign lift.
        </div>
      </CardContent>
    </Card>
  );
}
