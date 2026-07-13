"""
Alarm- und einfache Anomalie-Erkennung.

Zwei Quellen von Alarmen, bewusst mit unterschiedlichem `source`-Feld:
- "scada": 1:1 aus dem rohen `alarm_code`-Tag der Anlage übernommen
  (die Anlage selbst meldet einen Fehler).
- "derived": von der Integrationsschicht selbst über einfache
  Schwellwerte erkannt (z.B. Minderleistung, SoC-Grenzen,
  Kommunikationsausfall) - Dinge, die die Anlage selbst nicht als
  "Alarm" markiert, die aber betrieblich relevant sind.

Für die Demo reicht Schwellwertlogik auf dem jeweils letzten Messwert;
ein echtes System würde hier über ein gleitendes Zeitfenster mitteln,
um Rauschen/kurze Spitzen nicht sofort als Alarm zu werten.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alarm, Asset

STATE_ONLINE = 0
STATE_OFFLINE = 1
STATE_MAINTENANCE = 2
STATE_FAULT = 3

ALARM_MESSAGES = {
    "A101_GEARBOX_TEMP": "Getriebetemperatur außerhalb des zulässigen Bereichs",
    "A210_YAW_ERROR": "Fehler bei der Windnachführung (Yaw-System)",
    "A305_GRID_FAULT": "Netzfehler / Netzanschluss gestört",
    "B110_STRING_FAULT": "Strangausfall im PV-Feld erkannt",
    "B220_INVERTER_OVERTEMP": "Wechselrichter-Übertemperatur",
    "B301_ISOLATION_FAULT": "Isolationsfehler erkannt",
    "C105_CELL_IMBALANCE": "Zellspannungs-Ungleichgewicht im Batteriespeicher",
    "C210_THERMAL_WARNING": "Thermische Warnung im Batteriespeicher",
    "C330_COMM_LOSS": "Kommunikationsverlust zum Speicher-BMS",
}


def _sync_alarm(
    session: Session,
    asset_id: str,
    code: str,
    severity: str,
    message: str,
    source: str,
    ts: datetime,
    condition_true: bool,
) -> None:
    """Öffnet einen Alarm falls die Bedingung zutrifft und noch keiner offen ist,
    oder schließt ihn, sobald die Bedingung nicht mehr zutrifft."""
    existing = session.execute(
        select(Alarm).where(
            Alarm.asset_id == asset_id,
            Alarm.code == code,
            Alarm.source == source,
            Alarm.status == "active",
        )
    ).scalar_one_or_none()

    if condition_true:
        if existing is None:
            session.add(
                Alarm(
                    asset_id=asset_id,
                    code=code,
                    severity=severity,
                    message=message,
                    source=source,
                    status="active",
                    opened_at=ts,
                )
            )
    else:
        if existing is not None:
            existing.status = "resolved"
            existing.closed_at = ts


def process_scada_alarm_events(
    session: Session, alarm_events: list[dict], polled_asset_ids: set[str], ts: datetime
) -> None:
    """Gleicht die von der SCADA-Quelle gemeldeten Alarmcodes (`alarm_code`-Tag) mit
    unserem Alarm-Bestand ab: neue Codes öffnen, nicht mehr gemeldete Codes schließen."""
    codes_by_asset: dict[str, set[str]] = {}
    for ev in alarm_events:
        codes_by_asset.setdefault(ev["asset_id"], set()).add(ev["code"])

    for asset_id in polled_asset_ids:
        active_codes = codes_by_asset.get(asset_id, set())

        # bereits offene SCADA-Alarme dieser Anlage einsammeln, um auch
        # Codes zu schließen, die in diesem Poll nicht mehr gemeldet wurden
        existing_open = session.execute(
            select(Alarm.code).where(
                Alarm.asset_id == asset_id, Alarm.source == "scada", Alarm.status == "active"
            )
        ).scalars().all()

        for code in set(existing_open) | active_codes:
            _sync_alarm(
                session,
                asset_id=asset_id,
                code=code,
                severity="kritisch",
                message=ALARM_MESSAGES.get(code, f"Störmeldung {code}"),
                source="scada",
                ts=ts,
                condition_true=code in active_codes,
            )


def evaluate_derived_alarms(session: Session, asset: Asset, latest: dict[str, float], ts: datetime) -> None:
    """Einfache Schwellwert-Regeln der Integrationsschicht (nicht von der Anlage selbst gemeldet)."""
    state = latest.get("state_code")
    power = latest.get("power_kw", 0.0)

    _sync_alarm(
        session,
        asset_id=asset.asset_id,
        code="COMM_LOSS",
        severity="warnung",
        message="Keine aktuellen SCADA-Daten - Kommunikationsausfall vermutet",
        source="derived",
        ts=ts,
        condition_true=state == STATE_OFFLINE,
    )

    if asset.asset_type == "wind_turbine":
        wind_speed = latest.get("wind_speed_ms", 0.0)
        expected_fraction = min(1.0, (wind_speed / 12.0) ** 3) if wind_speed >= 3.5 else 0.0
        expected_power = asset.rated_power_kw * expected_fraction
        underperforming = (
            state == STATE_ONLINE and expected_power > 200 and power < 0.4 * expected_power
        )
        _sync_alarm(
            session,
            asset_id=asset.asset_id,
            code="UNDERPERFORMANCE",
            severity="warnung",
            message="Leistung deutlich unter Erwartungswert bei aktueller Windgeschwindigkeit",
            source="derived",
            ts=ts,
            condition_true=underperforming,
        )

    elif asset.asset_type == "pv_park":
        irradiance = latest.get("irradiance_wm2", 0.0)
        expected_power = (asset.capacity_kwp or 0) * (irradiance / 1000.0)
        underperforming = state == STATE_ONLINE and expected_power > 50 and power < 0.5 * expected_power
        _sync_alarm(
            session,
            asset_id=asset.asset_id,
            code="UNDERPERFORMANCE",
            severity="warnung",
            message="Leistung deutlich unter Erwartungswert bei aktueller Einstrahlung",
            source="derived",
            ts=ts,
            condition_true=underperforming,
        )

    elif asset.asset_type == "bess":
        soc = latest.get("soc_percent", 50.0)
        _sync_alarm(
            session,
            asset_id=asset.asset_id,
            code="SOC_LOW",
            severity="info",
            message="Ladezustand kritisch niedrig",
            source="derived",
            ts=ts,
            condition_true=soc <= 5,
        )
        _sync_alarm(
            session,
            asset_id=asset.asset_id,
            code="SOC_HIGH",
            severity="info",
            message="Ladezustand nahezu voll - Lademanagement prüfen",
            source="derived",
            ts=ts,
            condition_true=soc >= 97,
        )
