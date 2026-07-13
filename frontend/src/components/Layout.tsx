import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const linkBase = "px-3 py-2 rounded-md text-sm font-medium transition-colors";
const linkActive = "bg-[var(--surface-1)] text-[var(--text-primary)]";
const linkInactive = "text-[var(--text-secondary)] hover:text-[var(--text-primary)]";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b sticky top-0 z-20 bg-[var(--surface-2)]" style={{ borderColor: "var(--border)" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-md bg-[var(--series-wind)] flex items-center justify-center text-white text-xs font-bold">
              EP
            </div>
            <span className="font-semibold text-sm">Energie-Portfolio Betriebsführung</span>
            <span className="hidden sm:inline text-xs text-[var(--text-muted)] ml-1">Demo</span>
          </div>
          <nav className="flex items-center gap-1 rounded-lg p-1" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
            <NavLink to="/" end className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
              Kunden-Dashboard
            </NavLink>
            <NavLink to="/service" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
              Service-Dashboard
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">{children}</main>
      <footer className="text-center text-xs text-[var(--text-muted)] py-6">
        Demo-Anwendung · Daten aus simulierter SCADA-Schnittstelle, keine echten Anlagendaten
      </footer>
    </div>
  );
}
