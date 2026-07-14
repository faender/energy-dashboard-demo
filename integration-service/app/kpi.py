"""
KPI-Berechnung auf Basis der normalisierten `readings`-Tabelle.

Alle Funktionen hier kennen nur noch das einheitliche Schema
(asset_id, metric, timestamp, value) - keine SCADA-Tag-Namen mehr. Das
ist der Punkt der Normalisierung: KPI-Logik ist unabhängig vom
Anlagentyp und müsste sich auch dann nicht ändern, wenn ein neuer
Anlagentyp (z.B. Elektrolyseur) mit wieder anderen SCADA-Tags dazukäme -
solange normalize.py dafür ein Mapping auf `power_kw` etc. liefert.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from .alarms import STATE_FAULT, STATE_MAINTENANCE, STATE_OFFLINE, STATE_ONLINE
from .config import CO2_FACTOR_KG_PER_KWH
from .models import Asset, Reading

MAX_GAP_HOURS = 3  # Lücken größer als das (z.B. Backfill/Live-Grenze) nicht mitintegrieren


def _integrate_trapezoidal(points: list[tuple[datetime, float]]) -> float:
    """Numerische Integration einer Leistungs-Zeitreihe (kW über Zeit) zu kWh."""
    if len(points) < 2:
        return 0.0
    points = sorted(points, key=lambda p: p[0])
    energy = 0.0
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        dt_h = (t1 - t0).total_seconds() / 3600
        if 0 < dt_h <= MAX_GAP_HOURS:
            energy += (v0 + v1) / 2 * dt_h
    return energy


def _fetch_metric(
    session: Session, metric: str, start: datetime, end: datetime, asset_ids: list[str] | None = None
) -> dict[str, list[tuple[datetime, float]]]:
    stmt = select(Reading.asset_id, Reading.timestamp, Reading.value).where(
        Reading.metric == metric, Reading.timestamp >= start, Reading.timestamp <= end
    )
    if asset_ids is not None:
        stmt = stmt.where(Reading.asset_id.in_(asset_ids))
    rows = session.execute(stmt).all()
    grouped: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for asset_id, ts, value in rows:
        grouped[asset_id].append((ts, value))
    return grouped


def _latest_metric_per_asset(session: Session, metric: str) -> dict[str, tuple[datetime, float]]:
    """Neuester Wert je Anlage für eine Metrik (z.B. aktuelle Leistung, aktueller Status).

    Per Index (asset_id, metric, timestamp) über eine korrelierte Subquery
    gelöst, statt die komplette (unbegrenzte) Historie der Metrik in Python
    zu laden und dort das neueste Element je Anlage zu suchen - bei
    hunderttausenden Messwerten sonst ein teurer Full-Scan pro Aufruf.
    """
    R2 = aliased(Reading)
    latest_ts = (
        select(func.max(R2.timestamp))
        .where(R2.asset_id == Reading.asset_id, R2.metric == metric)
        .correlate(Reading)
        .scalar_subquery()
    )
    stmt = select(Reading.asset_id, Reading.timestamp, Reading.value).where(
        Reading.metric == metric, Reading.timestamp == latest_ts
    )
    return {asset_id: (ts, value) for asset_id, ts, value in session.execute(stmt)}


def latest_power_by_asset(session: Session) -> dict[str, tuple[datetime, float]]:
    return _latest_metric_per_asset(session, "power_kw")


def latest_state_by_asset(session: Session) -> dict[str, tuple[datetime, float]]:
    return _latest_metric_per_asset(session, "state_code")


def portfolio_summary(session: Session) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now - timedelta(days=30)

    assets = session.execute(select(Asset)).scalars().all()
    latest_power = _latest_metric_per_asset(session, "power_kw")
    latest_state = _latest_metric_per_asset(session, "state_code")

    counts_by_status = {"online": 0, "offline": 0, "maintenance": 0, "fault": 0}
    state_label = {STATE_ONLINE: "online", STATE_OFFLINE: "offline", STATE_MAINTENANCE: "maintenance", STATE_FAULT: "fault"}
    current_power_kw = 0.0
    for asset in assets:
        if asset.asset_id in latest_power:
            current_power_kw += latest_power[asset.asset_id][1]
        state = latest_state.get(asset.asset_id)
        label = state_label.get(int(state[1]), "offline") if state else "offline"
        counts_by_status[label] += 1

    power_points_today = _fetch_metric(session, "power_kw", today_start, now)
    today_yield_kwh = sum(_integrate_trapezoidal(pts) for pts in power_points_today.values())

    power_points_month = _fetch_metric(session, "power_kw", month_start, now)
    month_yield_kwh = sum(_integrate_trapezoidal(pts) for pts in power_points_month.values())

    total_capacity_kw = sum(a.rated_power_kw for a in assets if a.asset_type != "bess")

    return {
        "asset_count": len(assets),
        "counts_by_status": counts_by_status,
        "total_capacity_kw": round(total_capacity_kw, 0),
        "current_power_kw": round(current_power_kw, 1),
        "today_yield_kwh": round(today_yield_kwh, 1),
        "month_yield_kwh": round(month_yield_kwh, 1),
        "co2_saved_today_kg": round(today_yield_kwh * CO2_FACTOR_KG_PER_KWH, 1),
        "co2_saved_month_kg": round(month_yield_kwh * CO2_FACTOR_KG_PER_KWH, 1),
    }


def yield_series(session: Session, days: int = 30) -> list[dict]:
    """Täglicher Ertrag der letzten `days` Tage, aufgeschlüsselt nach Anlagentyp (für den Verlaufschart)."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    assets = session.execute(select(Asset)).scalars().all()
    asset_ids_by_type: dict[str, list[str]] = defaultdict(list)
    for a in assets:
        asset_ids_by_type[a.asset_type].append(a.asset_id)

    power_points = _fetch_metric(session, "power_kw", start, now)

    # Punkte je Anlage nach Kalendertag bucketen (ein Durchlauf über alle Messwerte)
    per_asset_day: dict[str, dict[str, list[tuple[datetime, float]]]] = defaultdict(lambda: defaultdict(list))
    day_keys: set[str] = set()
    for asset_id, points in power_points.items():
        for ts, value in points:
            day_key = ts.date().isoformat()
            per_asset_day[asset_id][day_key].append((ts, value))
            day_keys.add(day_key)

    series = []
    for day_key in sorted(day_keys):
        entry = {"date": day_key}
        for asset_type in ("wind_turbine", "pv_park", "bess"):
            total_kwh = 0.0
            for asset_id in asset_ids_by_type.get(asset_type, []):
                day_points = per_asset_day.get(asset_id, {}).get(day_key)
                if day_points:
                    total_kwh += _integrate_trapezoidal(day_points)
            entry[asset_type] = round(total_kwh, 1)
        series.append(entry)
    return series


