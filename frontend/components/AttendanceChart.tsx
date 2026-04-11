"use client";

import type { TicketTierSchema } from "@/lib/api";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart2 } from "lucide-react";

interface AttendanceChartProps {
  tiers?: TicketTierSchema[];
  loading?: boolean;
}

const COLORS: Record<string, string> = {
  "Early Bird": "#3b82f6",
  General: "#8b5cf6",
  VIP: "#f59e0b",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-card border border-border/50 rounded-lg px-4 py-3 text-sm shadow-xl">
      <p className="font-semibold mb-1">{d.name}</p>
      <p className="text-muted-foreground">
        Est. attendees:{" "}
        <span className="text-foreground font-medium">
          {d.est_sales.toLocaleString()}
        </span>
      </p>
      <p className="text-muted-foreground">
        Revenue:{" "}
        <span className="text-emerald-400 font-medium">
          ${(d.revenue / 1000).toFixed(1)}k
        </span>
      </p>
      <p className="text-muted-foreground">
        Price:{" "}
        <span className="text-foreground font-medium">
          ${d.price.toLocaleString()}
        </span>
      </p>
    </div>
  );
}

export default function AttendanceChart({
  tiers,
  loading,
}: AttendanceChartProps) {
  if (loading) {
    return (
      <Card className="border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-violet-400" />
            Attendance Forecast
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!tiers || tiers.length === 0) return null;

  const data = tiers.map((t) => ({
    name: t.name,
    est_sales: t.est_sales,
    revenue: t.revenue,
    price: t.price,
  }));

  const totalAttendance = tiers.reduce((sum, t) => sum + t.est_sales, 0);

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-violet-400" />
          Attendance Forecast
          <span className="ml-auto text-sm font-normal text-muted-foreground">
            Total:{" "}
            <span className="font-semibold text-foreground">
              {totalAttendance.toLocaleString()}
            </span>{" "}
            attendees
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={data}
            margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="rgba(255,255,255,0.06)"
            />
            <XAxis
              dataKey="name"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) =>
                v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
              }
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
            <Bar dataKey="est_sales" radius={[6, 6, 0, 0]} maxBarSize={80}>
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={COLORS[entry.name] ?? "#6366f1"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-3">
          {data.map((d) => (
            <div key={d.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span
                className="w-2.5 h-2.5 rounded-sm inline-block"
                style={{ backgroundColor: COLORS[d.name] ?? "#6366f1" }}
              />
              {d.name}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
