import { SEVERITY_COLOR, STATUS_COLOR, STATUS_LABEL, type AssetStatus, type Severity } from "../theme";

export function StatusBadge({ status }: { status: AssetStatus }) {
  const color = STATUS_COLOR[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ background: "var(--surface-2)", border: `1px solid ${color}`, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {STATUS_LABEL[status]}
    </span>
  );
}

const SEVERITY_LABEL: Record<Severity, string> = { kritisch: "Kritisch", warnung: "Warnung", info: "Info" };

export function SeverityBadge({ severity }: { severity: Severity }) {
  const color = SEVERITY_COLOR[severity];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ background: "var(--surface-2)", border: `1px solid ${color}`, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
