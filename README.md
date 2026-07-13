# Energie-Portfolio Betriebsführung – Demo

Demo-Webanwendung, die zeigt, wie eine Software-Schicht für die **technische
Betriebsführung** eines Energieportfolios (Windkraft, Photovoltaik,
Batteriespeicher) aussehen könnte – mit Fokus auf **SCADA-Datenintegration**,
nicht auf Anlagensteuerung.

Portfolio: ~110 WEA, ~150 MWp PV (4 Parks), ~70 MWh Batteriespeicher, verteilt
auf Standorte in Österreich.

## Die Grundidee in einem Satz

Es gibt bereits SCADA-Systeme an den Anlagen, die Rohdaten liefern – diese
Anwendung ersetzt sie nicht, sondern **liest sie ein, normalisiert sie,
führt sie in einer eigenen Datenbank zusammen** und baut darauf Dashboards,
KPIs und Alarmierung auf.

## Architektur

```
┌─────────────────────┐        ┌──────────────────────────┐        ┌─────────────────┐
│   scada-simulator    │  REST  │   integration-service     │  REST  │     frontend     │
│  (Mock-SCADA-Schicht)│───────▶│ (eigentliches Projekt)     │───────▶│ React-Dashboards │
│                       │        │                            │        │                  │
│ FastAPI, tut so als   │        │ Ingestion, Normalisierung, │        │ Kunden- +        │
│ käme sie von echten   │        │ eigene DB (SQLite), KPIs,  │        │ Service-Dashboard│
│ Anlagen-Leitsystemen  │        │ Alarme, Wartungstickets    │        │                  │
└─────────────────────┘        └──────────────────────────┘        └─────────────────┘
      Port 8001                        Port 8000                        Port 5173
```

Drei bewusst getrennte Services (auch als eigene Ordner/Repos vorstellbar):

| Ordner | Rolle |
|---|---|
| `scada-simulator/` | **Simuliert** die SCADA-Seite. Kennt nur Anlagen-Rohdaten im Tag-Format (Anlagen-ID, Tag-Name, Zeitstempel, Wert, Quality) – wie ein OPC-UA-Server oder Modbus-Gateway es liefern würde. Kennt keine Kunden-/KPI-/Alarm-Logik. |
| `integration-service/` | **Das eigentliche Projekt.** Holt SCADA-Daten (Polling), normalisiert sie auf ein einheitliches Schema, legt sie in einer eigenen SQLite-DB ab, berechnet KPIs (Ertrag, Verfügbarkeit, Performance Ratio), erkennt Alarme/Anomalien, verwaltet Wartungstickets, stellt eine eigene REST-API bereit. |
| `frontend/` | Zwei Dashboards (React + Vite + Tailwind + Recharts + Leaflet), die ausschließlich gegen die `integration-service`-API sprechen – nie gegen die SCADA-Schicht direkt. |

### Warum diese Trennung?

Das ist der eigentliche Punkt der Übung, nicht nur Ordnerstruktur:

1. **SCADA-Systeme sind heterogen.** Ein Windpark-Hersteller liefert
   OPC-UA-Tags, ein anderer Modbus-Register, ein PV-Wechselrichter eine
   REST-API, ein Batteriespeicher ein proprietäres Protokoll. Die
   Integrationsschicht ist der einzige Ort, der diese Vielfalt kennen muss
   (`scada_client.py` + `normalize.py`) – alles darüber (KPIs, Alarme,
   Dashboards) arbeitet nur noch mit einem einheitlichen Schema.
2. **Ausfallsicherheit.** Wenn eine SCADA-Verbindung wackelt oder ein
   Hersteller seine API ändert, betrifft das nur die Ingestion – nicht die
   Dashboards, die weiter mit den zuletzt bekannten (in der eigenen DB
   liegenden) Werten arbeiten können.
