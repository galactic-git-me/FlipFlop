# PROMETHEUS 3D reference images

Source images are grouped by the asset keys accepted by the build 3D-generation endpoint. The operator selects only the original `complete_build` photographs. The backend automatically publishes and submits up to four curated professional references for every component asset.

## Readiness

| Asset | Images | Identification | Ready for Meshy |
|---|---:|---|---|
| `complete_build` | 4 | Original PROMETHEUS photographs | Yes |
| `chassis` | 4 | APNX C1 ChromaFlair | Yes |
| `motherboard` | 4 | ASUS PRIME X870-P | Yes |
| `cpu` | 2 | AMD Ryzen 7 7800X3D | Yes |
| `gpu` | 5 | Palit GeForce RTX 3070 GameRock | Select the best four |
| `ram` | 3 | Lexar THOR OC DDR5 family | Review exact SKU before generation |
| `psu` | 4 | Corsair RM750i | Yes |
| `liquid_cooler` | 4 | Thermalright Aqua Elite 240 White V3 | Yes |
| `rgb_fan` | 3 | Thermalright TL-C12CW-S reference | Review against installed case fans |

The saved build record does not include a Lexar RAM SKU and describes the case fans generically. Those folders are deliberately marked for review because capacity and speed alone do not uniquely identify the product's physical design.

See `manifest.json` for source pages and direct asset URLs.
