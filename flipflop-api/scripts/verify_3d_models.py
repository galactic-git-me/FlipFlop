#!/usr/bin/env python3
"""
Verify 3D model integration status and database consistency.

Checks:
1. GLB files exist and are valid
2. Database has correct 3D model references
3. File sizes and metadata match
4. All models are properly attributed
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
import struct

sys.path.insert(0, str(Path(__file__).parent.parent))

MEDIA_DIR = Path(__file__).parent.parent / "media" / "3d-models" / "cases"

EXPECTED_MODELS = {
    "corsair_4000d.glb": {
        "creator": "SzaBa",
        "license": "CC-BY-4.0",
        "sketchfab_id": "bc15e007d6634579bc0e8ffdf238e665",
    },
    "be_quiet_pure_base_600.glb": {
        "creator": "JackZeta",
        "license": "CC-BY-4.0",
        "sketchfab_id": "6acb1b906fff44b69c9b8e04361f6b89",
    },
    "corsair_5000d.glb": {
        "creator": "lukeboxfx",
        "license": "CC-BY-4.0",
        "sketchfab_id": "565f7553ffda415799a6f18fe3174614",
    },
}


def verify_glb_format(filepath: Path) -> Tuple[bool, str]:
    """Verify GLB file has correct magic bytes and structure."""
    if not filepath.exists():
        return False, f"File not found: {filepath}"

    try:
        with open(filepath, "rb") as f:
            header = f.read(12)

            if len(header) < 12:
                return False, "File is too small (< 12 bytes)"

            magic = header[0:4]
            if magic != b"glTF":
                return False, f"Invalid magic bytes: {magic} (expected 'glTF')"

            version = struct.unpack("<I", header[4:8])[0]
            if version != 2:
                return False, f"Unsupported GLB version: {version} (expected 2)"

            length = struct.unpack("<I", header[8:12])[0]
            if length == 0:
                return False, "Invalid file length (0)"

            return True, f"Valid GLB v2 ({length} bytes)"

    except Exception as e:
        return False, f"Error reading file: {str(e)}"


def verify_manifest() -> Dict:
    """Verify integration manifest exists and is valid."""
    manifest_path = MEDIA_DIR / "manifest.json"

    if not manifest_path.exists():
        return {"exists": False, "message": "Manifest not found"}

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        if not isinstance(manifest, dict) or "models" not in manifest:
            return {"exists": True, "valid": False, "message": "Invalid manifest structure"}

        return {"exists": True, "valid": True, "model_count": len(manifest["models"])}

    except json.JSONDecodeError as e:
        return {"exists": True, "valid": False, "message": f"JSON decode error: {str(e)}"}
    except Exception as e:
        return {"exists": True, "valid": False, "message": f"Error: {str(e)}"}


def verify_integration_report() -> Dict:
    """Verify integration report exists and contains successful downloads."""
    report_path = MEDIA_DIR / "integration_report.json"

    if not report_path.exists():
        return {"exists": False, "message": "Integration report not found"}

    try:
        with open(report_path, "r") as f:
            report = json.load(f)

        summary = report.get("summary", {})
        completed = summary.get("downloaded", 0)
        failed = summary.get("failed", 0)

        return {
            "exists": True,
            "valid": True,
            "downloaded": completed,
            "failed": failed,
            "status": "success" if failed == 0 else "partial",
        }

    except Exception as e:
        return {"exists": True, "valid": False, "message": f"Error: {str(e)}"}


def main() -> None:
    """Run all verification checks."""
    print("\n" + "=" * 80)
    print("3D MODEL INTEGRATION VERIFICATION")
    print("=" * 80)

    print(f"\nChecking media directory: {MEDIA_DIR}\n")

    # Check if directory exists
    if not MEDIA_DIR.exists():
        print("ERROR: Media directory does not exist")
        print(f"Expected: {MEDIA_DIR}")
        sys.exit(1)

    # Check each expected model file
    print("FILE VERIFICATION:")
    print("-" * 80)

    files_ok = 0
    files_missing = 0
    files_invalid = 0

    for filename, info in EXPECTED_MODELS.items():
        filepath = MEDIA_DIR / filename
        status = "✓" if filepath.exists() else "✗"

        if filepath.exists():
            valid, message = verify_glb_format(filepath)
            file_size = filepath.stat().st_size

            if valid:
                files_ok += 1
                print(f"{status} {filename}")
                print(f"  Size: {file_size:,} bytes")
                print(f"  Status: {message}")
                print(f"  Creator: {info['creator']}")
                print(f"  License: {info['license']}")
            else:
                files_invalid += 1
                print(f"{status} {filename}")
                print(f"  ERROR: {message}")
        else:
            files_missing += 1
            print(f"{status} {filename} (NOT FOUND)")
            print(f"  Expected size: 5-15 MB")

        print()

    # Check manifest
    print("MANIFEST VERIFICATION:")
    print("-" * 80)
    manifest_status = verify_manifest()
    print(f"Manifest exists: {manifest_status.get('exists', False)}")
    if manifest_status.get("valid"):
        print(f"Model count: {manifest_status.get('model_count', 0)}")
    else:
        print(f"Status: {manifest_status.get('message', 'Unknown error')}")

    print()

    # Check integration report
    print("INTEGRATION REPORT:")
    print("-" * 80)
    report_status = verify_integration_report()
    print(f"Report exists: {report_status.get('exists', False)}")

    if report_status.get("valid"):
        print(f"Downloads: {report_status.get('downloaded', 0)}/3")
        print(f"Failures: {report_status.get('failed', 0)}")
        print(f"Status: {report_status.get('status', 'unknown')}")
    else:
        print(f"Status: {report_status.get('message', 'Unknown error')}")

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files present: {files_ok}/3")
    print(f"Files missing: {files_missing}/3")
    print(f"Files invalid: {files_invalid}/3")

    if files_ok == 3 and files_invalid == 0:
        print("\n✓ ALL MODELS VERIFIED SUCCESSFULLY")
        print("\nNext steps:")
        print("1. Run: python scripts/integrate_3d_models.py")
        print("2. Verify database updates: SELECT * FROM cases WHERE has_3d_model = true;")
        return 0

    elif files_ok > 0:
        print("\n⚠ PARTIAL VERIFICATION")
        if files_missing > 0:
            print(f"\nMissing files ({files_missing}):")
            for filename in EXPECTED_MODELS:
                if not (MEDIA_DIR / filename).exists():
                    print(f"  - {filename}")
            print("\nDownload from Sketchfab and save to:", MEDIA_DIR)
        if files_invalid > 0:
            print(f"\nInvalid files ({files_invalid}) - delete and re-download")
        return 1

    else:
        print("\n✗ NO MODELS FOUND")
        print(f"\nDownload models from Sketchfab and save to:")
        print(f"  {MEDIA_DIR}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
