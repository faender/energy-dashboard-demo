"""
Portfolio-Definition für die simulierte SCADA-Schicht.

Dieses Modul beschreibt NUR, welche physischen Anlagen "im Feld" existieren
(Windkraftanlagen, PV-Parks, Batteriespeicher) und wo sie stehen. In einer
echten Anbindung würden diese Stammdaten in den SCADA-/Leitsystemen der
Anlagenhersteller liegen, nicht in unserer Integrationsschicht - deshalb
liegen sie bewusst in diesem "scada-simulator"-Service und werden von der
Integrationsschicht als externe, fremde Datenquelle behandelt.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class AssetType(str, Enum):
    WIND_TURBINE = "wind_turbine"
    PV_PARK = "pv_park"
    BESS = "bess"  # Battery Energy Storage System / Batteriespeicher


@dataclass
class Site:
    """Ein physischer Standort, der eine oder mehrere Anlagen bündelt (ein 'Park')."""
    site_id: str
    name: str
    lat: float
    lon: float


@dataclass
class Asset:
    site_id: str
    asset_id: str
    type: AssetType
    name: str
    rated_power_kw: float
    # WEA-spezifisch
    rotor_diameter_m: float | None = None
    cut_in_ms: float = 3.0
    rated_ws_ms: float = 12.0
    cut_out_ms: float = 25.0
    # PV-spezifisch
    capacity_kwp: float | None = None
    # Speicher-spezifisch
    capacity_kwh: float | None = None
    # deterministischer Seed pro Anlage, damit das Verhalten über Neustarts stabil bleibt
    seed: int = field(default=0)


# Reale österreichische Regionen für eine plausible Standortverteilung
# (keine exakten Koordinaten realer Anlagen - nur ungefähre regionale
# Mittelpunkte für Demo-Zwecke).
_SITES_RAW = [
    # (site_id, name, lat, lon, type)
    ("wf-parndorf", "Windpark Parndorf", 47.9975, 16.8708, AssetType.WIND_TURBINE),
    ("wf-bruck", "Windpark Bruck/Leitha", 48.0142, 16.7778, AssetType.WIND_TURBINE),
    ("wf-deutschkreutz", "Windpark Deutschkreutz", 47.6167, 16.6167, AssetType.WIND_TURBINE),
    ("wf-eberschwang", "Windpark Eberschwang", 48.1667, 13.6167, AssetType.WIND_TURBINE),
    ("wf-pottendorf", "Windpark Pottendorf", 47.9500, 16.3833, AssetType.WIND_TURBINE),
    ("pv-neusiedl", "PV-Park Neusiedl am See", 47.9500, 16.8500, AssetType.PV_PARK),
    ("pv-stmargarethen", "PV-Park St. Margarethen", 47.7667, 16.6333, AssetType.PV_PARK),
    ("pv-koetschach", "PV-Park Kötschach", 46.6833, 12.9333, AssetType.PV_PARK),
    ("pv-allentsteig", "PV-Park Allentsteig", 48.6833, 15.3500, AssetType.PV_PARK),
    ("bess-parndorf", "Batteriespeicher Parndorf", 47.9950, 16.8650, AssetType.BESS),
    ("bess-allentsteig", "Batteriespeicher Allentsteig", 48.6800, 15.3450, AssetType.BESS),
]

# Anzahl Turbinen pro Windstandort, Summe ergibt exakt 110.
_TURBINES_PER_SITE = {
    "wf-parndorf": 26,
    "wf-bruck": 20,
    "wf-deutschkreutz": 18,
    "wf-eberschwang": 24,
    "wf-pottendorf": 22,
}
assert sum(_TURBINES_PER_SITE.values()) == 110

# PV-Leistung (kWp) pro Standort, Summe ergibt exakt 150.000 kWp (150 MWp).
_PV_CAPACITY_KWP = {
    "pv-neusiedl": 55_000,
    "pv-stmargarethen": 40_000,
    "pv-koetschach": 20_000,
    "pv-allentsteig": 35_000,
}
assert sum(_PV_CAPACITY_KWP.values()) == 150_000

# Speicherkapazität (kWh) pro Standort, Summe 70.000 kWh (70 MWh).
_BESS_CAPACITY_KWH = {
    "bess-parndorf": 40_000,
    "bess-allentsteig": 30_000,
}
assert sum(_BESS_CAPACITY_KWH.values()) == 70_000


def _build_sites() -> list[Site]:
    return [Site(s[0], s[1], s[2], s[3]) for s in _SITES_RAW]


def _build_assets() -> list[Asset]:
    rng = random.Random(42)  # fester Seed -> reproduzierbares Portfolio über Neustarts hinweg
    assets: list[Asset] = []

    for site_id, count in _TURBINES_PER_SITE.items():
        for i in range(count):
            rated_kw = rng.choice([2000, 2350, 3000, 3450])
            assets.append(
                Asset(
                    site_id=site_id,
                    asset_id=f"{site_id}-wtg-{i+1:02d}",
                    type=AssetType.WIND_TURBINE,
                    name=f"WEA {i+1:02d}",
                    rated_power_kw=rated_kw,
                    rotor_diameter_m=rng.choice([90, 112, 126, 136]),
                    cut_in_ms=3.0,
                    rated_ws_ms=rng.uniform(11.5, 13.0),
                    cut_out_ms=25.0,
                    seed=rng.randint(0, 1_000_000),
                )
            )

    for site_id, kwp in _PV_CAPACITY_KWP.items():
        # Jeder PV-Standort wird in mehrere Wechselrichterblöcke aufgeteilt
        # (SCADA-Granularität ist meist pro Wechselrichter/Strang, nicht
        # eine einzige riesige Anlage).
        n_blocks = max(2, kwp // 10_000)
        block_kwp = kwp / n_blocks
        for i in range(int(n_blocks)):
            assets.append(
                Asset(
                    site_id=site_id,
                    asset_id=f"{site_id}-inv-{i+1:02d}",
                    type=AssetType.PV_PARK,
                    name=f"Wechselrichterblock {i+1:02d}",
                    rated_power_kw=block_kwp,
                    capacity_kwp=block_kwp,
                    seed=rng.randint(0, 1_000_000),
                )
            )

    for site_id, kwh in _BESS_CAPACITY_KWH.items():
        assets.append(
            Asset(
                site_id=site_id,
                asset_id=f"{site_id}-bess-01",
                type=AssetType.BESS,
                name="Batteriespeicher-Einheit 01",
                rated_power_kw=kwh / 2,  # typisches 0.5C-Verhältnis Leistung/Energie
                capacity_kwh=kwh,
                seed=rng.randint(0, 1_000_000),
            )
        )

    return assets


SITES: dict[str, Site] = {s.site_id: s for s in _build_sites()}
ASSETS: dict[str, Asset] = {a.asset_id: a for a in _build_assets()}


def assets_by_type(asset_type: AssetType) -> list[Asset]:
    return [a for a in ASSETS.values() if a.type == asset_type]
