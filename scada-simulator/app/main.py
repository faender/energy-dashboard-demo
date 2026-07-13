"""
Mock-SCADA-Schnittstelle.

Tut so, als käme sie von echten Anlagen-Leitsystemen (OPC-UA-Server /
Modbus-Gateways vor Ort). Liefert Rohdaten im typischen Tag-Format:
(Anlagen-ID, Tag-Name, Zeitstempel, Wert, Quality) - OHNE jegliche
Aggregation, Normalisierung oder KPI-Logik. Das ist bewusst so: diese
Schicht bildet nur nach, was am Zaun der Anlage technisch ankommt.

Wichtig für die Demo: Dieser Service weiß NICHTS von "Kunden-Dashboard",
"Alarm-Priorisierung" oder "Verfügbarkeit" - das ist Aufgabe der
Integrationsschicht (siehe ../integration-service).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import AssetDescriptor, TagReading
from .portfolio import ASSETS, SITES
from .simulation import TAGS_BY_TYPE, tag_values

app = FastAPI(
    title="Mock-SCADA-Schnittstelle",
    description="Simulierte Anlagen-Leitsystem-Schnittstelle (OPC-UA/Modbus-artiges Tag-Format).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/scada/assets", response_model=list[AssetDescriptor], tags=["Stammdaten"])
def list_assets():
    """Liefert die 'Tag-Datenbank'-Stammdaten aller Anlagen (statisch, wie eine SCADA-Konfiguration)."""
    result = []
    for asset in ASSETS.values():
        site = SITES[asset.site_id]
        result.append(
            AssetDescriptor(
                asset_id=asset.asset_id,
                name=asset.name,
                site_id=asset.site_id,
                site_name=site.name,
                asset_type=asset.type,
                rated_power_kw=asset.rated_power_kw,
                capacity_kwp=asset.capacity_kwp,
                capacity_kwh=asset.capacity_kwh,
                available_tags=TAGS_BY_TYPE[asset.type],
                lat=site.lat,
                lon=site.lon,
            )
        )
    return result


@app.get("/scada/live", response_model=list[TagReading], tags=["Messwerte"])
def read_live(asset_id: str | None = Query(default=None, description="Optional: nur eine Anlage abfragen")):
    """
    Liefert die aktuellen Tag-Werte (Momentaufnahme, wie ein OPC-UA
    'Read' auf alle Tags). Ohne asset_id werden ALLE Anlagen geliefert -
    das entspricht in der Realität eher einem Poll über viele einzelne
    Anlagenverbindungen, hier zur Vereinfachung in einem Aufruf gebündelt.
    """
    now = datetime.now(timezone.utc)
    assets = [ASSETS[asset_id]] if asset_id else list(ASSETS.values())
    if asset_id and asset_id not in ASSETS:
        raise HTTPException(status_code=404, detail=f"Unbekannte asset_id: {asset_id}")

    readings: list[TagReading] = []
    for asset in assets:
        values = tag_values(asset, now)
        for tag_name, value in values.items():
            if value is None:
                continue
            readings.append(
                TagReading(asset_id=asset.asset_id, tag_name=tag_name, timestamp=now, value=value)
            )
    return readings


@app.get("/scada/history", response_model=list[TagReading], tags=["Messwerte"])
def read_history(
    asset_id: str = Query(..., description="Anlagen-ID, für die die Historie gelesen werden soll"),
    start: datetime = Query(..., description="Start (ISO-8601, UTC)"),
    end: datetime = Query(..., description="Ende (ISO-8601, UTC)"),
    interval_minutes: int = Query(default=15, ge=1, le=1440),
):
    """
    Liefert historische Tag-Werte für EINE Anlage im gegebenen Zeitraum -
    analog zu einem Historian-Query (z.B. OPC-UA 'ReadRaw' /
    'ReadProcessed'). Werte werden deterministisch generiert, nicht aus
    einer echten Historie gelesen (siehe simulation.py).
    """
    if asset_id not in ASSETS:
        raise HTTPException(status_code=404, detail=f"Unbekannte asset_id: {asset_id}")
    if end <= start:
        raise HTTPException(status_code=400, detail="end muss nach start liegen")
    if (end - start) > timedelta(days=95):
        raise HTTPException(status_code=400, detail="Zeitraum darf maximal 95 Tage umfassen")

    asset = ASSETS[asset_id]
    readings: list[TagReading] = []
    ts = start
    step = timedelta(minutes=interval_minutes)
    while ts <= end:
        values = tag_values(asset, ts)
        for tag_name, value in values.items():
            if value is None:
                continue
            readings.append(TagReading(asset_id=asset.asset_id, tag_name=tag_name, timestamp=ts, value=value))
        ts += step
    return readings


@app.get("/health", tags=["Status"])
def health():
    return {"status": "ok", "assets": len(ASSETS)}
