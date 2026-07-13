interface StatCardProps {
  label: string;
  value: string;
  sublabel?: string;
  accent?: string;
}

export default function StatCard({ label, value, sublabel, accent }: StatCardProps) {
  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-1"
      style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
    >
      <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-semibold tabular-nums" style={accent ? { color: accent } : undefined}>
        {value}
      </span>
      {sublabel && <span className="text-xs text-[var(--text-secondary)]">{sublabel}</span>}
    </div>
  );
}