3. **Eigene Historie/Kennzahlen unabhängig vom SCADA-Anbieter.** SCADA-Systeme
   sind meist nicht für Jahre an Historie oder für portfolioweite KPIs
   ausgelegt. Die Integrationsschicht baut eine eigene, dauerhafte
   Datengrundlage auf, aus der Reports, Abrechnungen, ML-Modelle etc.
   gespeist werden können.
4. **Kunden vs. Techniker sind unterschiedliche Zielgruppen** auf derselben
   Datengrundlage – deshalb zwei Frontend-Ansichten über eine gemeinsame API,
   nicht zwei getrennte Datenpfade.

## Wie eine echte SCADA-Anbindung aussehen würde

`scada-simulator/` ist reiner Mock. In einer echten Anbindung würde
**ausschließlich `integration-service/app/scada_client.py`** ausgetauscht –
der Rest der Integrationsschicht (Normalisierung, KPIs, Alarme, API) bliebe
unverändert, weil er nur mit dem eigenen normalisierten Schema arbeitet.
Konkret, je nach Hersteller/Anlagentyp:

- **OPC-UA** (häufig bei WEA-Herstellern, z.B. nach IEC 61400-25): ein
  OPC-UA-Client (z.B. `asyncua` in Python) abonniert Tags/Nodes statt sie per
  REST zu pollen – Push statt Pull, aber dieselbe Normalisierungslogik danach.
- **Modbus TCP/RTU** (häufig bei PV-Wechselrichtern, Zählern): ein
  Modbus-Client (z.B. `pymodbus`) liest Register nach Herstellerbelegung
  (Register-Map) aus und mappt sie auf dieselben normalisierten Metriken.
- **IEC 61850** (v.a. Umspannwerke/Netzanschlusspunkte): ein MMS-/GOOSE-Client
  liest Prozessdaten strukturiert nach Logical Nodes.
- **Hersteller-Cloud-APIs** (z.B. SMA, Fronius, Vestas, proprietäre
  Batteriespeicher-BMS-Portale): REST/GraphQL-Clients mit
  herstellerspezifischer Authentifizierung – ähnlich zu diesem Mock, aber
  mit echter Auth statt offenem Endpunkt.
- Häufig kommt zusätzlich ein **Protokoll-Gateway** (z.B. Kepware, Ignition)
  zum Einsatz, das mehrere Feldprotokolle bereits vor Ort auf einheitliches
  OPC-UA/MQTT normalisiert – dann bräuchte man nur noch einen OPC-UA/MQTT-Client.

Auch **MQTT** ist üblich (viele moderne SCADA-Gateways publizieren Tags als
MQTT-Topics) – in dieser Demo wurde stattdessen REST-Polling gewählt, weil es
für eine Ein-Tages-Demo ohne Message-Broker-Infrastruktur schneller
umzusetzen und einfacher nachzuvollziehen ist. Die Ingestion-Struktur
(`ingestion.py`: Backfill + Polling-Schleife) wäre bei MQTT dieselbe, nur
würde `poll_once()` durch einen Subscriber-Callback ersetzt.

## Backfill: warum die Demo nicht bei Null anfängt

Beim ersten Start lädt `integration-service` einmalig 30 Tage Historie aus
dem Mock-SCADA nach (`BACKFILL_DAYS`), damit KPI-Charts sofort einen
sinnvollen Verlauf zeigen. Das dauert beim ersten Start **ca. 1–2 Minuten**
(bei 126 Anlagen × 30 Tage stündliche Werte). Ab dem zweiten Start wird der
Backfill übersprungen, weil bereits Daten in der DB liegen. Danach läuft ein
Live-Poll alle 15 Sekunden (`POLL_INTERVAL_SECONDS`).

## Starten

Voraussetzung: Docker + Docker Compose.

```bash
docker compose up --build
```

Danach erreichbar:

- Frontend (Dashboards): http://localhost:5173
- Integrationsschicht-API (eigene API, Swagger-UI): http://localhost:8000/docs
- Mock-SCADA-API (Swagger-UI): http://localhost:8001/docs

