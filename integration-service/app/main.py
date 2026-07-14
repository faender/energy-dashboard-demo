"""
Eigene API der Integrationsschicht - das, was die Dashboards konsumieren.

Diese API kennt keine SCADA-Tags mehr, sondern nur noch das eigene,
normalisierte Domänenmodell (Assets, Readings, Alarme, Wartungstickets).
Frontend-Code muss nie wissen, ob eine Anlage eine Windkraftanlage,
ein PV-Block oder ein Speicher ist, um z.B. "die aktuelle Leistung"
abzufragen - genau das ist der Mehrwert der Normalisierung.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from . import kpi, predictive
from .alarms import STATE_FAULT, STATE_MAINTENANCE, STATE_OFFLINE, STATE_ONLINE
from .cache import cached
from .config import DATABASE_URL, POLL_INTERVAL_SECONDS
from .db import Base, engine, get_session
from .ingestion import backfill_history, poll_live_forever
from .models import Alarm, Asset, MaintenanceTicket, Reading
from .schemas import (
    AlarmOut,
    AssetDetailOut,
    AssetOut,
    HistoryPointOut,
    LiveValueOut,
    MaintenanceTicketOut,
    PortfolioSummaryOut,
    SiteOut,
    YieldSeriesPointOut,
)

logging.basicConfig(level=logging.INFO)

STATE_LABEL = {STATE_ONLINE: "online", STATE_OFFLINE: "offline", STATE_MAINTENANCE: "maintenance", STATE_FAULT: "fault"}
SEVERITY_ORDER = {"kritisch": 0, "warnung": 1, "info": 2}

# Die zugrunde liegenden Daten ändern sich ohnehin nur im Takt des
# Live-Pollers - ein Cache-TTL knapp darunter hält die Dashboards aktuell,
# entkoppelt die teure KPI-Berechnung aber von der Anzahl gleichzeitig
# pollender Clients/Tabs.
KPI_CACHE_TTL_SECONDS = max(5, POLL_INTERVAL_SECONDS - 2)

_poll_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await backfill_history()
    global _poll_task
    _poll_task = asyncio.create_task(poll_live_forever())
    yield
    if _poll_task:
        _poll_task.cancel()
        # Nicht auf den Task warten: er kann gerade in einem Worker-Thread
        # stecken (asyncio.to_thread), dessen Cancel erst nach Abschluss des
        # laufenden DB-Ticks greift - ein await hier kann den Shutdown lange
        # genug blockieren, dass Docker per SIGKILL abbricht, bevor der
        # Checkpoint unten überhaupt läuft.

    # Bestmöglicher Checkpoint beim Herunterfahren, mit kurzem eigenen
    # Timeout: startet die WAL-Datei bei jedem Neustart wieder klein statt
    # sich über mehrere Tage Nutzung aufzusummieren. Läuft der Poller
    # ausnahmsweise noch, wird einfach übersprungen statt den Shutdown zu
    # riskieren - das ist unkritisch, der nächste Start räumt es dann auf.
    if DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA busy_timeout=2000")
                conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            logging.getLogger("main").warning("Checkpoint beim Herunterfahren übersprungen (DB beschäftigt)")


app = FastAPI(
    title="Energie-Portfolio Integrationsschicht",
    description="Konsumiert Mock-SCADA-Daten, normalisiert sie und stellt Dashboards/KPIs/Alarme bereit.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _asset_to_out(asset: Asset, power: dict, state: dict, alarm_counts: dict) -> AssetOut:
    status = STATE_LABEL.get(int(state[asset.asset_id][1]), "offline") if asset.asset_id in state else "offline"
    return AssetOut(
        asset_id=asset.asset_id,
        name=asset.name,
        site_id=asset.site_id,
        site_name=asset.site_name,
        asset_type=asset.asset_type,
        lat=asset.lat,
        lon=asset.lon,
        rated_power_kw=asset.rated_power_kw,
        capacity_kwp=asset.capacity_kwp,
        capacity_kwh=asset.capacity_kwh,
        status=status,
        current_power_kw=power[asset.asset_id][1] if asset.asset_id in power else None,
        active_alarm_count=alarm_counts.get(asset.asset_id, 0),
    )


@app.get("/api/portfolio/summary", response_model=PortfolioSummaryOut, tags=["Portfolio"])
def get_portfolio_summary():
    def compute():
        session = get_session()
        try:
            return kpi.portfolio_summary(session)
        finally:
            session.close()

    return cached("portfolio_summary", KPI_CACHE_TTL_SECONDS, compute)


@app.get("/api/kpi/yield-series", response_model=list[YieldSeriesPointOut], tags=["Portfolio"])
def get_yield_series(days: int = Query(default=30, ge=1, le=90)):
    def compute():
        session = get_session()
        try:
            return kpi.yield_series(session, days=days)
        finally:
            session.close()

    return cached(f"yield_series:{days}", KPI_CACHE_TTL_SECONDS, compute)


@app.get("/api/sites", response_model=list[SiteOut], tags=["Portfolio"])
def get_sites():
    def compute():
        session = get_session()
        try:
            assets = session.execute(select(Asset)).scalars().all()
            state = kpi.latest_state_by_asset(session)

            by_site: dict[str, list[Asset]] = {}
            for a in assets:
                by_site.setdefault(a.site_id, []).append(a)

            result = []
            for site_id, site_assets in by_site.items():
                first = site_assets[0]
                online = sum(
                    1 for a in site_assets
                    if a.asset_id in state and int(state[a.asset_id][1]) == STATE_ONLINE
                )
                result.append(
                    SiteOut(
                        site_id=site_id,
                        site_name=first.site_name,
                        asset_type=first.asset_type,
                        lat=sum(a.lat for a in site_assets) / len(site_assets),
                        lon=sum(a.lon for a in site_assets) / len(site_assets),
                        asset_count=len(site_assets),
                        online_count=online,
                    )
                )
            return result
        finally:
            session.close()

    return cached("sites", KPI_CACHE_TTL_SECONDS, compute)


@app.get("/api/assets", response_model=list[AssetOut], tags=["Anlagen"])
def list_assets(
    asset_type: str | None = None,
    status: str | None = None,
    site_id: str | None = None,
    search: str | None = None,
):
    session = get_session()
    try:
        stmt = select(Asset)
        if asset_type:
            stmt = stmt.where(Asset.asset_type == asset_type)
        if site_id:
            stmt = stmt.where(Asset.site_id == site_id)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(func.lower(Asset.name).like(like))
        assets = session.execute(stmt).scalars().all()

        power = kpi.latest_power_by_asset(session)
        state = kpi.latest_state_by_asset(session)
        alarm_rows = session.execute(
            select(Alarm.asset_id, func.count(Alarm.id)).where(Alarm.status == "active").group_by(Alarm.asset_id)
        ).all()
        alarm_counts = dict(alarm_rows)

        out = [_asset_to_out(a, power, state, alarm_counts) for a in assets]
        if status:
            out = [a for a in out if a.status == status]
        return out
    finally:
        session.close()


@app.get("/api/assets/{asset_id}", response_model=AssetDetailOut, tags=["Anlagen"])
def get_asset_detail(asset_id: str):
    session = get_session()
    try:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Anlage nicht gefunden")

        power = kpi.latest_power_by_asset(session)
        state = kpi.latest_state_by_asset(session)
        alarm_rows = session.execute(
            select(Alarm.asset_id, func.count(Alarm.id)).where(Alarm.status == "active").group_by(Alarm.asset_id)
        ).all()
        alarm_counts = dict(alarm_rows)

        asset_out = _asset_to_out(asset, power, state, alarm_counts)

        latest_metrics_stmt = (
            select(Reading.metric, Reading.timestamp, Reading.value)
            .where(Reading.asset_id == asset_id)
            .order_by(Reading.metric, Reading.timestamp.desc())
        )
        seen_metrics: set[str] = set()
        live_values: list[LiveValueOut] = []
        for metric, ts, value in session.execute(latest_metrics_stmt):
            if metric in seen_metrics:
                continue
            seen_metrics.add(metric)
            live_values.append(LiveValueOut(metric=metric, value=value, timestamp=ts))

        risk = predictive.asset_risk_hint(session, asset_id)

        return AssetDetailOut(
            asset=asset_out,
            live_values=live_values,
            availability_30d=kpi.availability(session, asset_id),
            yield_30d_kwh=kpi.asset_yield_kwh(session, asset_id),
            performance_ratio_30d=kpi.performance_ratio_pv(session, asset_id),
            risk_level=risk["risk_level"],
            risk_hint=risk["hint"],
            fault_count_30d=risk["fault_count_30d"],
            underperformance_count_30d=risk["underperformance_count_30d"],
        )
    finally:
        session.close()


@app.get("/api/assets/{asset_id}/history", response_model=list[HistoryPointOut], tags=["Anlagen"])
def get_asset_history(asset_id: str, metric: str = Query(default="power_kw"), hours: int = Query(default=48, ge=1, le=24 * 90)):
    session = get_session()
    try:
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = session.execute(
            select(Reading.timestamp, Reading.value)
            .where(Reading.asset_id == asset_id, Reading.metric == metric, Reading.timestamp >= start)
            .order_by(Reading.timestamp)
        ).all()
        return [HistoryPointOut(timestamp=ts, value=value) for ts, value in rows]
    finally:
        session.close()


@app.get("/api/alarms", response_model=list[AlarmOut], tags=["Alarme"])
def list_alarms(status: str | None = "active", severity: str | None = None):
    session = get_session()
    try:
        stmt = select(Alarm, Asset).join(Asset, Alarm.asset_id == Asset.asset_id)
        if status:
            stmt = stmt.where(Alarm.status == status)
        if severity:
            stmt = stmt.where(Alarm.severity == severity)
        rows = session.execute(stmt).all()

        out = [
            AlarmOut(
                id=alarm.id,
                asset_id=alarm.asset_id,
                asset_name=asset.name,
                site_name=asset.site_name,
                code=alarm.code,
                severity=alarm.severity,
                message=alarm.message,
                source=alarm.source,
                status=alarm.status,
                opened_at=alarm.opened_at,
                closed_at=alarm.closed_at,
            )
            for alarm, asset in rows
        ]
        out.sort(key=lambda a: (SEVERITY_ORDER.get(a.severity, 9), -a.opened_at.timestamp()))
        return out
    finally:
        session.close()


@app.get("/api/maintenance", response_model=list[MaintenanceTicketOut], tags=["Wartung"])
def list_maintenance_tickets(status: str | None = None):
    session = get_session()
    try:
        stmt = select(MaintenanceTicket, Asset).join(Asset, MaintenanceTicket.asset_id == Asset.asset_id)
        if status:
            stmt = stmt.where(MaintenanceTicket.status == status)
        rows = session.execute(stmt).all()
        out = [
            MaintenanceTicketOut(
                id=t.id,
                asset_id=t.asset_id,
                asset_name=asset.name,
                title=t.title,
                description=t.description,
                priority=t.priority,
                status=t.status,
                created_at=t.created_at,
                due_date=t.due_date,
            )
            for t, asset in rows
        ]
        priority_order = {"hoch": 0, "mittel": 1, "niedrig": 2}
        out.sort(key=lambda t: (priority_order.get(t.priority, 9), t.created_at))
        return out
    finally:
        session.close()


@app.get("/health", tags=["Status"])
def health():
    session = get_session()
    try:
        asset_count = session.execute(select(func.count(Asset.asset_id))).scalar_one()
        reading_count = session.execute(select(func.count(Reading.id))).scalar_one()
        return {"status": "ok", "assets": asset_count, "readings": reading_count}
    finally:
        session.close()
