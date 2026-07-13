"""
ORM-Modelle der Integrationsschicht - das EIGENE, einheitliche Datenmodell.

Wichtig: Diese Tabellen kennen keine SCADA-Tag-Namen mehr. "wind_speed_ms"
und "irradiance_wm2" sind zwar unterschiedliche Rohtags, aber
"active_power_kw" (WEA/PV) und "power_kw" (BESS) landen hier beide unter
dem einen Metrik-Namen "power_kw" - siehe normalize.py. Das ist der Kern
der Normalisierung: unabhängig vom Anlagentyp gibt es hier eine
einheitliche Struktur, auf der Dashboards/KPIs/Alarme aufsetzen können.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Asset(Base):
    """Normalisierte Anlagen-Stammdaten (angereichert aus der SCADA-Stammdatenabfrage)."""
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str] = mapped_column(String, index=True)
    site_name: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    asset_type: Mapped[str] = mapped_column(String, index=True)  # wind_turbine | pv_park | bess
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    rated_power_kw: Mapped[float] = mapped_column(Float)
    capacity_kwp: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacity_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)


class Reading(Base):
    """
    Normalisierte Zeitreihe. Ein Datensatz pro (Anlage, Metrik, Zeitstempel).

    `quality` wird 1:1 aus der SCADA-Quelle übernommen (GOOD/UNCERTAIN/BAD) -
    so bleibt sichtbar, wie vertrauenswürdig ein Messwert an der Quelle war,
    auch nachdem er in unser eigenes Schema übernommen wurde.
    """
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("asset_id", "metric", "timestamp", name="uq_reading_asset_metric_ts"),
        Index("ix_reading_asset_metric_ts", "asset_id", "metric", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    metric: Mapped[str] = mapped_column(String, index=True)  # power_kw | wind_speed_ms | irradiance_wm2 | soc_percent | state_code
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Float)
    quality: Mapped[str] = mapped_column(String, default="GOOD")


class Alarm(Base):
    """Von der Integrationsschicht erkannte bzw. aus SCADA übernommene Alarme."""
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    code: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)  # kritisch | warnung | info
    message: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)  # scada | derived
    status: Mapped[str] = mapped_column(String, default="active", index=True)  # active | resolved
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MaintenanceTicket(Base):
    """Einfache Wartungsticket-Verwaltung (für die Demo teils automatisch aus Alarmen erzeugt)."""
    __tablename__ = "maintenance_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)  # hoch | mittel | niedrig
    status: Mapped[str] = mapped_column(String, default="offen", index=True)  # offen | in_bearbeitung | erledigt
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_alarm_id: Mapped[int | None] = mapped_column(ForeignKey("alarms.id"), nullable=True)
