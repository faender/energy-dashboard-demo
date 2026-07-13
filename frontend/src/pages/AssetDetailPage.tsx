import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../lib/usePolling";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import HistoryChart from "../components/HistoryChart";
import StatCard from "../components/StatCard";
import { ASSET_TYPE_LABEL, SERIES_COLOR } from "../theme";

const METRIC_UNIT: Record<string, string> = {
  power_kw: "kW",
  wind_speed_ms: "m/s",
  irradiance_wm2: "W/m²",
  soc_percent: "%",
};

const METRIC_LABEL: Record<string, string> = {
  power_kw: "Wirkleistung",
  wind_speed_ms: "Windgeschwindigkeit",
  irradiance_wm2: "Einstrahlung",
  soc_percent: "Ladezustand (SoC)",
};

const RISK_COLOR: Record<string, string> = {
  hoch: "var(--status-critical)",
  mittel: "var(--status-warning)",
  niedrig: "var(--status-good)",
};

const HOUR_OPTIONS = [
  { label: "24 Std.", hours: 24 },
  { label: "7 Tage", hours: 24 * 7 },
  { label: "30 Tage", hours: 24 * 30 },
];

export default function AssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>();
  const [metric, setMetric] = useState("power_kw");
  const [hours, setHours] = useState(24);

  const { data: detail } = usePolling(() => api.getAssetDetail(assetId!), 15_000, [assetId]);
  const { data: history } = usePolling(() => api.getAssetHistory(assetId!, metric, hours), 15_000, [assetId, metric, hours]);
  const { data: alarms } = usePolling(() => api.getAlarms({ status: "active" }), 15_000);

  if (!detail) {
    return <p className="text-sm text-[var(--text-muted)]">Lade Anlagendaten…</p>;
  }

  const { asset } = detail;
  const availableMetrics = detail.live_values.map((v) => v.metric).filter((m) => m in METRIC_LABEL);
  const assetAlarms = alarms?.filter((a) => a.asset_id === assetId) ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/service" className="text-xs text-[var(--text-muted)] hover:underline">
          ← Zurück zur Anlagenübersicht
        </Link>
        <div className="flex items-center gap-3 mt-1 flex-wrap">
          <h1 className="text-xl font-semibold">{asset.name}</h1>
          <StatusBadge status={asset.status} />
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: "var(--surface-2)", border: "1px solid var(--border)", color: SERIES_COLOR[asset.asset_type] }}
          >
            {ASSET_TYPE_LABEL[asset.asset_type]}
          </span>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          {asset.site_name} · {asset.asset_id}
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {detail.live_values
          .filter((v) => v.metric in METRIC_LABEL)
          .map((v) => (
            <StatCard
              key={v.metric}
              label={METRIC_LABEL[v.metric]}
              value={`${v.value.toLocaleString("de-AT", { maximumFractionDigits: 1 })} ${METRIC_UNIT[v.metric]}`}
            />
          ))}
        <StatCard label="Verfügbarkeit (30 Tage)" value={`${(detail.availability_30d * 100).toFixed(1)} %`} />
        <StatCard label="Ertrag (30 Tage)" value={`${(detail.yield_30d_kwh / 1000).toLocaleString("de-AT", { maximumFractionDigits: 1 })} MWh`} />
        {detail.performance_ratio_30d != null && (
          <StatCard label="Performance Ratio (30 Tage)" value={`${(detail.performance_ratio_30d * 100).toFixed(0)} %`} />
        )}
      </div>

      <div className="rounded-xl p-4" style={{ background: "var(--surface-1)", border: `1px solid ${RISK_COLOR[detail.risk_level]}` }}>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: RISK_COLOR[detail.risk_level] }} />
          <h2 className="text-sm font-semibold">Predictive-Maintenance-Hinweis · Risiko {detail.risk_level}</h2>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">{detail.risk_hint}</p>
        <p className="text-xs text-[var(--text-muted)] mt-2">
          Einfache Heuristik auf Basis von Störmeldungen und Minderleistungs-Warnungen der letzten 30 Tage - kein ML-Modell.
        </p>
      </div>

      <div className="rounded-xl p-4" style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}>
        <div className="flex items-center justify-between flex-wrap gap-3 mb-2">
          <div className="flex items-center gap-1 rounded-lg p-1" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
            {availableMetrics.map((m) => (
              <button
                key={m}
                onClick={() => setMetric(m)}
                className="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
                style={{
                  background: metric === m ? "var(--surface-1)" : "transparent",
                  color: metric === m ? "var(--text-primary)" : "var(--text-secondary)",
                }}
              >
                {METRIC_LABEL[m]}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 rounded-lg p-1" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
            {HOUR_OPTIONS.map((opt) => (
              <button
                key={opt.hours}
                onClick={() => setHours(opt.hours)}
                className="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
                style={{
                  background: hours === opt.hours ? "var(--surface-1)" : "transparent",
                  color: hours === opt.hours ? "var(--text-primary)" : "var(--text-secondary)",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        {history && <HistoryChart data={history} unit={METRIC_UNIT[metric]} color={SERIES_COLOR[asset.asset_type]} />}
      </div>

      <div className="rounded-xl p-4" style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-2">Aktive Alarme dieser Anlage</h2>
        {assetAlarms.length === 0 && <p className="text-sm text-[var(--text-muted)]">Keine aktiven Alarme.</p>}
        <div className="flex flex-col divide-y" style={{ borderColor: "var(--gridline)" }}>
          {assetAlarms.map((a) => (
            <div key={a.id} className="py-2.5 flex items-center gap-3">
              <SeverityBadge severity={a.severity} />
              <span className="text-sm">{a.message}</span>
              <span className="text-xs text-[var(--text-muted)] ml-auto">{a.source === "scada" ? "SCADA-Meldung" : "Abgeleitet"}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
