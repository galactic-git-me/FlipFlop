from app.services.benchmark_fetcher import (
    parse_passmark_cpu_table,
    parse_passmark_gpu_table,
    parse_passmark_disk_table,
    BenchmarkRecord,
)

_CPU_HTML = """
<table id="cputable">
<tr><td>1</td><td><a href="/cpu/AMD-Ryzen-9-9950X">AMD Ryzen 9 9950X</a></td><td>68,985</td></tr>
<tr><td>2</td><td><a href="/cpu/AMD-Ryzen-7-7800X3D">AMD Ryzen 7 7800X3D</a></td><td>34,212</td></tr>
<tr><td>3</td><td><a href="/cpu/Intel-Core-i9-14900K">Intel Core i9-14900K</a></td><td>63,445</td></tr>
</table>
"""

_GPU_HTML = """
<table id="gputable">
<tr><td>1</td><td><a href="/gpu/NVIDIA-GeForce-RTX-4090">NVIDIA GeForce RTX 4090</a></td><td>38,000</td></tr>
<tr><td>2</td><td><a href="/gpu/NVIDIA-GeForce-RTX-3070">NVIDIA GeForce RTX 3070</a></td><td>17,500</td></tr>
</table>
"""

_DISK_HTML = """
<table id="disktable">
<tr><td>1</td><td><a href="/disk/Samsung-970-EVO-1TB">Samsung 970 EVO 1TB</a></td><td>4,500</td></tr>
</table>
"""

def test_parse_passmark_cpu_table():
    records = parse_passmark_cpu_table(_CPU_HTML)
    assert len(records) == 3
    r = records[1]  # 7800X3D
    assert "7800X3D" in r.model
    assert r.overall_score == 34212
    assert r.component_type == "cpu"

def test_parse_passmark_gpu_table():
    records = parse_passmark_gpu_table(_GPU_HTML)
    assert len(records) == 2
    r = records[1]  # RTX 3070
    assert "3070" in r.model
    assert r.overall_score == 17500
    assert r.component_type == "gpu"

def test_parse_passmark_disk_table():
    records = parse_passmark_disk_table(_DISK_HTML)
    assert len(records) == 1
    assert records[0].overall_score == 4500
    assert records[0].component_type == "storage"

def test_benchmark_record_normalised_model():
    records = parse_passmark_cpu_table(_CPU_HTML)
    r7 = next(r for r in records if "7800" in r.model)
    assert r7.normalized_model == "amd_ryzen_7_7800x3d"
