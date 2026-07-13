"""Zentrale Konfiguration der Integrationsschicht (per Umgebungsvariable überschreibbar)."""
import os

# Basis-URL des Mock-SCADA-Service. In Docker-Compose zeigt das auf den
# Service-Namen "scada-simulator", lokal (ohne Docker) auf localhost.
SCADA_BASE_URL = os.environ.get("SCADA_BASE_URL", "http://localhost:8001")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/integration.db")

# Wie viele Tage Historie beim ersten Start aus dem Mock-SCADA nachgeladen
# werden (einmaliger Backfill), damit KPI-Charts sofort sinnvolle Verläufe
# zeigen statt bei Null anzufangen.
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "30"))
BACKFILL_INTERVAL_MINUTES = int(os.environ.get("BACKFILL_INTERVAL_MINUTES", "60"))

# Takt der Live-Polling-Schleife (SCADA-Werte abholen + Alarme prüfen).
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "15"))

# Angenommener CO2-Emissionsfaktor für vermiedenen Strombezug aus dem Netz
# (kg CO2 pro kWh). Grober Demo-Annahmewert, keine offizielle Kennzahl -
# in einer echten Anwendung würde man hier einen aktuellen, ggf.
# zeitlich aufgelösten Netz-Emissionsfaktor verwenden.
CO2_FACTOR_KG_PER_KWH = float(os.environ.get("CO2_FACTOR_KG_PER_KWH", "0.4"))
