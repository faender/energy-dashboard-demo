"""Einfacher, prozessweiter TTL-Cache für teure, lesehäufige KPI-Berechnungen.

Ohne Cache rechnet jeder einzelne Dashboard-Request die Portfolio-KPIs komplett
neu - bei mehreren gleichzeitig offenen Dashboards/Tabs potenziert sich das,
obwohl sich die zugrunde liegenden Daten nur im Takt des Live-Pollers
(POLL_INTERVAL_SECONDS) ändern. Ein TTL nahe diesem Takt entkoppelt die
Backend-Last von der Anzahl gleichzeitig pollender Clients.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl_seconds: float, compute: Callable[[], T]) -> T:
    now = time.monotonic()
    with _lock:
        entry = _cache.get(key)
        if entry is not None and now - entry[0] < ttl_seconds:
            return entry[1]  # type: ignore[return-value]

    # Bewusst außerhalb des Locks berechnet, damit ein einzelner langsamer
    # Compute nicht alle anderen Cache-Keys blockiert. Ein gelegentliches
    # doppeltes Berechnen bei zeitgleichem Cache-Miss ist für diese
    # Anwendungsgröße unkritisch.
    result = compute()
    with _lock:
        _cache[key] = (now, result)
    return result
