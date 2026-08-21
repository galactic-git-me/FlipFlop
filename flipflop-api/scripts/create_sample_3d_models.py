#!/usr/bin/env python3
"""
Create sample/placeholder 3D model files for testing and development.

This creates minimal valid GLB files with proper structure so integration
scripts can extract metadata and test database updates.

For production, replace these with actual downloaded Sketchfab models.
"""

import json
import struct
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

MEDIA_DIR = Path(__file__).parent.parent / "media" / "3d-models" / "cases"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Model specifications for realistic placeholder files
MODELS = {
    "corsair_4000d": {
        "filename": "corsair_4000d.glb",
        "creator": "SzaBa",
        "license": "CC-BY-4.0",
        "vertices": 45230,
        "polygons": 22615,
    },
    "be_quiet_pure_base_600": {
        "filename": "be_quiet_pure_base_600.glb",
        "creator": "JackZeta",
        "license": "CC-BY-4.0",
        "vertices": 38950,
        "polygons": 19475,
    },
    "corsair_5000d": {
        "filename": "corsair_5000d.glb",
        "creator": "lukeboxfx",
        "license": "CC-BY-4.0",
        "vertices": 52840,
        "polygons": 26420,
    },
}


def create_minimal_glb(
    filepath: Path,
    num_vertices: int,
    num_polygons: int,
) -> None:
    """
    Create a minimal valid GLB file with specified vertex and polygon counts.

    GLB structure:
    - Header (12 bytes): magic "glTF", version 2, file length
    - JSON chunk: glTF structure with metadata
    - BIN chunk: vertex data buffer
    """

    # Create gltf JSON structure with accessor information
    gltf_data = {
        "asset": {
            "version": "2.0",
            "generator": "FlipFlop 3D Model Generator",
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "primitives": [
                    {
                        "mode": 4,  # Triangles
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                    }
                ]
            }
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,  # FLOAT
                "count": num_vertices,
                "type": "VEC3",
                "max": [1.0, 1.0, 1.0],
                "min": [-1.0, -1.0, -1.0],
            },
            {
                "bufferView": 1,
                "componentType": 5125,  # UNSIGNED_INT
                "count": num_polygons * 3,  # 3 indices per triangle
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {
                "buffer": 0,
                "byteLength": num_vertices * 12,  # 3 floats * 4 bytes each
                "byteOffset": 0,
            },
            {
                "buffer": 0,
                "byteLength": num_polygons * 3 * 4,  # uint32 per index
                "byteOffset": num_vertices * 12,
            },
        ],
        "buffers": [
            {
                "byteLength": num_vertices * 12 + num_polygons * 3 * 4,
            }
        ],
    }

    # Encode JSON
    json_str = json.dumps(gltf_data)
    json_bytes = json_str.encode("utf-8")
    json_padded_length = ((len(json_bytes) + 3) // 4) * 4  # Align to 4-byte boundary
    json_padding = b" " * (json_padded_length - len(json_bytes))

    # Create binary data buffer (simplified vertex + index data)
    bin_vertex_data = struct.pack(f"<{num_vertices * 3}f", *([0.0] * (num_vertices * 3)))
    bin_index_data = struct.pack(f"<{num_polygons * 3}I", *list(range(num_polygons * 3)))
    bin_data = bin_vertex_data + bin_index_data
    bin_padded_length = ((len(bin_data) + 3) // 4) * 4
    bin_padding = b"\x00" * (bin_padded_length - len(bin_data))

    # Build GLB file
    with open(filepath, "wb") as f:
        # Header
        magic = b"glTF"
        version = struct.pack("<I", 2)

        # Calculate total file length
        json_chunk_header = 8
        bin_chunk_header = 8
        total_length = 12 + json_chunk_header + json_padded_length + bin_chunk_header + bin_padded_length
        length = struct.pack("<I", total_length)

        f.write(magic)
        f.write(version)
        f.write(length)

        # JSON chunk
        f.write(struct.pack("<I", json_padded_length))  # Chunk length
        f.write(struct.pack("<I", 0x4E4F4A))  # "JSON" in little-endian
        f.write(json_bytes)
        f.write(json_padding)

        # BIN chunk
        f.write(struct.pack("<I", bin_padded_length))  # Chunk length
        f.write(struct.pack("<I", 0x004E4942))  # "BIN\x00" in little-endian
        f.write(bin_data)
        f.write(bin_padding)


def main() -> None:
    """Create all sample 3D model files."""
    print("\n" + "="*80)
    print("CREATING SAMPLE 3D MODEL FILES")
    print("="*80)
    print(f"\nMedia directory: {MEDIA_DIR}\n")

    for model_key, model_info in MODELS.items():
        filepath = MEDIA_DIR / model_info["filename"]

        print(f"[{model_key}]")
        print(f"  Filename: {model_info['filename']}")
        print(f"  Creator: {model_info['creator']}")
        print(f"  License: {model_info['license']}")
        print(f"  Vertices: {model_info['vertices']}")
        print(f"  Polygons: {model_info['polygons']}")

        try:
            create_minimal_glb(
                filepath,
                model_info["vertices"],
                model_info["polygons"],
            )

            file_size = filepath.stat().st_size
            size_mb = file_size / (1024 * 1024)

            print(f"  Status: ✓ CREATED")
            print(f"  File size: {file_size:,} bytes ({size_mb:.2f} MB)")
            print(f"  Path: {filepath}\n")

        except Exception as e:
            print(f"  Status: ✗ FAILED")
            print(f"  Error: {str(e)}\n")

    # Create manifest
    manifest = {
        "generated_at": datetime.utcnow().isoformat(),
        "type": "sample_models",
        "note": "These are placeholder GLB files created for testing. Replace with actual Sketchfab downloads for production.",
        "models": [
            {
                "name": model_key,
                "filename": model_info["filename"],
                "creator": model_info["creator"],
                "license": model_info["license"],
                "vertices": model_info["vertices"],
                "polygons": model_info["polygons"],
                "type": "sample_placeholder",
            }
            for model_key, model_info in MODELS.items()
        ],
    }

    manifest_path = MEDIA_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("="*80)
    print("✓ SAMPLE MODELS CREATED SUCCESSFULLY")
    print("="*80)
    print(f"\nManifest: {manifest_path}")
    print("\nNext steps:")
    print("1. Verify files: python scripts/verify_3d_models.py")
    print("2. Integrate into database: python scripts/integrate_3d_models.py")
    print("\nNote: These are placeholder files for testing.")
    print("For production, download actual models from Sketchfab:")
    print("  - Corsair 4000D: https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665")
    print("  - be quiet! Pure Base 600: https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89")
    print("  - Corsair 5000D RGB: https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614")
    print()


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
