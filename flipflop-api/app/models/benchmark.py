from datetime import datetime
from typing import Optional
from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class HardwareBenchmark(Base):
    __tablename__ = "hardware_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_type: Mapped[str] = mapped_column(String(20), index=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(300))
    normalized_model: Mapped[str] = mapped_column(String(300), index=True)
    benchmark_source: Mapped[str] = mapped_column(String(100))
    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    gaming_score: Mapped[Optional[float]] = mapped_column(Float)
    workstation_score: Mapped[Optional[float]] = mapped_column(Float)
    single_thread_score: Mapped[Optional[float]] = mapped_column(Float)
    multi_thread_score: Mapped[Optional[float]] = mapped_column(Float)
    memory_score: Mapped[Optional[float]] = mapped_column(Float)
    storage_score: Mapped[Optional[float]] = mapped_column(Float)
    vram_gb: Mapped[Optional[float]] = mapped_column(Float)
    ram_capacity_gb: Mapped[Optional[float]] = mapped_column(Float)
    ram_speed_mts: Mapped[Optional[float]] = mapped_column(Float)
    ram_latency_cl: Mapped[Optional[float]] = mapped_column(Float)
    storage_capacity_gb: Mapped[Optional[float]] = mapped_column(Float)
    storage_interface: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_refreshed_at: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())


class ComponentPerformanceMetric(Base):
    __tablename__ = "component_performance_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_listing_id: Mapped[Optional[str]] = mapped_column(String(100))
    component_type: Mapped[str] = mapped_column(String(20), index=True)
    normalized_model: Mapped[str] = mapped_column(String(300), index=True)
    acquisition_price: Mapped[Optional[float]] = mapped_column(Float)
    benchmark_score: Mapped[Optional[float]] = mapped_column(Float)
    gaming_score: Mapped[Optional[float]] = mapped_column(Float)
    workstation_score: Mapped[Optional[float]] = mapped_column(Float)
    performance_per_pound: Mapped[Optional[float]] = mapped_column(Float)
    gaming_per_pound: Mapped[Optional[float]] = mapped_column(Float)
    workstation_per_pound: Mapped[Optional[float]] = mapped_column(Float)
    marketability_score: Mapped[Optional[float]] = mapped_column(Float)
    demand_score: Mapped[Optional[float]] = mapped_column(Float)
    liquidity_score: Mapped[Optional[float]] = mapped_column(Float)
    opportunity_score: Mapped[Optional[float]] = mapped_column(Float)
    calculated_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())


class BenchmarkRefreshRun(Base):
    __tablename__ = "benchmark_refresh_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[Optional[str]] = mapped_column(String(20))
    started_at: Mapped[Optional[str]] = mapped_column(String(50))
    completed_at: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    components_checked: Mapped[int] = mapped_column(Integer, default=0)
    components_updated: Mapped[int] = mapped_column(Integer, default=0)
    components_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(20))
    error_log: Mapped[Optional[str]] = mapped_column(Text)
