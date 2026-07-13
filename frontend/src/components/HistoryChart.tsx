import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistoryPoint } from "../api/client";
import { parseUtc } from "../lib/time";

function formatTime(ts: string) {
  return parseUtc(ts).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
}

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs shadow-lg"
      style={{ background: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
    >
      <div className="text-[var(--text-secondary)] mb-0.5">{formatTime(label)}</div>
      <div className="tabular-nums font-semibold">
        {payload[0].value.toLocaleString("de-AT", { maximumFractionDigits: 1 })} {unit}
      </div>
    </div>
  );
}

export default function HistoryChart({ data, unit, color = "var(--series-wind)" }: { data: HistoryPoint[]; unit: string; color?: string }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--gridline)" />
        <XAxis
          dataKey="timestamp"
          tickFormatter={formatTime}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
          minTickGap={40}
        />
        <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} width={50} />
        <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ stroke: "var(--gridline)" }} />
        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
