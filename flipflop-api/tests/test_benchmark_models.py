import pytest
from sqlalchemy import inspect
from app.models.benchmark import HardwareBenchmark, ComponentPerformanceMetric, BenchmarkRefreshRun
from app.database import Base

def test_hardware_benchmark_tablename():
    assert HardwareBenchmark.__tablename__ == "hardware_benchmarks"

def test_component_performance_metric_tablename():
    assert ComponentPerformanceMetric.__tablename__ == "component_performance_metrics"

def test_benchmark_refresh_run_tablename():
    assert BenchmarkRefreshRun.__tablename__ == "benchmark_refresh_runs"

def test_hardware_benchmark_required_columns():
    cols = {c.key for c in inspect(HardwareBenchmark).mapper.column_attrs}
    assert {"component_type", "model", "normalized_model", "benchmark_source", "overall_score"} <= cols
