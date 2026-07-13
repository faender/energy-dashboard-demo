"""Response-Schemas der eigenen API (das, was Kunden-/Service-Dashboard tatsächlich konsumieren)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AssetOut(BaseModel):
    asset_id: str
    name: str
    site_id: str
    site_name: str
    asset_type: str
    lat: float
    lon: float
    rated_power_kw: float
    capacity_kwp: float | None
    capacity_kwh: float | None
    status: str
    current_power_kw: float | None
    active_alarm_count: int

    class Config:
        from_attributes = True


class LiveValueOut(BaseModel):
    metric: str
    value: float
    timestamp: datetime


class AssetDetailOut(BaseModel):
    asset: AssetOut
    live_values: list[LiveValueOut]
    availability_30d: float
    yield_30d_kwh: float
    performance_ratio_30d: float | None
    risk_level: str
    risk_hint: str
    fault_count_30d: int
    underperformance_count_30d: int


class HistoryPointOut(BaseModel):
    timestamp: datetime
    value: float


class AlarmOut(BaseModel):
    id: int
    asset_id: str
    asset_name: str
    site_name: str
    code: str
    severity: str
    message: str
    source: str
    status: str
    opened_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True


class MaintenanceTicketOut(BaseModel):
    id: int
    asset_id: str
    asset_name: str
    title: str
    description: str
    priority: str
    status: str
    created_at: datetime
    due_date: datetime | None

    class Config:
        from_attributes = True


class PortfolioSummaryOut(BaseModel):
    asset_count: int
    counts_by_status: dict[str, int]
    total_capacity_kw: float
    current_power_kw: float
    today_yield_kwh: float
    month_yield_kwh: float
    co2_saved_today_kg: float
    co2_saved_month_kg: float


class YieldSeriesPointOut(BaseModel):
    date: str
    wind_turbine: float
    pv_park: float
    bess: float


class SiteOut(BaseModel):
    site_id: str
    site_name: str
    asset_type: str
    lat: float
    lon: float
    asset_count: int
    online_count: int
