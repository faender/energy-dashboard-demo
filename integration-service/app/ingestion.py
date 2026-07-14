"""
Ingestion: holt Daten aus der Mock-SCADA-Schnittstelle, normalisiert sie
und schreibt sie in die eigene Datenbank. Zwei Betriebsarten:

1. `backfill_history()` - läuft einmalig beim ersten Start und lädt die
   letzten `BACKFILL_DAYS` Tage nach, damit KPI-Charts sofort einen
   sinnvollen Verlauf zeigen (nicht bei Null anfangen).
2. `poll_live()` - Endlosschleife, die im Sekundentakt (konfigurierbar)
   die aktuellen Werte abholt, speichert und die Alarm-Erkennung anstößt.
   Das ist die "Polling/Ingestion-Job"-Komponente aus der Aufgabenstellung.

Beide nutzen dieselbe Normalisierung (normalize.py), damit Backfill und
Live-Betrieb garantiert im selben Schema landen.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from . import scada_client
from .alarms import evaluate_derived_alarms, process_scada_alarm_events
from .config import BACKFILL_DAYS, BACKFILL_INTERVAL_MINUTES, POLL_INTERVAL_SECONDS
from .db import SessionLocal
from .maintenance import sync_tickets_from_alarms
from .models import Asset, Reading
from .normalize import normalize_tag_readings

logger = logging.getLogger("ingestion")


async def sync_asset_master_data(session: Session) -> None:
    """Legt/aktualisiert die normalisierten Anlagen-Stammdaten aus der SCADA-Stammdatenabfrage."""
    descriptors = await scada_client.fetch_asset_descriptors()
    for d in descriptors:
        asset = session.get(Asset, d["asset_id"])
        if asset is None:
            asset = Asset(asset_id=d["asset_id"])
            session.add(asset)
        asset.site_id = d["site_id"]
        asset.site_name = d["site_name"]
        asset.name = d["name"]
        asset.asset_type = d["asset_type"]
        asset.lat = d["lat"]
        asset.lon = d["lon"]
        asset.rated_power_kw = d["rated_power_kw"]
        asset.capacity_kwp = d.get("capacity_kwp")
        asset.capacity_kwh = d.get("capacity_kwh")
    session.commit()
    logger.info("Stammdaten synchronisiert: %d Anlagen", len(descriptors))


def _upsert_readings(session: Session, rows: list[dict]) -> None:
    """Schreibt normalisierte Messwerte idempotent (INSERT ... ON CONFLICT DO NOTHING)."""
    if not rows:
        return
    stmt = sqlite_insert(Reading).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["asset_id", "metric", "timestamp"])
    session.execute(stmt)
    session.commit()


async def backfill_history() -> None:
    """Lädt einmalig Historie für alle Anlagen nach, falls die DB noch leer ist."""
    session = SessionLocal()
    try:
        existing = session.execute(select(Reading.id).limit(1)).first()
        if existing is not None:
            logger.info("Backfill übersprungen - es sind bereits Messwerte vorhanden.")
            return

        await sync_asset_master_data(session)
        assets = session.execute(select(Asset)).scalars().all()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=BACKFILL_DAYS)
        logger.info("Starte Backfill für %d Anlagen (%d Tage, %d-Minuten-Raster)...", len(assets), BACKFILL_DAYS, BACKFILL_INTERVAL_MINUTES)

        # Beim Backfill werden NUR Messwerte geladen, bewusst OHNE
        # Alarm-/Ticket-Erkennung: Die Alarmlogik bildet einen aktuellen
        # Zustand ab (offen/geschlossen). Würde man sie über 30 Tage
        # Historie laufen lassen, würde jeder irgendwann in diesem
        # Zeitraum aufgetretene Fehlercode fälschlich als "gerade jetzt
        # aktiv" markiert. Der erste Live-Poll direkt nach dem Backfill
        # (siehe poll_live_forever) baut den Alarmstand stattdessen aus
        # dem tatsächlich aktuellen Anlagenzustand korrekt auf.
        for i, asset in enumerate(assets, start=1):
            raw = await scada_client.fetch_history(asset.asset_id, start, end, BACKFILL_INTERVAL_MINUTES)
            normalized, _alarm_events = normalize_tag_readings(raw)
            _upsert_readings(session, normalized)
            if i % 20 == 0 or i == len(assets):
                logger.info("Backfill: %d/%d Anlagen geladen", i, len(assets))

        logger.info("Backfill abgeschlossen.")
    finally:
        session.close()


def _poll_once_sync(raw: list[dict]) -> None:
    """Synchroner DB-Teil eines Poll-Durchlaufs - läuft via asyncio.to_thread,
    damit die (blockierenden) SQLAlchemy-Aufrufe nicht den Event-Loop
    einfrieren und dabei alle gerade laufenden API-Requests verzögern."""
    session = SessionLocal()
    try:
        normalized, alarm_events = normalize_tag_readings(raw)
        _upsert_readings(session, normalized)

        polled_asset_ids = {r["asset_id"] for r in normalized}
        now = datetime.now(timezone.utc)
        process_scada_alarm_events(session, alarm_events, polled_asset_ids, now)

        # neueste Werte je Anlage einsammeln, um die Schwellwert-Alarme auszuwerten
        latest_by_asset: dict[str, dict[str, float]] = {}
        for row in normalized:
            latest_by_asset.setdefault(row["asset_id"], {})[row["metric"]] = row["value"]

        assets = session.execute(select(Asset)).scalars().all()
        assets_by_id = {a.asset_id: a for a in assets}
        for asset_id, values in latest_by_asset.items():
            asset = assets_by_id.get(asset_id)
            if asset is not None:
                evaluate_derived_alarms(session, asset, values, now)

        sync_tickets_from_alarms(session, now)
        session.commit()
    finally:
        session.close()


async def poll_once() -> None:
    """Ein Durchlauf: aktuelle Werte holen, normalisieren, speichern, Alarme prüfen."""
    try:
        raw = await scada_client.fetch_live_readings()
        await asyncio.to_thread(_poll_once_sync, raw)
    except Exception:
        logger.exception("Fehler beim Live-Poll")


async def poll_live_forever() -> None:
    while True:
        await poll_once()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
