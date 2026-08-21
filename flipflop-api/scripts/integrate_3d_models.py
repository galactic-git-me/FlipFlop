#!/usr/bin/env python3
"""
Download 3D models from Sketchfab and integrate into FlipFlop database.

This script:
1. Downloads GLB files from Sketchfab
2. Extracts model metadata (vertices, polygons, file size)
3. Updates the cases table with model references
4. Generates a summary report
"""

import os
import sys
import json
import gzip
import struct
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime
import asyncio
import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, engine, init_db
from app.models.case import Case
from sqlalchemy import select

MEDIA_DIR = Path(__file__).parent.parent / "media" / "3d-models" / "cases"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Model download configuration
MODELS = {
    "corsair_4000d": {
        "url": "https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665/download",
        "filename": "corsair_4000d.glb",
        "creator": "SzaBa",
        "license": "CC-BY-4.0",
        "case_names": ["corsair 4000d", "corsair frame 4000d"],
    },
    "be_quiet_pure_base_600": {
        "url": "https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89/download",
        "filename": "be_quiet_pure_base_600.glb",
        "creator": "JackZeta",
        "license": "CC-BY-4.0",
        "case_names": ["pure base 600", "be quiet pure base 600"],
    },
    "corsair_5000d": {
        "url": "https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614/download",
        "filename": "corsair_5000d.glb",
        "creator": "lukeboxfx",
        "license": "CC-BY-4.0",
        "case_names": ["corsair 5000d", "corsair icue 5000d", "corsair icue 5000d rgb"],
    },
}


def extract_glb_metadata(glb_path: Path) -> Dict[str, Optional[int]]:
    """
    Extract metadata from a GLB file.

    GLB format:
    - 12-byte header (magic, version, length)
    - JSON chunk (type 0x4E4F4A) with asset info
    - BIN chunk (type 0x004E4942) with mesh data

    This extracts vertex and polygon count from the mesh data.
    """
    metadata = {"vertices": None, "polygons": None, "file_size": 0}

    if not glb_path.exists():
        return metadata

    try:
        with open(glb_path, "rb") as f:
            # Read header (12 bytes)
            header = f.read(12)
            if len(header) < 12:
                return metadata

            magic = header[0:4]
            if magic != b"glTF":
                print(f"  Warning: Not a valid GLB file (magic: {magic})")
                return metadata

            # Get file size
            metadata["file_size"] = glb_path.stat().st_size

            version = struct.unpack("<I", header[4:8])[0]
            length = struct.unpack("<I", header[8:12])[0]

            if version != 2:
                print(f"  Warning: GLB version {version} not 2")
                return metadata

            # Read chunks
            position = 12
            vertices_count = 0
            polygon_count = 0

            while position < length:
                # Read chunk header (8 bytes)
                f.seek(position)
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    break

                chunk_length = struct.unpack("<I", chunk_header[0:4])[0]
                chunk_type = struct.unpack("<I", chunk_header[4:8])[0]

                position += 8 + chunk_length
                aligned_position = ((position + 3) // 4) * 4  # Align to 4-byte boundary

                # JSON chunk (type 0x4E4F4A = "JSON" in little-endian)
                if chunk_type == 0x4E4F4A:
                    json_data = f.read(chunk_length)
                    try:
                        asset_data = json.loads(json_data.decode("utf-8"))

                        # Extract mesh information from accessors
                        if "accessors" in asset_data:
                            for accessor in asset_data["accessors"]:
                                if accessor.get("type") == "VEC3" and accessor.get(
                                    "componentType"
                                ) == 5126:  # Float32 component type
                                    # This is likely vertex position data
                                    count = accessor.get("count", 0)
                                    if count > vertices_count:
                                        vertices_count = count

                        # Extract triangle count from primitive
                        if "meshes" in asset_data:
                            for mesh in asset_data["meshes"]:
                                if "primitives" in mesh:
                                    for primitive in mesh["primitives"]:
                                        indices_idx = primitive.get("indices")
                                        if indices_idx is not None:
                                            indices_accessor = asset_data["accessors"][
                                                indices_idx
                                            ]
                                            # Triangle count = indices count / 3
                                            triangle_count = (
                                                indices_accessor.get("count", 0) // 3
                                            )
                                            polygon_count += triangle_count

                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        print(f"  Warning: Could not parse JSON chunk: {e}")

                position = aligned_position

            metadata["vertices"] = vertices_count if vertices_count > 0 else None
            metadata["polygons"] = polygon_count if polygon_count > 0 else None

    except Exception as e:
        print(f"  Error reading GLB file: {e}")

    return metadata


def estimate_quality(polygon_count: Optional[int]) -> str:
    """Estimate quality level based on polygon count."""
    if polygon_count is None:
        return "unknown"
    elif polygon_count < 10000:
        return "low"
    elif polygon_count < 100000:
        return "medium"
    else:
        return "high"


async def download_model(model_key: str, model_info: dict) -> Tuple[bool, str]:
    """
    Download a model from Sketchfab.

    Note: Sketchfab download URLs require proper authentication headers.
    Without a valid Sketchfab account or API token, downloads will fail with 403.
    """
    filepath = MEDIA_DIR / model_info["filename"]

    if filepath.exists():
        print(f"  File already exists: {filepath}")
        return True, str(filepath)

    print(f"  Downloading from: {model_info['url']}")

    try:
        async with httpx.AsyncClient() as client:
            # Sketchfab requires User-Agent and proper session
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            }

            response = await client.get(model_info["url"], headers=headers, follow_redirects=True, timeout=30.0)

            if response.status_code == 403:
                return False, (
                    f"Access denied (403). Sketchfab requires authentication to download. "
                    f"Please visit {model_info['url']} manually and download the GLB file."
                )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"

            # Save file
            with open(filepath, "wb") as f:
                f.write(response.content)

            print(f"  Saved to: {filepath} ({len(response.content)} bytes)")
            return True, str(filepath)

    except httpx.TimeoutException:
        return False, "Download timeout"
    except Exception as e:
        return False, f"Download error: {str(e)}"


