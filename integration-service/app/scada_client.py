"""
Dünner HTTP-Client für die Mock-SCADA-Schnittstelle.

Das ist bewusst der EINZIGE Ort im Code, der weiß, dass die "SCADA-Quelle"
aktuell ein REST-Mock ist. Würde man später auf eine echte Anbindung
(OPC-UA-Client, Modbus-Polling, Hersteller-Cloud-API) umstellen, müsste
nur dieses Modul ausgetauscht werden - der Rest der Integrationsschicht
(normalize.py, ingestion.py, kpi.py, alarms.py) bliebe unverändert, weil
er nur mit den normalisierten Modellen arbeitet.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from .config import SCADA_BASE_URL


async def fetch_asset_descriptors() -> list[dict]:
    async with httpx.AsyncClient(base_url=SCADA_BASE_URL, timeout=30) as client:
        resp = await client.get("/scada/assets")
        resp.raise_for_status()
        return resp.json()


async def fetch_live_readings() -> list[dict]:
    async with httpx.AsyncClient(base_url=SCADA_BASE_URL, timeout=30) as client:
        resp = await client.get("/scada/live")
        resp.raise_for_status()
        return resp.json()


async def fetch_history(asset_id: str, start: datetime, end: datetime, interval_minutes: int) -> list[dict]:
    async with httpx.AsyncClient(base_url=SCADA_BASE_URL, timeout=60) as client:
        resp = await client.get(
            "/scada/history",
            params={
                "asset_id": asset_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "interval_minutes": interval_minutes,
            },
        )
        resp.raise_for_status()
        return resp.json()
