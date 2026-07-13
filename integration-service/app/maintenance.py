"""
Einfache Wartungsticket-Verwaltung.

Für die Demo werden Tickets automatisch aus SCADA-Störmeldungen erzeugt
(jede neue kritische Anlagenstörung bekommt ein offenes Ticket) - in
einem echten Betriebsführungssystem käme hier zusätzlich manuelles
Ticketing durch Techniker/Disponenten dazu. Die Automatik läuft bei
jedem Live-Poll mit und legt nur dann ein neues Ticket an, wenn für den
jeweiligen Alarm noch keines existiert (kein Duplikat-Spam).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alarm, Asset, MaintenanceTicket

ASSET_TYPE_LABEL = {"wind_turbine": "WEA", "pv_park": "PV-Block", "bess": "Speicher"}


def sync_tickets_from_alarms(session: Session, ts: datetime) -> None:
    open_alarms = session.execute(
        select(Alarm).where(Alarm.status == "active", Alarm.source == "scada")
    ).scalars().all()

    for alarm in open_alarms:
        existing = session.execute(
            select(MaintenanceTicket).where(MaintenanceTicket.linked_alarm_id == alarm.id)
        ).scalar_one_or_none()
        if existing is not None:
            continue

        asset = session.get(Asset, alarm.asset_id)
        asset_label = ASSET_TYPE_LABEL.get(asset.asset_type, "Anlage") if asset else "Anlage"
        name = asset.name if asset else alarm.asset_id

        session.add(
            MaintenanceTicket(
                asset_id=alarm.asset_id,
                title=f"Störung {name} ({asset_label}): {alarm.code}",
                description=alarm.message,
                priority="hoch" if alarm.severity == "kritisch" else "mittel",
                status="offen",
                created_at=ts,
                due_date=ts + timedelta(days=3),
                linked_alarm_id=alarm.id,
            )
        )
