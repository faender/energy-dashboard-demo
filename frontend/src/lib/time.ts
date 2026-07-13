// Das Backend liefert Zeitstempel als naive ISO-Strings ohne "Z"/Offset
// (SQLite kennt keine echten tz-aware Timestamps), die Werte sind aber
// intern durchgehend UTC. Ohne "Z" würde JS `new Date(...)` sie fälschlich
// als lokale Zeit interpretieren - deshalb zentral hier korrigieren.
export function parseUtc(iso: string): Date {
  const withZ = iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  return new Date(withZ);
}
