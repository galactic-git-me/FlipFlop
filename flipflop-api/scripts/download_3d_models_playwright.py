#!/usr/bin/env python3
"""
Download 3D models from Sketchfab using Playwright browser automation.

This script uses Playwright to automate the download process, which is necessary
because Sketchfab requires authentication and has CSRF protections that standard
HTTP requests cannot bypass.

Usage:
    python download_3d_models_playwright.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

MEDIA_DIR = Path(__file__).parent.parent / "media" / "3d-models" / "cases"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

MODELS = {
    "corsair_4000d": {
        "url": "https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665",
        "filename": "corsair_4000d.glb",
        "creator": "SzaBa",
        "license": "CC-BY-4.0",
    },
    "be_quiet_pure_base_600": {
        "url": "https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89",
        "filename": "be_quiet_pure_base_600.glb",
        "creator": "JackZeta",
        "license": "CC-BY-4.0",
    },
    "corsair_5000d": {
        "url": "https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614",
        "filename": "corsair_5000d.glb",
        "creator": "lukeboxfx",
        "license": "CC-BY-4.0",
    },
}


async def download_model_with_browser(url: str, output_path: Path) -> tuple[bool, str]:
    """
    Download a model from Sketchfab using Playwright.

    Args:
        url: Sketchfab model URL (without /download suffix)
        output_path: Path to save the GLB file

    Returns:
        (success: bool, message: str)
    """
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        return True, f"File already exists ({size_mb:.1f} MB)"

    async with async_playwright() as p:
        try:
            print(f"    Launching browser...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Set download path
            await context.expect_download(async_action=lambda: None)

            print(f"    Navigating to: {url}")
            await page.goto(url, wait_until="networkidle")

            # Wait for the page to load
            await page.wait_for_timeout(2000)

            # Look for download button - Sketchfab has a download icon/button
            # The button might be in different places depending on the page state
            print(f"    Looking for download button...")

            # Try multiple selectors for the download button
            selectors = [
                'button[aria-label*="Download"]',
                'button[aria-label*="download"]',
                'a[href*="download"]',
                '[data-testid="download-button"]',
                '.downloadButton',
            ]

            download_clicked = False
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"    Found download button with selector: {selector}")
                        await elements[0].click()
                        download_clicked = True
                        break
                except Exception:
                    pass

            if not download_clicked:
                # Try to find and click via JavaScript
                print(f"    Trying JavaScript-based download...")
                try:
                    # Look for download link in page
                    download_link = await page.evaluate("""
                        () => {
                            const links = Array.from(document.querySelectorAll('a[href*="download"]'));
                            return links[0]?.href || null;
                        }
                    """)

                    if download_link:
                        print(f"    Found download link: {download_link}")
                        async with page.expect_download() as download_info:
                            await page.goto(download_link)
                        download = await download_info.value
                        await download.save_as(output_path)
                        size_mb = output_path.stat().st_size / (1024 * 1024)
                        await browser.close()
                        return True, f"Downloaded ({size_mb:.1f} MB)"
                except Exception as e:
                    print(f"    JavaScript download failed: {e}")

            # If we got here, try to handle the download via event listener
            print(f"    Waiting for download to complete...")
            async with page.expect_download() as download_info:
                # The download might start when we click the button above
                # If not, we need to find another trigger
                if not download_clicked:
                    await page.evaluate("document.querySelector('[data-testid=\"download-button\"]')?.click()")

                # Wait for download with timeout
                try:
                    download = await download_info.value
                    await download.save_as(output_path)
                    size_mb = output_path.stat().st_size / (1024 * 1024)
                    print(f"    Download completed: {size_mb:.1f} MB")
                except asyncio.TimeoutError:
                    print(f"    Download timeout - file may not exist yet")
                    await browser.close()
                    return False, "Download timed out"

            await browser.close()

            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                return True, f"Downloaded ({size_mb:.1f} MB)"
            else:
                return False, "Download completed but file not saved"

        except Exception as e:
            return False, f"Browser error: {str(e)}"


async def download_all_models() -> dict:
    """Download all models and return a report."""
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "media_directory": str(MEDIA_DIR),
        "models": {},
        "summary": {
            "total": len(MODELS),
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
        },
    }

    print("\n" + "="*80)
    print("DOWNLOADING 3D MODELS FROM SKETCHFAB")
    print("="*80)
    print(f"\nMedia directory: {MEDIA_DIR}\n")

    for model_key, model_info in MODELS.items():
        print(f"\n[{model_key}]")
        print(f"  URL: {model_info['url']}")
        print(f"  Creator: {model_info['creator']}")
        print(f"  License: {model_info['license']}")

        output_path = MEDIA_DIR / model_info["filename"]

        try:
            success, message = await download_model_with_browser(model_info["url"], output_path)

            if success:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                print(f"  Status: SUCCESS - {message}")
                print(f"  File: {output_path}")
                print(f"  Size: {file_size:,} bytes")

                report["models"][model_key] = {
                    "status": "success",
                    "filename": model_info["filename"],
                    "filepath": str(output_path),
                    "file_size": file_size,
                    "creator": model_info["creator"],
                    "license": model_info["license"],
                }
                report["summary"]["downloaded"] += 1
            else:
                print(f"  Status: FAILED - {message}")
                report["models"][model_key] = {
                    "status": "failed",
                    "error": message,
                    "filename": model_info["filename"],
                }
                report["summary"]["failed"] += 1

        except Exception as e:
            print(f"  Status: ERROR - {str(e)}")
            report["models"][model_key] = {
                "status": "error",
                "error": str(e),
                "filename": model_info["filename"],
            }
            report["summary"]["failed"] += 1

    # Save report
    report_path = MEDIA_DIR / "download_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "="*80)
    print("DOWNLOAD SUMMARY")
    print("="*80)
    print(f"Total models: {report['summary']['total']}")
    print(f"Downloaded: {report['summary']['downloaded']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Skipped: {report['summary']['skipped']}")
    print(f"\nReport saved to: {report_path}")

    return report


if __name__ == "__main__":
    try:
        report = asyncio.run(download_all_models())
        sys.exit(0 if report["summary"]["failed"] == 0 else 1)
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
