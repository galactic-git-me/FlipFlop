#!/usr/bin/env python3
"""
Automated Sketchfab Model Downloader
Downloads all 3D models for FlipFlop high-end gaming build
Uses Playwright for browser automation
"""

import asyncio
import os
import zipfile
import shutil
from pathlib import Path
from urllib.parse import urljoin
import logging

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: Playwright not installed")
    print("Install with: pip install playwright")
    print("Then setup browsers with: playwright install")
    exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Model download configuration
MODELS_CONFIG = {
    "gpu": [
        {
            "variant": 1,
            "name": "RTX 4090",
            "search": "RTX 4090 OR \"nvidia RTX 4090\" OR \"graphics card RTX 4090\" OR \"4090 GPU\" RGB"
        },
        {
            "variant": 2,
            "name": "RTX 4080",
            "search": "RTX 4080 OR RTX 4070 Ti OR \"nvidia graphics card\" high-end RGB"
        },
        {
            "variant": 3,
            "name": "RTX 3090 Ti",
            "search": "RTX 3090 Ti OR \"graphics card\" high-end OR nvidia GPU professional"
        }
    ],
    "cpu": [
        {
            "variant": 1,
            "name": "Intel i9 + Tower Cooler",
            "search": "\"CPU cooler\" \"RGB\" OR \"tower cooler\" RGB intel OR \"Noctua NH-D15\" OR \"be quiet Dark Rock\" RGB"
        },
        {
            "variant": 2,
            "name": "Ryzen 9 + AIO Cooler",
            "search": "\"liquid cooler\" \"AIO\" RGB OR \"water cooler\" RGB OR \"NZXT Kraken\" OR \"Corsair H150i\" RGB"
        },
        {
            "variant": 3,
            "name": "CPU + RGB Cooler",
            "search": "\"CPU cooler\" RGB gaming OR processor cooler illuminated OR tower cooler RGB lights"
        }
    ],
    "ram": [
        {
            "variant": 1,
            "name": "DDR5 RGB",
            "search": "DDR5 RAM RGB OR \"memory stick\" RGB LED OR Corsair Dominator RGB OR G.Skill Trident RGB"
        },
        {
            "variant": 2,
            "name": "DDR5 RGB Alt",
            "search": "\"DDR5\" \"RGB\" OR Kingston Fury Beast RGB OR Crucial T-Force RGB memory"
        },
        {
            "variant": 3,
            "name": "DDR5 RGB Variant",
            "search": "DDR5 \"RGB\" OR memory stick \"LED\" OR RAM gaming illuminated OR DDR5 premium"
        }
    ],
    "storage": [
        {
            "variant": 1,
            "name": "NVMe RGB",
            "search": "\"NVMe\" \"RGB\" OR \"M.2 SSD\" RGB OR Samsung 990 Pro RGB OR Corsair MP600 RGB OR \"SSD\" \"RGB\""
        },
        {
            "variant": 2,
            "name": "NVMe RGB Alt",
            "search": "NVMe SSD \"RGB\" OR M.2 drive LED OR \"nvme\" \"illuminated\" OR \"high speed storage\" RGB"
        },
        {
            "variant": 3,
            "name": "High-Cap NVMe",
            "search": "\"2TB NVMe\" OR \"4TB SSD\" RGB OR high capacity storage RGB OR \"SSD\" \"LED\" gaming"
        }
    ],
    "cases": [
        {
            "variant": 1,
            "name": "Black Aquarium",
            "search": "\"aquarium case\" black OR \"black aquarium\" PC case OR glass case black gaming OR tempered glass showcase"
        },
        {
            "variant": 2,
            "name": "White Aquarium",
            "search": "\"aquarium case\" white OR \"white aquarium\" PC case OR glass case white gaming OR tempered glass white"
        },
        {
            "variant": 3,
            "name": "Lian Li Dark Mirror",
            "search": "\"Lian Li\" \"Dark Mirror\" OR \"LANCOOL\" \"Dark Mirror\" OR Lian Li chrome case OR \"Dark Mirror\" PC case"
        },
        {
            "variant": 4,
            "name": "NZXT/Corsair",
            "search": "\"NZXT H510 Flow\" OR \"Corsair Crystal\" OR \"high-end gaming case\" tempered glass OR showcase PC case"
        }
    ]
}

