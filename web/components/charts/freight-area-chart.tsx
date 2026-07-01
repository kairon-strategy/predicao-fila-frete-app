"use client";

import {
  Area,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { brl } from "@/lib/format";

export type FreightPoint = { label: string; value: number; low: number; high: number };

export function FreightAreaChart({ data, height = 260 }: { data: FreightPoint[]; height?: number }) {
  const rows = data.map((p) => ({ ...p, range: [p.low, p.high] as [number, number] }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 10, right: 12, left: 4, bottom: 4 }}>
        <defs>
          <linearGradient id="goldBand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#c5a572" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#c5a572" stopOpacity={0.04} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="label"
          tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "rgba(197,165,114,0.15)" }}
        />
        <YAxis
          tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(v) => `${Math.round(v)}`}
        />
        <Tooltip
          contentStyle={{
            background: "#0e1424",
            border: "1px solid rgba(197,165,114,0.3)",
            borderRadius: 10,
            color: "#fff",
            fontSize: 12,
          }}
          labelStyle={{ color: "#c5a572" }}
          formatter={(value, name) => {
            if (name === "Banda" && Array.isArray(value)) {
              return [`${brl(Number(value[0]))} – ${brl(Number(value[1]))}`, "Banda p10–p90"];
            }
            return [brl(Number(value)), "Frete"];
          }}
        />
        <Area
          type="monotone"
          dataKey="range"
          name="Banda"
          stroke="none"
          fill="url(#goldBand)"
          isAnimationActive
        />
        <Line
          type="monotone"
          dataKey="value"
          name="Frete"
          stroke="#c5a572"
          strokeWidth={2.5}
          dot={{ r: 2.5, fill: "#c5a572" }}
          activeDot={{ r: 5 }}
          isAnimationActive
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
