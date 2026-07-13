"""
Normalisierung: rohe SCADA-Tags -> einheitliches Metrik-Schema.

Verschiedene Anlagentypen liefern unterschiedliche Tag-Namen für
"denselben" Sachverhalt (z.B. Wirkleistung heißt bei WEA/PV
"active_power_kw", beim Speicher "power_kw"). Hier wird das auf einen
gemeinsamen Metrik-Namen gemappt, damit KPI-Berechnung und Dashboards
NICHT nach Anlagentyp unterscheiden müssen, welches Feld "die Leistung" ist.
"""
from __future__ import annotations

from datetime import datetime

# Roher SCADA-Tag-Name -> einheitlicher Metrik-Name in unserer DB.
RAW_TAG_TO_METRIC = {
    "active_power_kw": "power_kw",
    "power_kw": "power_kw",
    "wind_speed_ms": "wind_speed_ms",
    "irradiance_wm2": "irradiance_wm2",
    "soc_percent": "soc_percent",
    "state_code": "state_code",
}

# alarm_code wird NICHT als numerische Zeitreihe abgelegt, sondern separat
# an die Alarm-Erkennung weitergereicht (siehe ingestion.py / alarms.py).
ALARM_TAG_NAME = "alarm_code"


def normalize_tag_readings(raw_readings: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Wandelt eine Liste roher SCADA-TagReadings (dicts mit asset_id,
    tag_name, timestamp, value, quality) in
    - normalisierte Messwert-Zeilen (für die readings-Tabelle) und
    - Alarm-Ereignisse (für die Alarm-Erkennung)
    um.
    """
    normalized: list[dict] = []
    alarm_events: list[dict] = []

    for raw in raw_readings:
        tag_name = raw["tag_name"]
        ts = raw["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

        if tag_name == ALARM_TAG_NAME:
            if raw["value"] is not None:
                alarm_events.append(
                    {"asset_id": raw["asset_id"], "code": raw["value"], "timestamp": ts}
                )
            continue

        metric = RAW_TAG_TO_METRIC.get(tag_name)
        if metric is None:
            continue  # unbekannter Tag - in einer echten Anbindung würde man das loggen/alerten

        normalized.append(
            {
                "asset_id": raw["asset_id"],
                "metric": metric,
                "timestamp": ts,
                "value": float(raw["value"]),
                "quality": raw.get("quality", "GOOD"),
            }
        )

    return normalized, alarm_events
