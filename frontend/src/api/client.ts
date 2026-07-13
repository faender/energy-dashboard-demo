// Dünner Fetch-Wrapper für die Integrationsschicht-API. Bewusst kein
// generierter Client (z.B. aus OpenAPI) - für eine Demo dieser Größe reicht
// ein einfacher, gut lesbarer Wrapper mit manuell gepflegten Typen.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(BASE_URL + path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API-Fehler ${res.status} bei ${path}`);
  }
  return res.json();
}

export interface PortfolioSummary {
  asset_count: number;
  counts_by_status: Record<string, number>;
  total_capacity_kw: number;
  current_power_kw: number;
  today_yield_kwh: number;
  month_yield_kwh: number;
  co2_saved_today_kg: number;
  co2_saved_month_kg: number;
}

export interface YieldSeriesPoint {
  date: string;
  wind_turbine: number;
  pv_park: number;
  bess: number;
}

export interface SiteSummary {
  site_id: string;
  site_name: string;
  asset_type: "wind_turbine" | "pv_park" | "bess";
  lat: number;
  lon: number;
  asset_count: number;
  online_count: number;
}

export interface Asset {
  asset_id: string;
  name: string;
  site_id: string;
  site_name: string;
  asset_type: "wind_turbine" | "pv_park" | "bess";
  lat: number;
  lon: number;
  rated_power_kw: number;
  capacity_kwp: number | null;
  capacity_kwh: number | null;
  status: "online" | "offline" | "maintenance" | "fault";
  current_power_kw: number | null;
  active_alarm_count: number;
}

export interface LiveValue {
  metric: string;
  value: number;
  timestamp: string;
}

export interface AssetDetail {
  asset: Asset;
  live_values: LiveValue[];
  availability_30d: number;
  yield_30d_kwh: number;
  performance_ratio_30d: number | null;
  risk_level: "hoch" | "mittel" | "niedrig";
  risk_hint: string;
  fault_count_30d: number;
  underperformance_count_30d: number;
}

export interface HistoryPoint {
  timestamp: string;
  value: number;
}

export interface Alarm {
  id: number;
  asset_id: string;
  asset_name: string;
  site_name: string;
  code: string;
  severity: "kritisch" | "warnung" | "info";
  message: string;
  source: "scada" | "derived";
  status: "active" | "resolved";
  opened_at: string;
  closed_at: string | null;
}

export interface MaintenanceTicket {
  id: number;
  asset_id: string;
  asset_name: string;
  title: string;
  description: string;
  priority: "hoch" | "mittel" | "niedrig";
  status: "offen" | "in_bearbeitung" | "erledigt";
  created_at: string;
  due_date: string | null;
}

export const api = {
  getPortfolioSummary: () => get<PortfolioSummary>("/api/portfolio/summary"),
  getYieldSeries: (days = 30) => get<YieldSeriesPoint[]>("/api/kpi/yield-series", { days }),
  getSites: () => get<SiteSummary[]>("/api/sites"),
  getAssets: (filters?: { asset_type?: string; status?: string; site_id?: string; search?: string }) =>
    get<Asset[]>("/api/assets", filters),
  getAssetDetail: (assetId: string) => get<AssetDetail>(`/api/assets/${assetId}`),
  getAssetHistory: (assetId: string, metric: string, hours = 48) =>
    get<HistoryPoint[]>(`/api/assets/${assetId}/history`, { metric, hours }),
  getAlarms: (filters?: { status?: string; severity?: string }) => get<Alarm[]>("/api/alarms", filters),
  getMaintenanceTickets: (status?: string) => get<MaintenanceTicket[]>("/api/maintenance", { status }),
};
