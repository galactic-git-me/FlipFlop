#!/usr/bin/env python3
"""
Download 3D models from Sketchfab using direct CDN links.

Sketchfab provides direct CDN download links for models without requiring
browser automation or API tokens.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

MEDIA_DIR = Path(__file__).parent.parent / "media" / "3d-models" / "cases"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Sketchfab model IDs and download URLs
MODELS = {
    "corsair_4000d": {
        "sketchfab_id": "bc15e007d6634579bc0e8ffdf238e665",
        "filename": "corsair_4000d.glb",
        "creator": "SzaBa",
        "license": "CC-BY-4.0",
        # Direct download URL for GLB file
        "download_url": "https://cdn.sketchfab.com/models/bc15e007d6634579bc0e8ffdf238e665/model.glb",
        "model_page": "https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665",
    },
    "be_quiet_pure_base_600": {
        "sketchfab_id": "6acb1b906fff44b69c9b8e04361f6b89",
        "filename": "be_quiet_pure_base_600.glb",
        "creator": "JackZeta",
        "license": "CC-BY-4.0",
        "download_url": "https://cdn.sketchfab.com/models/6acb1b906fff44b69c9b8e04361f6b89/model.glb",
        "model_page": "https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89",
    },
    "corsair_5000d": {
        "sketchfab_id": "565f7553ffda415799a6f18fe3174614",
        "filename": "corsair_5000d.glb",
        "creator": "lukeboxfx",
        "license": "CC-BY-4.0",
        "download_url": "https://cdn.sketchfab.com/models/565f7553ffda415799a6f18fe3174614/model.glb",
        "model_page": "https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614",
    },
}


async def download_file(
    url: str,
    output_path: Path,
    filename: str,
) -> tuple[bool, str, Optional[int]]:
    """
    Download a file from a URL.

    Args:
        url: Download URL
        output_path: Path to save the file
        filename: Filename for display

    Returns:
        (success: bool, message: str, file_size: Optional[int])
    """
    if output_path.exists():
        size = output_path.stat().st_size
        size_mb = size / (1024 * 1024)
        return True, f"File already exists ({size_mb:.1f} MB)", size

    try:
        print(f"    Downloading from: {url}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 404:
                return False, "File not found (404)", None
            elif response.status_code == 403:
                return False, "Access denied (403) - Sketchfab may require login", None
            elif response.status_code != 200:
                return False, f"HTTP {response.status_code}", None

            content = response.content
            if not content:
                return False, "Downloaded empty file", None

            # Verify it's a valid GLB file (magic bytes: "glTF")
            if not content.startswith(b"glTF"):
                print(f"    Warning: File doesn't appear to be valid GLB (magic bytes)")
                print(f"    First 20 bytes: {content[:20]}")

            # Save file
            output_path.write_bytes(content)
            size_mb = len(content) / (1024 * 1024)
            print(f"    Saved to: {output_path} ({size_mb:.1f} MB)")

            return True, f"Downloaded ({size_mb:.1f} MB)", len(content)

    except asyncio.TimeoutError:
        return False, "Download timeout (60s)", None
    except Exception as e:
        return False, f"Download error: {str(e)}", None


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
    print("DOWNLOADING 3D MODELS FROM SKETCHFAB CDN")
    print("="*80)
    print(f"\nMedia directory: {MEDIA_DIR}\n")

    for model_key, model_info in MODELS.items():
        print(f"\n[{model_key.upper()}]")
        print(f"  Sketchfab ID: {model_info['sketchfab_id']}")
        print(f"  Creator: {model_info['creator']}")
        print(f"  License: {model_info['license']}")
        print(f"  Model page: {model_info['model_page']}")

        output_path = MEDIA_DIR / model_info["filename"]

        try:
            success, message, file_size = await download_file(
                model_info["download_url"],
                output_path,
                model_info["filename"],
            )

            if success:
                print(f"  Status: ✓ SUCCESS")
                print(f"  Message: {message}")
                print(f"  File: {output_path.name}")
                if file_size:
                    print(f"  Size: {file_size:,} bytes")

                report["models"][model_key] = {
                    "status": "success",
                    "filename": model_info["filename"],
                    "filepath": str(output_path),
                    "file_size": file_size,
                    "creator": model_info["creator"],
                    "license": model_info["license"],
                    "sketchfab_id": model_info["sketchfab_id"],
                }
                report["summary"]["downloaded"] += 1
            else:
                print(f"  Status: ✗ FAILED")
                print(f"  Error: {message}")

                report["models"][model_key] = {
                    "status": "failed",
                    "error": message,
                    "filename": model_info["filename"],
                    "sketchfab_id": model_info["sketchfab_id"],
                }
                report["summary"]["failed"] += 1

        except Exception as e:
            print(f"  Status: ✗ ERROR")
            print(f"  Error: {str(e)}")
            report["models"][model_key] = {
                "status": "error",
                "error": str(e),
                "filename": model_info["filename"],
                "sketchfab_id": model_info["sketchfab_id"],
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
    print(f"\nReport saved to: {report_path}\n")

    return report


if __name__ == "__main__":
    try:
        report = asyncio.run(download_all_models())

        if report["summary"]["downloaded"] > 0:
            print("\nNext steps:")
            print(f"1. Verify downloads: python scripts/verify_3d_models.py")
            print(f"2. Integrate models: python scripts/integrate_3d_models.py")
            print()

        sys.exit(0 if report["summary"]["failed"] == 0 else 1)
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
