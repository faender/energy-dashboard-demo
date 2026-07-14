import { useEffect, useState } from "react";

/**
 * Ruft `fetcher` sofort auf und danach im gegebenen Intervall erneut - so
 * bleiben die Dashboards nahe am Live-Poll-Takt der Integrationsschicht
 * (siehe POLL_INTERVAL_SECONDS im Backend), ohne dass der Nutzer manuell
 * neu laden muss.
 */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    setLoading(true);

    async function tick() {
      // Läuft der vorherige Request noch (langsames Backend), keinen weiteren
      // draufstapeln - sonst sammeln sich bei jedem Intervall mehr offene
      // Requests an, was das Backend zusätzlich belastet und es noch
      // langsamer macht.
      if (inFlight) return;
      inFlight = true;
      try {
        const result = await fetcher();
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err as Error);
      } finally {
        inFlight = false;
        if (!cancelled) setLoading(false);
      }
    }

    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading };
}