class SketchfabDownloader:
    def __init__(self):
        self.base_url = "https://sketchfab.com"
        self.models_dir = Path("public/models")
        self.temp_dir = Path("temp_downloads")

    async def download_model(self, page, component_type: str, model_info: dict) -> bool:
        """Download a single model"""
        variant = model_info["variant"]
        name = model_info["name"]
        search_term = model_info["search"]

        output_dir = self.models_dir / component_type
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"variant-{variant}.gltf"

        # Skip if already exists
        if output_file.exists():
            logger.info(f"✓ {component_type}/variant-{variant} already exists, skipping")
            return True

        try:
            logger.info(f"Searching: {component_type}/{variant} ({name})")

            # Navigate to Sketchfab search with CC filters
            search_url = f"{self.base_url}/search?q={search_term}&type=models&license=CC0"
            await page.goto(search_url, wait_until="networkidle", timeout=30000)

            # Wait for results to load
            try:
                await page.wait_for_selector('[data-test="search-results-item"]', timeout=10000)
            except:
                logger.warning(f"No results found for {component_type}/{variant}")
                return False

            # Click first result
            first_result = await page.query_selector('[data-test="search-results-item"] a')
            if not first_result:
                logger.warning(f"No clickable result for {component_type}/{variant}")
                return False

            model_url = await first_result.get_attribute("href")
            await page.goto(urljoin(self.base_url, model_url), wait_until="networkidle", timeout=30000)

            # Scroll to download section
            await page.evaluate("window.scrollBy(0, window.innerHeight)")

            # Find download button
            download_button = None
            try:
                download_button = await page.query_selector('a[download]')
            except:
                pass

            if not download_button:
                logger.warning(f"No download button found for {component_type}/{variant}")
                return False

            # Setup download handler
            async with page.expect_download() as download_info:
                await download_button.click()

            download = await download_info.value

            # Save to temp directory
            self.temp_dir.mkdir(exist_ok=True)
            temp_path = self.temp_dir / download.suggested_filename
            await download.save_as(temp_path)

            logger.info(f"  Downloaded: {temp_path.name}")

            # Extract if ZIP
            if temp_path.suffix.lower() == ".zip":
                extract_dir = self.temp_dir / f"extract_{component_type}_{variant}"
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                # Find .gltf or .glb file
                gltf_file = None
                for file in extract_dir.rglob("*.gltf"):
                    gltf_file = file
                    break
                if not gltf_file:
                    for file in extract_dir.rglob("*.glb"):
                        gltf_file = file
                        break

                if gltf_file:
                    shutil.copy2(gltf_file, output_file)
                    logger.info(f"✓ Extracted and saved: {output_file.name}")
                else:
                    logger.error(f"No glTF/GLB file found in archive for {component_type}/{variant}")
                    return False
            else:
                # Copy directly (probably .glb)
                shutil.copy2(temp_path, output_file)
                logger.info(f"✓ Saved: {output_file.name}")

            # Cleanup temp file
            temp_path.unlink()
            return True

        except Exception as e:
            logger.error(f"Error downloading {component_type}/{variant}: {e}")
            return False

    async def run(self):
        """Main download loop"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Set timeout
            page.set_default_timeout(30000)

            total = sum(len(models) for models in MODELS_CONFIG.values())
            completed = 0

            for component_type, models in MODELS_CONFIG.items():
                logger.info(f"\n{'='*60}")
                logger.info(f"{component_type.upper()}")
                logger.info(f"{'='*60}")

                for model in models:
                    if await self.download_model(page, component_type, model):
                        completed += 1

                    # Rate limiting (be nice to Sketchfab)
                    await asyncio.sleep(3)

            await browser.close()

        # Cleanup temp directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        logger.info(f"\n{'='*60}")
        logger.info(f"Download complete: {completed}/{total} models")
        logger.info(f"{'='*60}")
        logger.info(f"Models saved to: public/models/")
        logger.info(f"\nNext: npm run dev -- --port 3001")
        logger.info(f"Then: visit http://andromeda-ts:3001/configure/gaming-rig")

async def main():
    downloader = SketchfabDownloader()
    await downloader.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nDownload interrupted by user")
        exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)
