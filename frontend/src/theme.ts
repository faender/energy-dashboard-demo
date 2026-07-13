// Zentrale Farbzuordnung, damit Status-/Serienfarben überall konsistent sind
// (an die im Projekt genutzten Design-Tokens aus index.css gekoppelt).

export const SERIES_COLOR = {
  wind_turbine: "var(--series-wind)",
  pv_park: "var(--series-pv)",
  bess: "var(--series-bess)",
} as const;

export const ASSET_TYPE_LABEL = {
  wind_turbine: "Windkraft",
  pv_park: "Photovoltaik",
  bess: "Batteriespeicher",
} as const;

export const STATUS_COLOR = {
  online: "var(--status-good)",
  offline: "var(--status-serious)",
  maintenance: "var(--status-neutral)",
  fault: "var(--status-critical)",
} as const;

export const STATUS_LABEL = {
  online: "Online",
  offline: "Offline",
  maintenance: "Wartung",
  fault: "Störung",
} as const;

export const SEVERITY_COLOR = {
  kritisch: "var(--status-critical)",
  warnung: "var(--status-warning)",
  info: "var(--status-neutral)",
} as const;

export type AssetType = keyof typeof SERIES_COLOR;
export type AssetStatus = keyof typeof STATUS_COLOR;
export type Severity = keyof typeof SEVERITY_COLOR;
