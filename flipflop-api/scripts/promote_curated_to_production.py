#!/usr/bin/env python3
"""
Promote curated FlipFlop set from dev to production (andromeda-ts).

Usage:
    # Export from dev
    python scripts/promote_curated_to_production.py export --output ./curated-promotion-manifest.json

    # Dry-run import to production (ALWAYS DO THIS FIRST)
    python scripts/promote_curated_to_production.py import --manifest ./curated-promotion-manifest.json --dry-run

    # Apply to production (after dry-run verification)
    python scripts/promote_curated_to_production.py import --manifest ./curated-promotion-manifest.json

    # View promotion history
    python scripts/promote_curated_to_production.py history

Safety features:
- Always defaults to dry-run mode
- Verifies production environment before applying
- Requires explicit --no-dry-run flag to apply changes
- Logs all operations to curated_promotions table
- Computes manifest hash for verification

Design:
Michael's current Approve clicks are dev sign-off only. After promote,
only new/changed SKUs go through /approvals again. BuildBot/PricingBot/MeshyBot
daily updates write to prod admin directly.
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add app to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.curated_promotion_service import (
    CuratedPromotionService,
    export_curated_set_to_file,
    import_curated_set_from_file
)
from app.config import get_settings
from structlog import get_logger

log = get_logger(__name__)


def export_command(args):
    """Export curated set from current (dev) environment."""
    print("=" * 80)
    print("CURATED SET EXPORT - Dev → Production")
    print("=" * 80)
    print()
    
    output_path = Path(args.output)
    promoted_by = args.promoted_by or "cli-script"
    
    print(f"Exporting curated set to: {output_path}")
    print(f"Promoted by: {promoted_by}")
    print()
    
    try:
        manifest_path = export_curated_set_to_file(
            output_path=output_path,
            promoted_by=promoted_by,
            source_environment="dev"
        )
        
        # Load and display summary
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        
        print("✅ Export successful!")
        print()
        print("Manifest Summary:")
        print(f"  - Playbooks: {manifest.get('playbooks_count', 0)}")
        print(f"  - Pricing items: {manifest.get('pricing_count', 0)}")
        print(f"  - Photo packs: {manifest.get('photo_packs_count', 0)}")
        print(f"  - 3D assets: {manifest.get('assets_3d_count', 0)}")
        print(f"  - Hash: {manifest.get('manifest_hash', 'N/A')}")
        print()
        print(f"Manifest written to: {manifest_path}")
        print()
        print("Next steps:")
        print(f"  1. Review the manifest file: {manifest_path}")
        print(f"  2. Dry-run import: python {Path(__file__).name} import --manifest {manifest_path} --dry-run")
        print(f"  3. Apply to prod: python {Path(__file__).name} import --manifest {manifest_path} --no-dry-run")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        sys.exit(1)


def import_command(args):
    """Import curated set to production."""
    print("=" * 80)
    print("CURATED SET IMPORT - Dev → Production")
    print("=" * 80)
    print()
    
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"❌ Manifest file not found: {manifest_path}")
        sys.exit(1)
    
    dry_run = not args.no_dry_run
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be applied")
    else:
        print("⚠️  LIVE MODE - Changes will be applied to production!")
        print()
        response = input("Are you sure you want to proceed? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    print()
    print(f"Manifest: {manifest_path}")
    print(f"Target: production (andromeda-ts)")
    print()
    
    # Verify environment
    settings = get_settings()
    app_env = getattr(settings, "app_env", "unknown")
    runtime_env = getattr(settings, "flipflop_runtime_env", "unknown")
    
    print("Environment check:")
    print(f"  - APP_ENV: {app_env}")
    print(f"  - FLIPFLOP_RUNTIME_ENV: {runtime_env}")
    
    if not dry_run and app_env != "production" and runtime_env != "live":
        print()
        print("⚠️  WARNING: Not running in production environment!")
        print("This script should be run on andromeda-ts with production settings.")
        response = input("Continue anyway? Type 'yes' to proceed: ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    print()
    
    try:
        success, result = import_curated_set_from_file(
            manifest_path=manifest_path,
            target_environment="production",
            dry_run=dry_run
        )
        
        print()
        print("=" * 80)
        print("IMPORT RESULT")
        print("=" * 80)
        print()
        
        # Display checks
        if "checks" in result:
            print("Pre-import checks:")
            for check_name, check_result in result["checks"].items():
                if isinstance(check_result, str):
                    status = "✅" if check_result == "PASS" else "⚠️"
                    print(f"  {status} {check_name}: {check_result}")
                elif isinstance(check_result, dict):
                    is_pass = check_result.get("is_production", False)
                    status = "✅" if is_pass else "⚠️"
                    print(f"  {status} {check_name}:")
                    for key, value in check_result.items():
                        print(f"      {key}: {value}")
            print()
        
        # Display applied changes
        if "applied" in result:
            print("Applied changes:")
            for category, category_result in result["applied"].items():
                if isinstance(category_result, dict):
                    imported = category_result.get("imported", 0)
                    skipped = category_result.get("skipped", 0)
                    errors = category_result.get("errors", [])
                    note = category_result.get("note", "")
                    
                    status = "✅" if category_result.get("success") else "❌"
                    print(f"  {status} {category}: {imported} imported, {skipped} skipped")
                    if note:
                        print(f"      Note: {note}")
                    if errors:
                        for error in errors:
                            print(f"      ❌ {error}")
            print()
        
        # Display errors
        if result.get("errors"):
            print("Errors:")
            for error in result["errors"]:
                print(f"  ❌ {error}")
            print()
        
        # Summary
        if success:
            if dry_run:
                print("✅ Dry-run validation passed!")
                print()
                print("Next step:")
                print(f"  Apply to production: python {Path(__file__).name} import --manifest {manifest_path} --no-dry-run")
            else:
                print("✅ Import completed successfully!")
                print()
                print("Curated builds are now available on production storefront.")
                print("BuildBot/PricingBot/MeshyBot daily updates will write to prod admin.")
        else:
            print("❌ Import failed!")
            if dry_run:
                print("Fix the errors above before applying to production.")
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def history_command(args):
    """View promotion history (requires database access)."""
    print("=" * 80)
    print("CURATED SET PROMOTION HISTORY")
    print("=" * 80)
    print()
    
    print("Note: Promotion history is stored in the curated_promotions table.")
    print("Use the admin API endpoint /api/admin/curated-promotion/history to view it.")
    print()
    print("Example:")
    print("  curl -H 'Authorization: Bearer <admin-token>' \\")
    print("       https://www.theflipflop.shop/api/admin/curated-promotion/history")


def main():
    parser = argparse.ArgumentParser(
        description="Promote curated FlipFlop set from dev to production",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from dev
  python scripts/promote_curated_to_production.py export --output ./manifest.json

  # Dry-run import (ALWAYS DO THIS FIRST)
  python scripts/promote_curated_to_production.py import --manifest ./manifest.json --dry-run

  # Apply to production (after verification)
  python scripts/promote_curated_to_production.py import --manifest ./manifest.json --no-dry-run

Safety:
  - Always run with --dry-run first
  - Verifies production environment before applying
  - Requires explicit confirmation for live imports
  - All operations logged to curated_promotions table
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export curated set from dev")
    export_parser.add_argument(
        "--output",
        default=f"./curated-promotion-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
        help="Output manifest file path"
    )
    export_parser.add_argument(
        "--promoted-by",
        help="Admin user email (defaults to 'cli-script')"
    )
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import curated set to production")
    import_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to promotion manifest JSON file"
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Validate but don't apply changes (default)"
    )
    import_parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Apply changes to production (DANGEROUS - use with caution!)"
    )
    
    # History command
    history_parser = subparsers.add_parser("history", help="View promotion history")
    
    args = parser.parse_args()
    
    if args.command == "export":
        export_command(args)
    elif args.command == "import":
        import_command(args)
    elif args.command == "history":
        history_command(args)


if __name__ == "__main__":
    main()
