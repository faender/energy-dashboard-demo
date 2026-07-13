import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../lib/usePolling";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import { ASSET_TYPE_LABEL } from "../theme";
import { parseUtc } from "../lib/time";

function timeAgo(iso: string) {
  const diffMs = Date.now() - parseUtc(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `vor ${hours} Std.`;
  return `vor ${Math.round(hours / 24)} Tagen`;
}

const PRIORITY_LABEL: Record<string, string> = { hoch: "Hoch", mittel: "Mittel", niedrig: "Niedrig" };

export default function ServiceDashboard() {
  const [assetType, setAssetType] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [search, setSearch] = useState("");

  const { data: assets } = usePolling(
    () => api.getAssets({ asset_type: assetType || undefined, status: status || undefined, search: search || undefined }),
    15_000,
    [assetType, status, search],
  );
  const { data: alarms } = usePolling(() => api.getAlarms({ status: "active" }), 15_000);
  const { data: tickets } = usePolling(() => api.getMaintenanceTickets(), 20_000);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Service-Dashboard</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Anlagenübersicht, aktive Alarme und Wartungstickets für die technische Betriebsführung.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Aktive Alarme" subtitle={`${alarms?.length ?? 0} offen, nach Priorität sortiert`}>
          <div className="flex flex-col divide-y" style={{ borderColor: "var(--gridline)" }}>
            {alarms?.length === 0 && <EmptyRow text="Keine aktiven Alarme." />}
            {alarms?.map((a) => (
              <Link
                to={`/service/assets/${a.asset_id}`}
                key={a.id}
                className="py-2.5 flex items-start justify-between gap-3 hover:bg-[var(--surface-2)] -mx-1 px-1 rounded transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={a.severity} />
                    <span className="text-sm font-medium truncate">{a.asset_name}</span>
                    <span className="text-xs text-[var(--text-muted)] truncate">{a.site_name}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">{a.message}</p>
                </div>
                <span className="text-xs text-[var(--text-muted)] whitespace-nowrap">{timeAgo(a.opened_at)}</span>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel title="Wartungstickets" subtitle={`${tickets?.length ?? 0} Tickets, nach Priorität sortiert`}>
          <div className="flex flex-col divide-y" style={{ borderColor: "var(--gridline)" }}>
            {tickets?.length === 0 && <EmptyRow text="Keine offenen Tickets." />}
            {tickets?.map((t) => (
              <Link
                to={`/service/assets/${t.asset_id}`}
                key={t.id}
                className="py-2.5 flex items-start justify-between gap-3 hover:bg-[var(--surface-2)] -mx-1 px-1 rounded transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{
                        background: "var(--surface-2)",
                        border: "1px solid var(--border)",
                        color: t.priority === "hoch" ? "var(--status-critical)" : "var(--text-secondary)",
                      }}
                    >
                      {PRIORITY_LABEL[t.priority]}
                    </span>
                    <span className="text-sm font-medium truncate">{t.title}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t.description}</p>
                </div>
                <span className="text-xs text-[var(--text-muted)] whitespace-nowrap capitalize">{t.status.replace("_", " ")}</span>
              </Link>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Anlagen" subtitle={`${assets?.length ?? 0} Anlagen`}>
        <div className="flex flex-wrap gap-2 mb-3">
          <select
            className="text-sm rounded-md px-2 py-1.5"
            style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
          >
            <option value="">Alle Anlagentypen</option>
            <option value="wind_turbine">Windkraft</option>
            <option value="pv_park">Photovoltaik</option>
            <option value="bess">Batteriespeicher</option>
          </select>
          <select
            className="text-sm rounded-md px-2 py-1.5"
            style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Alle Status</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="maintenance">Wartung</option>
            <option value="fault">Störung</option>
          </select>
          <input
            type="text"
            placeholder="Suche nach Anlagenname…"
            className="text-sm rounded-md px-3 py-1.5 flex-1 min-w-[180px]"
            style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="max-h-[520px] overflow-y-auto rounded-lg" style={{ border: "1px solid var(--gridline)" }}>
          <table className="w-full text-sm">
            <thead className="sticky top-0" style={{ background: "var(--surface-2)" }}>
              <tr className="text-left text-xs text-[var(--text-muted)] uppercase tracking-wide">
                <th className="px-3 py-2 font-medium">Anlage</th>
                <th className="px-3 py-2 font-medium">Typ</th>
                <th className="px-3 py-2 font-medium">Standort</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium text-right">Leistung</th>
                <th className="px-3 py-2 font-medium text-right">Alarme</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--gridline)" }}>
              {assets?.map((a) => (
                <tr key={a.asset_id} className="hover:bg-[var(--surface-2)] cursor-pointer">
                  <td className="px-3 py-2">
                    <Link to={`/service/assets/${a.asset_id}`} className="font-medium hover:underline">
                      {a.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">{ASSET_TYPE_LABEL[a.asset_type]}</td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">{a.site_name}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {a.current_power_kw != null ? `${a.current_power_kw.toLocaleString("de-AT", { maximumFractionDigits: 0 })} kW` : "-"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {a.active_alarm_count > 0 ? (
                      <span style={{ color: "var(--status-critical)" }}>{a.active_alarm_count}</span>
                    ) : (
                      <span className="text-[var(--text-muted)]">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <h2 className="text-sm font-semibold">{title}</h2>
      {subtitle && <p className="text-xs text-[var(--text-muted)] mb-2">{subtitle}</p>}
      {children}
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <p className="text-sm text-[var(--text-muted)] py-3">{text}</p>;
}
