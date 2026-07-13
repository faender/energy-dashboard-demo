"""
Physikalisch plausible Simulation von Messwerten pro Anlage und Zeitpunkt.

Kernidee: Für jede Anlage und jeden Zeitpunkt wird der Wert DETERMINISTISCH
aus (asset.seed, timestamp) berechnet - kein gespeicherter Zustand nötig.
Das erlaubt sowohl "Live"-Abfragen (aktueller Zeitpunkt) als auch
"History"-Abfragen (beliebiger Zeitpunkt in der Vergangenheit) mit
demselben Code, ohne Millionen Messwerte vorhalten zu müssen - genau wie
ein echter SCADA-Historian es tun würde (dort liegen die Werte natürlich
tatsächlich gespeichert, hier generieren wir sie "on the fly").
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime

from .portfolio import Asset, AssetType, SITES

TWO_PI = 2 * math.pi


def _stable_random(*parts: object) -> float:
    """Liefert eine deterministische Pseudozufallszahl in [0, 1) aus beliebigen Teilen."""
    key = "|".join(str(p) for p in parts).encode()
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:12], 16) / 16**12


def _hour_fraction(ts: datetime) -> float:
    """Uhrzeit als Bruchteil des Tages, 0.0 = Mitternacht, 0.5 = Mittag."""
    return (ts.hour * 3600 + ts.minute * 60 + ts.second) / 86400


def solar_elevation_factor(ts: datetime, lat: float) -> float:
    """
    Stark vereinfachtes Sonnenstands-Modell: liefert einen Faktor in [0, 1],
    der die Tages- und Jahreszeit grob abbildet (0 nachts, Maximum um die
    Mittagszeit, geringere Amplitude im Winterhalbjahr). Keine astronomisch
    exakte Berechnung - für eine Demo aber ausreichend realistisch.
    """
    day_of_year = ts.timetuple().tm_yday
    # Saisonale Amplitude: Sommer ~1.0, Winter ~0.35 (Mitteleuropa)
    seasonal = 0.675 + 0.325 * math.cos(TWO_PI * (day_of_year - 172) / 365)

    hour = ts.hour + ts.minute / 60
    # Sonnenauf-/-untergang wandert grob zwischen 05:30/21:00 (Sommer) und
    # 07:45/16:15 (Winter) - linear interpoliert über die Saison.
    winter_weight = 1 - seasonal
    sunrise = 5.5 * seasonal + 7.75 * winter_weight
    sunset = 21.0 * seasonal + 16.25 * winter_weight

    if hour <= sunrise or hour >= sunset:
        return 0.0

    day_length = sunset - sunrise
    x = (hour - sunrise) / day_length  # 0..1 über den Tag
    elevation = math.sin(math.pi * x)  # 0 -> 1 -> 0
    return max(0.0, elevation * seasonal)


def wind_speed_ms(asset: Asset, ts: datetime) -> float:
    """
    Windgeschwindigkeit: Grundniveau pro Standort + Tagesgang (nachts/morgens
    oft böiger) + kurzfristiges Rauschen + langsam wanderndes "Wetter"
    (mehrtägige Schönwetter-/Sturmphasen).
    """
    site = SITES[asset.site_id]
    base = 4.5 + 3.5 * _stable_random(site.site_id, "base_wind")

    # Mehrtägiges Wettermuster: ändert sich langsam (Periode ~4 Tage)
    weather_phase = _stable_random(site.site_id, "weather_phase") * TWO_PI
    day_index = ts.timestamp() / 86400
    weather = 1.0 + 0.9 * math.sin(TWO_PI * day_index / 4.2 + weather_phase)

    # Leichter Tagesgang: abends/nachts tendenziell etwas windiger
    diurnal = 1.0 + 0.15 * math.cos(TWO_PI * (_hour_fraction(ts) - 0.15))

    # Kurzfristiges Rauschen (Böigkeit), pro 10-Minuten-Fenster stabil
    ten_min_bucket = int(ts.timestamp() // 600)
    noise = 0.7 + 0.6 * _stable_random(asset.asset_id, "gust", ten_min_bucket)

    speed = base * weather * diurnal * noise
    return max(0.0, round(speed, 2))


def wind_power_kw(asset: Asset, ws: float) -> float:
    """Typische kubische Leistungskurve einer WEA zwischen Cut-in und Nennwind."""
    if ws < asset.cut_in_ms or ws >= asset.cut_out_ms:
        return 0.0
    if ws >= asset.rated_ws_ms:
        return asset.rated_power_kw
    fraction = (ws - asset.cut_in_ms) / (asset.rated_ws_ms - asset.cut_in_ms)
    return round(asset.rated_power_kw * fraction**3, 1)


def irradiance_wm2(asset: Asset, ts: datetime) -> float:
    """Globalstrahlung: Sonnenstand * Wolkenfaktor (langsam wandernd, wie Wetter)."""
    site = SITES[asset.site_id]
    elevation = solar_elevation_factor(ts, site.lat)
    if elevation <= 0:
        return 0.0

    cloud_phase = _stable_random(site.site_id, "cloud_phase") * TWO_PI
    day_index = ts.timestamp() / 86400
    # Wolkenfaktor zwischen ~0.35 (stark bewölkt) und 1.0 (klar)
    cloud_factor = 0.675 + 0.325 * math.sin(TWO_PI * day_index / 2.7 + cloud_phase)

    five_min_bucket = int(ts.timestamp() // 300)
    flicker = 0.92 + 0.16 * _stable_random(asset.asset_id, "cloud_flicker", five_min_bucket)

    irradiance = 1000 * elevation * cloud_factor * flicker
    return max(0.0, round(irradiance, 1))


def pv_power_kw(asset: Asset, irr: float, ts: datetime) -> float:
    """PV-Leistung ~ linear zur Einstrahlung, mit leichtem Temperatur-Derating im Sommer."""
    if irr <= 0:
        return 0.0
    day_of_year = ts.timetuple().tm_yday
    seasonal_heat = 0.5 + 0.5 * math.cos(TWO_PI * (day_of_year - 172) / 365)
    temp_derating = 1.0 - 0.08 * seasonal_heat * (irr / 1000)
    power = asset.capacity_kwp * (irr / 1000) * temp_derating
    return max(0.0, round(power, 1))


def bess_state(asset: Asset, ts: datetime) -> tuple[float, float]:
    """
    Liefert (state_of_charge_percent, power_kw) für einen Batteriespeicher.
    Vereinfachtes Lade-/Entladeschema: lädt tagsüber (PV-Überschuss),
    entlädt abends/nachts (Spitzenlast) - ein typisches Arbitrage-Muster.
    """
    hf = _hour_fraction(ts)
    # Ladezyklus: laden 10-15 Uhr, entladen 17-22 Uhr, sonst Halten mit leichter Drift
    if 0.42 <= hf <= 0.625:  # ~10:00-15:00
        power = -asset.rated_power_kw * (0.4 + 0.5 * _stable_random(asset.asset_id, "charge", int(ts.timestamp() // 900)))
    elif 0.708 <= hf <= 0.917:  # ~17:00-22:00
        power = asset.rated_power_kw * (0.4 + 0.5 * _stable_random(asset.asset_id, "discharge", int(ts.timestamp() // 900)))
    else:
        power = asset.rated_power_kw * 0.03 * (_stable_random(asset.asset_id, "idle", int(ts.timestamp() // 900)) - 0.5)

    # SoC grob aus der Tageszeit ableiten (Sägezahn: niedrig am Morgen, hoch am Nachmittag)
    if hf < 0.42:
        soc = 25 + 15 * (hf / 0.42)
    elif hf < 0.625:
        soc = 40 + 55 * ((hf - 0.42) / (0.625 - 0.42))
    elif hf < 0.917:
        soc = 95 - 65 * ((hf - 0.625) / (0.917 - 0.625))
    else:
        soc = 30 - 5 * ((hf - 0.917) / (1 - 0.917))

    soc += 3 * (_stable_random(asset.asset_id, "soc_noise", int(ts.timestamp() // 600)) - 0.5)
    soc = min(98.0, max(2.0, soc))
    return round(soc, 1), round(power, 1)


# --- Störungen / Anomalien --------------------------------------------------
#
# Statuscodes bewusst im typischen SCADA-Stil gehalten (kleine Ganzzahl statt
# Klartext), analog zu z.B. IEC 61400-25 Zustandscodes bei WEA-Herstellern.
STATE_ONLINE = 0
STATE_OFFLINE = 1
STATE_MAINTENANCE = 2
STATE_FAULT = 3

STATE_LABELS = {
    STATE_ONLINE: "online",
    STATE_OFFLINE: "offline",
    STATE_MAINTENANCE: "maintenance",
    STATE_FAULT: "fault",
}

# Ein paar Anlagen bekommen "eingebrannte" Störfenster, damit die Demo
# reproduzierbare Alarme/Anomalien zeigt statt rein zufälligem Rauschen.
_ALARM_CODES = {
    AssetType.WIND_TURBINE: ["A101_GEARBOX_TEMP", "A210_YAW_ERROR", "A305_GRID_FAULT"],
    AssetType.PV_PARK: ["B110_STRING_FAULT", "B220_INVERTER_OVERTEMP", "B301_ISOLATION_FAULT"],
    AssetType.BESS: ["C105_CELL_IMBALANCE", "C210_THERMAL_WARNING", "C330_COMM_LOSS"],
}


def asset_state(asset: Asset, ts: datetime) -> tuple[int, str | None]:
    """
    Bestimmt Statuscode + optionalen Alarmcode für eine Anlage zu einem
    Zeitpunkt. Nutzt stündliche Zeitfenster, damit Störungen über mehrere
    aufeinanderfolgende Messpunkte hinweg konsistent bleiben (wie in der
    Realität, wo ein Fehler nicht nach 10 Sekunden von selbst verschwindet).
    """
    hour_bucket = int(ts.timestamp() // 3600)
    roll = _stable_random(asset.asset_id, "state_roll", hour_bucket)

    # ~1.5% der Stunden: Wartung (geplant, längere Fenster von ca. 4-8h)
    maintenance_roll = _stable_random(asset.asset_id, "maintenance_window", hour_bucket // 6)
    if maintenance_roll < 0.015:
        return STATE_MAINTENANCE, None

    # ~2% der Stunden: Störung mit Alarmcode
    if roll < 0.02:
        codes = _ALARM_CODES[asset.type]
        idx = int(_stable_random(asset.asset_id, "alarm_code", hour_bucket) * len(codes))
        return STATE_FAULT, codes[idx]

    # ~0.5% der Stunden: kommunikationsbedingt offline (SCADA-Verbindung weg)
    if roll < 0.025:
        return STATE_OFFLINE, None

    return STATE_ONLINE, None


def tag_values(asset: Asset, ts: datetime) -> dict[str, float | str | None]:
    """
    Berechnet alle SCADA-Tags einer Anlage zu einem Zeitpunkt in einem
    Rutsch. Zentrale Stelle, die main.py sowohl für /scada/live als auch
    /scada/history verwendet, damit beide Endpunkte garantiert dieselben
    Werte liefern (kein State, rein deterministisch aus asset + ts).
    """
    state_code, alarm_code = asset_state(asset, ts)
    running = state_code in (STATE_ONLINE,)

    if asset.type == AssetType.WIND_TURBINE:
        ws = wind_speed_ms(asset, ts)
        power = wind_power_kw(asset, ws) if running else 0.0
        return {
            "wind_speed_ms": ws,
            "active_power_kw": power,
            "state_code": state_code,
            "alarm_code": alarm_code,
        }

    if asset.type == AssetType.PV_PARK:
        irr = irradiance_wm2(asset, ts)
        power = pv_power_kw(asset, irr, ts) if running else 0.0
        return {
            "irradiance_wm2": irr,
            "active_power_kw": power,
            "state_code": state_code,
            "alarm_code": alarm_code,
        }

    if asset.type == AssetType.BESS:
        soc, power = bess_state(asset, ts)
        if not running:
            power = 0.0
        return {
            "soc_percent": soc,
            "power_kw": power,
            "state_code": state_code,
            "alarm_code": alarm_code,
        }

    raise ValueError(f"Unbekannter Anlagentyp: {asset.type}")


TAGS_BY_TYPE = {
    AssetType.WIND_TURBINE: ["wind_speed_ms", "active_power_kw", "state_code", "alarm_code"],
    AssetType.PV_PARK: ["irradiance_wm2", "active_power_kw", "state_code", "alarm_code"],
    AssetType.BESS: ["soc_percent", "power_kw", "state_code", "alarm_code"],
}
