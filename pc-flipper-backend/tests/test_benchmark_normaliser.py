from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu, normalise_storage, detect_component_type

def test_normalise_cpu_variants():
    assert normalise_cpu("AMD Ryzen 7 7800X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("Ryzen 7 7800X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("R7 7800X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("7800 X3D") == "amd_ryzen_7_7800x3d"
    assert normalise_cpu("Intel Core i7-13700K") == "intel_core_i7_13700k"
    assert normalise_cpu("i7 13700K") == "intel_core_i7_13700k"
    assert normalise_cpu("Core i5-12400F") == "intel_core_i5_12400f"

def test_normalise_gpu_variants():
    assert normalise_gpu("RTX 3070") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("Nvidia RTX3070") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("GeForce RTX 3070") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("3070 8GB") == "nvidia_geforce_rtx_3070"
    assert normalise_gpu("RX 6800 XT") == "amd_radeon_rx_6800_xt"
    assert normalise_gpu("Radeon RX 6800XT") == "amd_radeon_rx_6800_xt"

def test_normalise_storage_variants():
    assert normalise_storage("Samsung 970 EVO 1TB") == "samsung_970_evo_1tb"
    assert normalise_storage("WD Blue SN570 1TB NVMe") == "wd_blue_sn570_1tb"

def test_detect_component_type():
    assert detect_component_type("Ryzen 7 5800X") == "cpu"
    assert detect_component_type("RTX 3080 10GB") == "gpu"
    assert detect_component_type("Samsung 870 EVO 1TB") == "storage"
    assert detect_component_type("32GB DDR4 3200MHz") == "ram"