async def match_case_names(session, model_key: str, case_names: list) -> Optional[int]:
    """Find a case in the database matching any of the provided names."""
    query = select(Case.id, Case.name).where(Case.source_site.in_(["Amazon", "eBay", "Overclockers"]))

    result = await session.execute(query)
    cases = result.fetchall()

    for case_id, case_name in cases:
        case_name_lower = case_name.lower()
        if any(cn.lower() in case_name_lower for cn in case_names):
            return case_id

    return None


async def integrate_models() -> None:
    """Main integration workflow."""
    print("\n" + "=" * 80)
    print("3D MODEL INTEGRATION FOR SKETCHFAB CASES")
    print("=" * 80)

    await init_db()

    # Summary report
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "media_directory": str(MEDIA_DIR),
        "models": {},
        "summary": {
            "total_models": len(MODELS),
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
        },
    }

    print(f"\nMedia directory: {MEDIA_DIR}\n")

    # Download models
    for model_key, model_info in MODELS.items():
        print(f"\nProcessing: {model_key}")
        print(f"  Creator: {model_info['creator']}")
        print(f"  License: {model_info['license']}")

        # Try to download
        success, message = await download_model(model_key, model_info)

        if not success:
            print(f"  Download FAILED: {message}")
            report["models"][model_key] = {
                "status": "failed",
                "error": message,
                "filepath": None,
                "metadata": None,
            }
            report["summary"]["failed"] += 1
            continue

        # Extract metadata from downloaded file
        filepath = MEDIA_DIR / model_info["filename"]
        metadata = extract_glb_metadata(filepath)
        quality = estimate_quality(metadata.get("polygons"))

        print(f"  Metadata:")
        print(f"    Vertices: {metadata['vertices']}")
        print(f"    Polygons: {metadata['polygons']}")
        print(f"    File size: {metadata['file_size']} bytes")
        print(f"    Quality: {quality}")

        # Find matching case in database
        async with AsyncSessionLocal() as session:
            case_id = await match_case_names(session, model_key, model_info["case_names"])

            if case_id:
                print(f"  Found matching case ID: {case_id}")

                # Update case record
                case = await session.get(Case, case_id)
                if case:
                    case.has_3d_model = True
                    case.model_3d_url = f"/media/3d-models/cases/{model_info['filename']}"
                    case.model_3d_source = "sketchfab"
                    case.model_3d_creator = model_info["creator"]
                    case.model_3d_license = model_info["license"]
                    case.model_3d_quality = quality
                    case.model_3d_vertices = metadata.get("vertices")
                    case.model_3d_polygons = metadata.get("polygons")
                    case.model_3d_file_size = metadata.get("file_size")

                    await session.commit()
                    print(f"  Case record updated successfully")
            else:
                print(f"  No matching case found (manual update required)")

        report["models"][model_key] = {
            "status": "completed",
            "filepath": str(filepath),
            "creator": model_info["creator"],
            "license": model_info["license"],
            "metadata": {
                "vertices": metadata.get("vertices"),
                "polygons": metadata.get("polygons"),
                "file_size": metadata.get("file_size"),
                "quality": quality,
            },
            "case_id": case_id,
        }
        report["summary"]["downloaded"] += 1

    # Write report
    report_path = MEDIA_DIR / "integration_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("INTEGRATION SUMMARY")
    print("=" * 80)
    print(f"Total models: {report['summary']['total_models']}")
    print(f"Downloaded: {report['summary']['downloaded']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Skipped: {report['summary']['skipped']}")
    print(f"\nReport saved to: {report_path}")
    print()


if __name__ == "__main__":
    asyncio.run(integrate_models())