def availability(session: Session, asset_id: str, days: int = 30) -> float:
    """
    Vereinfachte technische Verfügbarkeit: Anteil der Zeit im Zustand
    "online" bezogen auf die Zeit ohne geplante Wartung. Eine echte
    Verfügbarkeitskennzahl würde vertraglich exakt definierte
    Ausschlusszeiten (Force Majeure, Netzabschaltung etc.) berücksichtigen.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    rows = session.execute(
        select(Reading.value).where(
            Reading.asset_id == asset_id, Reading.metric == "state_code", Reading.timestamp >= start
        )
    ).scalars().all()
    if not rows:
        return 1.0
    total = len(rows)
    online = sum(1 for v in rows if int(v) == STATE_ONLINE)
    planned_maintenance = sum(1 for v in rows if int(v) == STATE_MAINTENANCE)
    denom = total - planned_maintenance
    if denom <= 0:
        return 1.0
    return round(online / denom, 4)


def performance_ratio_pv(session: Session, asset_id: str, days: int = 30) -> float | None:
    """
    PV Performance Ratio = tatsächlicher Energieertrag / Referenzertrag
    (Referenzertrag = eingestrahlte Energie bezogen auf STC-Nennleistung).
    Standardkennzahl zur Bewertung der PV-Anlagenperformance unabhängig
    vom Wetter.
    """
    asset = session.get(Asset, asset_id)
    if asset is None or asset.asset_type != "pv_park" or not asset.capacity_kwp:
        return None

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    power_points = _fetch_metric(session, "power_kw", start, now, [asset_id]).get(asset_id, [])
    irradiance_points = _fetch_metric(session, "irradiance_wm2", start, now, [asset_id]).get(asset_id, [])

    actual_energy_kwh = _integrate_trapezoidal(power_points)
    # Referenzertrag: eingestrahlte Energie (kWh/m^2, aus W/m^2 über der Zeit
    # integriert) multipliziert mit der STC-Nennleistung der Anlage.
    irradiance_kwh_per_m2 = _integrate_trapezoidal(irradiance_points) / 1000.0
    reference_yield_kwh = irradiance_kwh_per_m2 * asset.capacity_kwp

    if reference_yield_kwh <= 0:
        return None
    return round(actual_energy_kwh / reference_yield_kwh, 3)


def asset_yield_kwh(session: Session, asset_id: str, days: int = 30) -> float:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    points = _fetch_metric(session, "power_kw", start, now, [asset_id]).get(asset_id, [])
    return round(_integrate_trapezoidal(points), 1)
