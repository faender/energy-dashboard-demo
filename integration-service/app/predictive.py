"""
Sehr einfache "Predictive Maintenance"-Heuristik für die Demo.

Kein Machine-Learning-Modell, sondern eine nachvollziehbare Regel: häufen
sich Störmeldungen (SCADA-Alarme) oder Minderleistungs-Warnungen einer
Anlage in den letzten 30 Tagen, steigt das eingeschätzte Ausfallrisiko.
In einer echten Anwendung würde man hier z.B. Vibrationsdaten,
Öltemperaturtrends oder Herstellermodelle einbeziehen - das Prinzip
"aus Historie einen Risiko-Score ableiten" bleibt aber dasselbe.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alarm


def asset_risk_hint(session: Session, asset_id: str, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    alarms = session.execute(
        select(Alarm).where(Alarm.asset_id == asset_id, Alarm.opened_at >= since)
    ).scalars().all()

    fault_count = sum(1 for a in alarms if a.source == "scada")
    underperf_count = sum(1 for a in alarms if a.code == "UNDERPERFORMANCE")

    score = fault_count * 2 + underperf_count
    if score >= 5:
        level = "hoch"
        hint = f"{fault_count} Störmeldungen und {underperf_count} Minderleistungs-Warnungen in {days} Tagen - Inspektion empfehlen."
    elif score >= 2:
        level = "mittel"
        hint = f"{fault_count} Störmeldungen in {days} Tagen - Entwicklung beobachten."
    else:
        level = "niedrig"
        hint = "Keine Auffälligkeiten in der jüngeren Historie."

    return {"risk_level": level, "hint": hint, "fault_count_30d": fault_count, "underperformance_count_30d": underperf_count}
