"""
Antwort-Schemas der simulierten SCADA-Schnittstelle.

Bewusst im "Tag-Format" gehalten, wie es OPC-UA-Server oder
Modbus-Gateways liefern würden: eine flache Liste aus
(Anlagen-ID, Tag-Name, Zeitstempel, Wert, Quality) statt eines schönen,
anwendungsfreundlichen JSON-Objekts. Die Integrationsschicht ist genau
dafür da, aus diesem rohen Tag-Strom ein sauberes Domänenmodell zu machen.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .portfolio import AssetType


class TagQuality(str):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"


class TagReading(BaseModel):
    asset_id: str
    tag_name: str
    timestamp: datetime
    value: float | str | None
    quality: str = "GOOD"


class AssetDescriptor(BaseModel):
    """Statische SCADA-Konfigurationsdaten einer Anlage (Tag-Datenbank-Eintrag)."""
    asset_id: str
    name: str
    site_id: str
    site_name: str
    asset_type: AssetType
    rated_power_kw: float
    capacity_kwp: float | None = None
    capacity_kwh: float | None = None
    available_tags: list[str]
    lat: float
    lon: float