Der erste Start dauert wegen des Backfills etwas länger (siehe oben) – im
Log von `integration-service` sieht man den Fortschritt
(`Backfill: 80/126 Anlagen geladen`).

## Die beiden Dashboards

- **Kunden-Dashboard** (`/`): Portfolio-Übersicht, Kartenansicht der
  Standorte, Ertragsverlauf (30 Tage, nach Anlagenart), CO2-Einsparung –
  bewusst reduziert auf Kennzahlen, die für Investoren/Betreiber relevant sind.
- **Service-Dashboard** (`/service`): Anlagenliste mit Filtern (Typ, Status,
  Suche), priorisierte Alarmliste, Wartungstickets, Klick auf eine Anlage
  öffnet die Detailansicht mit Live-SCADA-Werten, Verlaufschart und einem
  einfachen Predictive-Maintenance-Hinweis.

## Wichtige Vereinfachungen (bewusst, für eine Ein-Tages-Demo)

- **Alarm-Schwellwerte** wirken auf den jeweils letzten Messwert, nicht auf
  ein gleitendes Zeitfenster – ein Produktivsystem würde kurze Ausreißer
  herausfiltern, bevor ein Alarm ausgelöst wird (siehe Kommentare in
  `integration-service/app/alarms.py`).
- **Predictive Maintenance** ist eine nachvollziehbare Regel (Häufung von
  Störmeldungen), kein ML-Modell (siehe `predictive.py`).
- **CO2-Faktor** ist ein angenommener Demo-Wert
  (`CO2_FACTOR_KG_PER_KWH`), keine offizielle Kennzahl.
- **Verfügbarkeit** ist vereinfacht definiert (Zeit online / Zeit ohne
  geplante Wartung) – ein reales SLA hätte vertraglich exakt definierte
  Ausschlusszeiten.
- Die Kartenansicht nutzt öffentliche OpenStreetMap-Kacheln – dafür ist beim
  Betrachten im Browser eine Internetverbindung nötig (Backend-Daten selbst
  brauchen keine).

## Projektstruktur

```
scada-simulator/         Mock-SCADA-Schicht (Schicht 1)
  app/
    portfolio.py          Anlagen-/Standort-Stammdaten (110 WEA, 4 PV-Parks, 2 BESS)
    simulation.py          Physik: Windkurve, PV-Ertrag, Speicher-Lade-/Entladeschema, Störungen
    models.py               Response-Schemas im SCADA-Tag-Format
    main.py                  Endpunkte: /scada/assets, /scada/live, /scada/history

integration-service/     Integrationsschicht (Schicht 2, das eigentliche Projekt)
  app/
    scada_client.py         Einziger Ort, der die (Mock-)SCADA-Schnittstelle kennt
    normalize.py             Rohe SCADA-Tags -> einheitliches Metrik-Schema
    ingestion.py              Backfill + Live-Polling-Schleife
    models.py / db.py         Eigenes Datenmodell (SQLite via SQLAlchemy)
    kpi.py                    Ertrag, Verfügbarkeit, Performance Ratio
    alarms.py                 Schwellwert-/Anomalie-Erkennung
    maintenance.py            Automatische Wartungsticket-Erzeugung aus Alarmen
    predictive.py             Einfache Risiko-Heuristik
    main.py                   Eigene REST-API für die Dashboards

frontend/                 React (Vite + Tailwind + Recharts + Leaflet)
  src/
    api/client.ts            Typisierter Fetch-Client gegen integration-service
    pages/                    CustomerDashboard, ServiceDashboard, AssetDetailPage
    components/               Karte, Charts, Badges, Stat-Karten
```

## Tech-Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite, httpx
- **Frontend**: React + TypeScript, Vite, Tailwind CSS v4, Recharts,
  React-Leaflet, React Router
- **Start**: Docker Compose (ein Befehl, drei Services)
