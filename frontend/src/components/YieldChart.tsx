import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { YieldSeriesPoint } from "../api/client";
import { ASSET_TYPE_LABEL, SERIES_COLOR } from "../theme";

// Reihenfolge bewusst fix (Wind -> PV -> Speicher), nie nach Wert
// umsortiert - Farbe/Reihenfolge folgt der Anlagenart, nicht dem Rang.
const SERIES_ORDER: Array<keyof typeof SERIES_COLOR> = ["wind_turbine", "pv_park", "bess"];

function formatDateShort(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit" });
}

function formatKwh(value: number) {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toLocaleString("de-AT", { maximumFractionDigits: 1 })} MWh`;
  return `${value.toLocaleString("de-AT", { maximumFractionDigits: 0 })} kWh`;
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((sum: number, p: any) => sum + (p.value ?? 0), 0);
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs shadow-lg"
      style={{ background: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
    >
      <div className="font-medium mb-1">{formatDateShort(label)}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 justify-between">
          <span className="flex items-center gap-1.5 text-[var(--text-secondary)]">
            <span className="h-2 w-2 rounded-full" style={{ background: p.fill }} />
            {ASSET_TYPE_LABEL[p.dataKey as keyof typeof ASSET_TYPE_LABEL]}
          </span>
          <span className="tabular-nums font-medium">{formatKwh(p.value)}</span>
        </div>
      ))}
      <div className="flex items-center justify-between mt-1 pt-1 border-t" style={{ borderColor: "var(--gridline)" }}>
        <span className="text-[var(--text-secondary)]">Gesamt</span>
        <span className="tabular-nums font-semibold">{formatKwh(total)}</span>
      </div>
    </div>
  );
}

export default function YieldChart({ data }: { data: YieldSeriesPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke="var(--gridline)" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDateShort}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={(v) => formatKwh(v)}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={70}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--surface-2)" }} />
        <Legend
          formatter={(value) => (
            <span style={{ color: "var(--text-secondary)", fontSize: 12 }}>
              {ASSET_TYPE_LABEL[value as keyof typeof ASSET_TYPE_LABEL]}
            </span>
          )}
          iconType="circle"
          iconSize={8}
        />
        {SERIES_ORDER.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            stackId="yield"
            fill={SERIES_COLOR[key]}
            stroke="var(--surface-1)"
            strokeWidth={2}
            radius={i === SERIES_ORDER.length - 1 ? [3, 3, 0, 0] : undefined}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
