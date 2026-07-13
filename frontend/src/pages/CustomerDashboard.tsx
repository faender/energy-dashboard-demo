import { api } from "../api/client";
import { usePolling } from "../lib/usePolling";
import StatCard from "../components/StatCard";
import PortfolioMap from "../components/PortfolioMap";
import YieldChart from "../components/YieldChart";
import { ASSET_TYPE_LABEL, SERIES_COLOR } from "../theme";

function fmt(value: number, digits = 0) {
  return value.toLocaleString("de-AT", { maximumFractionDigits: digits });
}

function fmtMWh(kwh: number) {
  return `${fmt(kwh / 1000, 1)} MWh`;
}

function fmtTons(kg: number) {
  return `${fmt(kg / 1000, 1)} t`;
}

export default function CustomerDashboard() {
  const { data: summary } = usePolling(api.getPortfolioSummary, 15_000);
  const { data: sites } = usePolling(api.getSites, 15_000);
  const { data: yieldSeries } = usePolling(() => api.getYieldSeries(30), 60_000);

  const onlineCount = summary?.counts_by_status.online ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Portfolio-Übersicht</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Windkraft, Photovoltaik und Batteriespeicher in Österreich - konsolidierte Sicht auf Ertrag, Verfügbarkeit
          und CO2-Einsparung.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Aktuelle Einspeiseleistung"
          value={summary ? `${fmt(summary.current_power_kw / 1000, 1)} MW` : "…"}
          sublabel={summary ? `von ${fmt(summary.total_capacity_kw / 1000, 0)} MW installiert` : undefined}
        />
        <StatCard label="Ertrag heute" value={summary ? fmtMWh(summary.today_yield_kwh) : "…"} />
        <StatCard label="Ertrag letzte 30 Tage" value={summary ? fmtMWh(summary.month_yield_kwh) : "…"} />
        <StatCard
          label="CO2-Einsparung (30 Tage)"
          value={summary ? fmtTons(summary.co2_saved_month_kg) : "…"}
          sublabel="ggü. angenommenem Netzstrommix"
          accent="var(--status-good)"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div
          className="lg:col-span-2 rounded-xl overflow-hidden h-96"
          style={{ border: "1px solid var(--border)" }}
        >
          <PortfolioMap sites={sites ?? []} />
        </div>

        <div className="rounded-xl p-4 flex flex-col gap-4" style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}>
          <div>
            <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Anlagenstatus</span>
            <div className="text-2xl font-semibold tabular-nums mt-1">
              {onlineCount} <span className="text-sm font-normal text-[var(--text-secondary)]">/ {summary?.asset_count ?? "…"} online</span>
            </div>
          </div>
          <div className="flex flex-col gap-2 text-sm">
            {(["wind_turbine", "pv_park", "bess"] as const).map((type) => {
              const site_count = sites?.filter((s) => s.asset_type === type).length ?? 0;
              return (
                <div key={type} className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-[var(--text-secondary)]">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: SERIES_COLOR[type] }} />
                    {ASSET_TYPE_LABEL[type]}
                  </span>
                  <span className="tabular-nums text-[var(--text-muted)]">{site_count} Standorte</span>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-auto">
            Kreisgröße = Anzahl Anlagen je Standort. Kräftige Füllung = alle Anlagen online.
          </p>
        </div>
      </div>

      <div className="rounded-xl p-4" style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-1">Ertragsverlauf (30 Tage)</h2>
        <p className="text-xs text-[var(--text-muted)] mb-2">Täglicher Energieertrag nach Anlagenart</p>
        {yieldSeries && <YieldChart data={yieldSeries} />}
      </div>
    </div>
  );
}
