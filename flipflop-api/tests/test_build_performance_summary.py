from app.services.build_performance_summary import (
    generate_build_performance_summary,
    generate_listing_performance_text,
    classify_tier,
)

def test_classify_tier_cpu():
    assert classify_tier("cpu", 60000) == "Flagship"
    assert classify_tier("cpu", 30000) == "High-End"
    assert classify_tier("cpu", 15000) == "Mid-Range"
    assert classify_tier("cpu", 5000) == "Entry"

def test_classify_tier_gpu():
    assert classify_tier("gpu", 30000) == "Flagship"
    assert classify_tier("gpu", 15000) == "High-End"
    assert classify_tier("gpu", 8000) == "Mid-Range"
    assert classify_tier("gpu", 2000) == "Entry"

def test_generate_build_performance_summary_structure():
    summary = generate_build_performance_summary(
        cpu_model="Ryzen 7 7800X3D",
        cpu_score=34000,
        gpu_model="RTX 3070",
        gpu_score=17500,
        vram_gb=8,
        ram_gb=32,
        ram_speed_mts=5600,
        storage_gb=1000,
        storage_interface="PCIe 4.0 NVMe",
    )
    assert "cpu" in summary
    assert "gpu" in summary
    assert "overall" in summary
    assert summary["cpu"]["tier"] == "High-End"
    assert summary["gpu"]["tier"] == "High-End"

def test_generate_listing_performance_text_gaming():
    text = generate_listing_performance_text(
        use_case="gaming",
        cpu_model="Ryzen 7 7800X3D",
        cpu_tier="High-End",
        gpu_model="RTX 3070",
        gpu_tier="High-End",
        ram_gb=32,
        storage_interface="PCIe 4.0 NVMe",
    )
    assert "gaming" in text.lower()
    assert "7800X3D" in text or "Ryzen 7" in text
