"use client";

import {
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { brl } from "@/lib/format";

// month = "YYYY-MM"; o eixo mostra a inicial do mês e destaca a virada de ano.
export type FreightPoint = { month: string; value: number; low: number; high: number };

const MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

function mesAbrev(m: string): string {
  const i = Number(m.slice(5, 7)) - 1;
  return MESES[i] ?? m;
}
function ano(m: string): string {
  return m.slice(0, 4);
}

export function FreightAreaChart({ data, height = 260 }: { data: FreightPoint[]; height?: number }) {
  const rows = data.map((p) => ({ ...p, range: [p.low, p.high] as [number, number] }));

  // índice onde o ano vira (primeiro mês com ano diferente do 1º ponto)
  const turnIdx = rows.findIndex((r) => rows.length > 0 && ano(r.month) !== ano(rows[0].month));
  const hasTurn = turnIdx > 0;
  const ano1 = rows.length ? ano(rows[0].month) : "";
  const ano2 = hasTurn ? ano(rows[turnIdx].month) : "";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 24, right: 12, left: 4, bottom: 4 }}>
        <defs>
          <linearGradient id="goldBand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#c5a572" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#c5a572" stopOpacity={0.04} />
          </linearGradient>
        </defs>

        {/* rótulos de ano por trecho + linha vertical na virada */}
        {hasTurn && (
          <>
            <ReferenceArea
              x1={rows[0].month}
              x2={rows[turnIdx - 1].month}
              fill="transparent"
              label={{ value: ano1, position: "insideTop", fill: "#c5a572", fontSize: 13 }}
            />
            <ReferenceArea
              x1={rows[turnIdx].month}
              x2={rows[rows.length - 1].month}
              fill="transparent"
              label={{ value: ano2, position: "insideTop", fill: "#c5a572", fontSize: 13 }}
            />
            <ReferenceLine
              x={rows[turnIdx].month}
              stroke="rgba(197,165,114,0.55)"
              strokeDasharray="4 4"
            />
          </>
        )}

        <XAxis
          dataKey="month"
          tickFormatter={mesAbrev}
          tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "rgba(197,165,114,0.15)" }}
          interval={0}
          minTickGap={0}
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
          labelFormatter={(m) => `${mesAbrev(String(m))}/${ano(String(m)).slice(2)}`}
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
