"""
Curated Promotion Service - Export/Import for dev → production promotion.

Handles exporting approved curated playbooks, pricing, photo packs, and 3D assets
from dev environment and importing them into production (andromeda-ts).

Design:
- Export creates a complete promotion manifest (JSON)
- Import validates and applies the manifest to target environment
- Tracks all promotions in curated_promotions table
- Supports dry-run mode for safety
- Verifies target environment before applying changes
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from structlog import get_logger

log = get_logger(__name__)


class CuratedPromotionService:
    """Service for managing curated set promotions between environments."""
    
    def __init__(self, source_environment: str = "dev", target_environment: str = "production"):
        self.source_environment = source_environment
        self.target_environment = target_environment
    
    def export_curated_set(
        self, 
        include_playbooks: bool = True,
        include_pricing: bool = True,
        include_photo_packs: bool = True,
        include_3d_assets: bool = True,
        promoted_by: str = "system"
    ) -> Dict:
        """
        Export approved curated playbooks, pricing, photo packs, and 3D assets.
        
        Returns a promotion manifest with all approved data ready for import.
        
        Args:
            include_playbooks: Include curated build definitions
            include_pricing: Include approved pricing (sells + upsell deltas)
            include_photo_packs: Include photo pack references
            include_3d_assets: Include approved .glb/3D asset references
            promoted_by: Admin user email performing the promotion
            
        Returns:
            Promotion manifest dict with all data and metadata
        """
        log.info(
            "curated_promotion.export_start",
            source=self.source_environment,
            target=self.target_environment,
            promoted_by=promoted_by
        )
        
        manifest = {
            "version": "1.0",
            "promoted_at": datetime.utcnow().isoformat(),
            "promoted_by": promoted_by,
            "source_environment": self.source_environment,
            "target_environment": self.target_environment,
            "data": {}
        }
        
        # Export curated playbooks (from curated_build_definitions.json + ship_name_map.json)
        if include_playbooks:
            playbooks_data = self._export_curated_playbooks()
            manifest["data"]["playbooks"] = playbooks_data
            manifest["playbooks_count"] = len(playbooks_data.get("builds", []))
        else:
            manifest["playbooks_count"] = 0
        
        # Export approved pricing (from tmp/ship-name-map.json bot_approval_queue_id refs)
        if include_pricing:
            pricing_data = self._export_approved_pricing()
            manifest["data"]["pricing"] = pricing_data
            manifest["pricing_count"] = len(pricing_data.get("items", []))
        else:
            manifest["pricing_count"] = 0
        
        # Export photo pack references (placeholder - depends on where photo packs are stored)
        if include_photo_packs:
            photo_packs_data = self._export_photo_packs()
            manifest["data"]["photo_packs"] = photo_packs_data
            manifest["photo_packs_count"] = len(photo_packs_data.get("packs", []))
        else:
            manifest["photo_packs_count"] = 0
        
        # Export 3D asset references (placeholder - depends on MeshyBot integration)
        if include_3d_assets:
            assets_3d_data = self._export_3d_assets()
            manifest["data"]["assets_3d"] = assets_3d_data
            manifest["assets_3d_count"] = len(assets_3d_data.get("assets", []))
        else:
            manifest["assets_3d_count"] = 0
        
        # Generate manifest hash for verification
        manifest["manifest_hash"] = self._compute_manifest_hash(manifest)
        
        log.info(
            "curated_promotion.export_complete",
            playbooks=manifest["playbooks_count"],
            pricing=manifest["pricing_count"],
            photo_packs=manifest["photo_packs_count"],
            assets_3d=manifest["assets_3d_count"],
            hash=manifest["manifest_hash"]
        )
        
        return manifest
    
    def import_curated_set(
        self,
        manifest: Dict,
        dry_run: bool = True,
        verify_environment: bool = True
    ) -> Tuple[bool, Dict]:
        """
        Import a promotion manifest into the target environment.
        
        Args:
            manifest: Promotion manifest from export_curated_set()
            dry_run: If True, validate but don't apply changes
            verify_environment: If True, verify target environment matches
            
        Returns:
            (success: bool, result: dict with details)
        """
        log.info(
            "curated_promotion.import_start",
            target=self.target_environment,
            dry_run=dry_run,
            manifest_version=manifest.get("version"),
            hash=manifest.get("manifest_hash")
        )
        
        result = {
            "dry_run": dry_run,
            "target_environment": self.target_environment,
            "checks": {},
            "applied": {},
            "errors": []
        }
        
        # Verify manifest integrity
        manifest_hash = manifest.get("manifest_hash")
        if manifest_hash:
            # Recompute hash (excluding the hash field itself)
            manifest_copy = dict(manifest)
            manifest_copy.pop("manifest_hash", None)
            computed_hash = self._compute_manifest_hash(manifest_copy)
            if computed_hash != manifest_hash:
                result["errors"].append(f"Manifest hash mismatch: expected {manifest_hash}, got {computed_hash}")
                return False, result
            result["checks"]["manifest_integrity"] = "PASS"
        
        # Verify target environment
        if verify_environment:
            env_check = self._verify_target_environment()
            result["checks"]["environment"] = env_check
            if not env_check.get("is_production"):
                result["errors"].append(f"Target environment check failed: {env_check.get('reason')}")
                if not dry_run:
                    return False, result
        
        # Import playbooks
        if "playbooks" in manifest.get("data", {}):
            playbooks_result = self._import_curated_playbooks(
                manifest["data"]["playbooks"],
                dry_run=dry_run
            )
            result["applied"]["playbooks"] = playbooks_result
            if not playbooks_result.get("success"):
                result["errors"].extend(playbooks_result.get("errors", []))
        
        # Import pricing
        if "pricing" in manifest.get("data", {}):
            pricing_result = self._import_approved_pricing(
                manifest["data"]["pricing"],
                dry_run=dry_run
            )
            result["applied"]["pricing"] = pricing_result
            if not pricing_result.get("success"):
                result["errors"].extend(pricing_result.get("errors", []))
        
        # Import photo packs
        if "photo_packs" in manifest.get("data", {}):
            photo_packs_result = self._import_photo_packs(
                manifest["data"]["photo_packs"],
                dry_run=dry_run
            )
            result["applied"]["photo_packs"] = photo_packs_result
            if not photo_packs_result.get("success"):
                result["errors"].extend(photo_packs_result.get("errors", []))
        
        # Import 3D assets
        if "assets_3d" in manifest.get("data", {}):
            assets_3d_result = self._import_3d_assets(
                manifest["data"]["assets_3d"],
                dry_run=dry_run
            )
            result["applied"]["assets_3d"] = assets_3d_result
            if not assets_3d_result.get("success"):
                result["errors"].extend(assets_3d_result.get("errors", []))
        
        success = len(result["errors"]) == 0
        
        log.info(
            "curated_promotion.import_complete",
            success=success,
            dry_run=dry_run,
            errors_count=len(result["errors"])
        )
        
        return success, result
    
    # Private helper methods
    
    def _export_curated_playbooks(self) -> Dict:
        """Export curated playbooks from curated_build_definitions.json and ship_name_map.json."""
        data = {"builds": [], "ship_names": {}}
        
        # Load curated build definitions
        definitions_path = Path(__file__).resolve().parents[2] / 'data/curated_build_definitions.json'
        if definitions_path.exists():
            definitions = json.loads(definitions_path.read_text(encoding='utf-8'))
            data["builds"] = definitions.get("builds", [])
        
        # Load ship name map (BuildBot stamped, ids 122-145)
        ship_map_path = Path(__file__).resolve().parents[2] / 'tmp/ship-name-map.json'
        if ship_map_path.exists():
            ship_map = json.loads(ship_map_path.read_text(encoding='utf-8'))
            data["ship_names"] = ship_map
        
        # Load legacy ship names config
        ship_config_path = Path(__file__).resolve().parents[2] / 'data/ship_names.json'
        if ship_config_path.exists():
            ship_config = json.loads(ship_config_path.read_text(encoding='utf-8'))
            data["ship_config"] = ship_config
        
        return data
    
    def _export_approved_pricing(self) -> Dict:
        """Export approved pricing from bot approval queue (ids 66-89 for pricing, 122-145 for playbooks)."""
        data = {"items": [], "note": "Pricing approved via bot approval queue ids 66-89"}
        
        # TODO: If pricing is stored in database, query it here
        # For now, document that pricing should be referenced via bot_approval_queue_id
        
        # Placeholder: pricing is referenced by bot_approval_queue_id in ship_name_map
        ship_map_path = Path(__file__).resolve().parents[2] / 'tmp/ship-name-map.json'
        if ship_map_path.exists():
            ship_map = json.loads(ship_map_path.read_text(encoding='utf-8'))
            builds = ship_map.get("builds", [])
            for build in builds:
                data["items"].append({
                    "build_id": build.get("id"),
                    "bot_approval_queue_id": build.get("bot_approval_queue_id"),
                    "segment": build.get("segment"),
                    "tier": build.get("tier"),
                    "note": "Pricing approval queue id: 66-89 (to be cross-referenced)"
                })
        
        return data
    
    def _export_photo_packs(self) -> Dict:
        """Export photo pack references."""
        data = {"packs": [], "note": "Photo packs pending MeshyBot approval"}
        
        # TODO: When photo packs are stored/tracked, export references here
        # Placeholder for future implementation
        
        return data
    
    def _export_3d_assets(self) -> Dict:
        """Export 3D asset references (.glb files from MeshyBot)."""
        data = {"assets": [], "note": "3D assets pending MeshyBot .glb generation"}
        
        # TODO: When .glb assets are generated and stored, export references here
        # Placeholder for future implementation
        
        return data
    
    def _import_curated_playbooks(self, playbooks_data: Dict, dry_run: bool) -> Dict:
        """Import curated playbooks into target environment."""
        result = {"success": True, "imported": 0, "skipped": 0, "errors": []}
        
        builds = playbooks_data.get("builds", [])
        ship_names = playbooks_data.get("ship_names", {})
        ship_config = playbooks_data.get("ship_config", {})
        
        if dry_run:
            result["imported"] = len(builds)
            result["note"] = "DRY RUN: Would import curated_build_definitions.json and ship naming data"
            return result
        
        # Write curated build definitions
        try:
            definitions_path = Path(__file__).resolve().parents[2] / 'data/curated_build_definitions.json'
            definitions_path.parent.mkdir(parents=True, exist_ok=True)
            definitions_path.write_text(
                json.dumps({"builds": builds}, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            result["imported"] += len(builds)
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Failed to write curated_build_definitions.json: {str(e)}")
        
        # Write ship name map
        if ship_names:
            try:
                ship_map_path = Path(__file__).resolve().parents[2] / 'tmp/ship-name-map.json'
                ship_map_path.parent.mkdir(parents=True, exist_ok=True)
                ship_map_path.write_text(
                    json.dumps(ship_names, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
            except Exception as e:
                result["success"] = False
                result["errors"].append(f"Failed to write ship-name-map.json: {str(e)}")
        
        # Write ship config
        if ship_config:
            try:
                ship_config_path = Path(__file__).resolve().parents[2] / 'data/ship_names.json'
                ship_config_path.parent.mkdir(parents=True, exist_ok=True)
                ship_config_path.write_text(
                    json.dumps(ship_config, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
            except Exception as e:
                result["success"] = False
                result["errors"].append(f"Failed to write ship_names.json: {str(e)}")
        
        return result
    
    def _import_approved_pricing(self, pricing_data: Dict, dry_run: bool) -> Dict:
        """Import approved pricing into target environment."""
        result = {"success": True, "imported": 0, "skipped": 0, "errors": []}
        
        items = pricing_data.get("items", [])
        
        if dry_run:
            result["imported"] = len(items)
            result["note"] = "DRY RUN: Would import pricing references (bot_approval_queue_id 66-89)"
            return result
        
        # TODO: When pricing is stored in database, insert/update here
        # For now, pricing is referenced via bot_approval_queue_id in ship_name_map
        result["note"] = "Pricing referenced via bot_approval_queue_id in ship_name_map (no separate import)"
        result["skipped"] = len(items)
        
        return result
    
    def _import_photo_packs(self, photo_packs_data: Dict, dry_run: bool) -> Dict:
        """Import photo pack references into target environment."""
        result = {"success": True, "imported": 0, "skipped": 0, "errors": []}
        
        packs = photo_packs_data.get("packs", [])
        
        if dry_run:
            result["note"] = "DRY RUN: Photo packs pending implementation"
            return result
        
        # TODO: Implement when photo packs are tracked
        result["note"] = "Photo packs not yet implemented"
        result["skipped"] = len(packs)
        
        return result
    
    def _import_3d_assets(self, assets_3d_data: Dict, dry_run: bool) -> Dict:
        """Import 3D asset references into target environment."""
        result = {"success": True, "imported": 0, "skipped": 0, "errors": []}
        
        assets = assets_3d_data.get("assets", [])
        
        if dry_run:
            result["note"] = "DRY RUN: 3D assets pending MeshyBot .glb generation"
            return result
        
        # TODO: Implement when .glb assets are generated and tracked
        result["note"] = "3D assets not yet implemented"
        result["skipped"] = len(assets)
        
        return result
    
    def _verify_target_environment(self) -> Dict:
        """Verify the target environment is production (safety check)."""
        from app.config import get_settings
        
        settings = get_settings()
        
        result = {
            "is_production": False,
            "app_env": getattr(settings, "app_env", "unknown"),
            "runtime_env": getattr(settings, "flipflop_runtime_env", "unknown"),
            "database_url": settings.database_url if hasattr(settings, "database_url") else "unknown"
        }
        
        # Check for production indicators
        is_prod_app = result["app_env"] == "production"
        is_prod_runtime = result["runtime_env"] == "live"
        is_prod_db = "andromeda" in result["database_url"] or result["database_url"].startswith("postgresql")
        
        result["is_production"] = is_prod_app or is_prod_runtime
        
        if not result["is_production"]:
            result["reason"] = f"Not production environment: app_env={result['app_env']}, runtime_env={result['runtime_env']}"
        
        return result
    
    def _compute_manifest_hash(self, manifest: Dict) -> str:
        """Compute SHA256 hash of manifest for verification."""
        # Normalize manifest for consistent hashing
        manifest_json = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(manifest_json.encode('utf-8')).hexdigest()[:16]


# Convenience functions for common operations

def export_curated_set_to_file(
    output_path: Path,
    promoted_by: str = "system",
    source_environment: str = "dev"
) -> Path:
    """
    Export curated set to a JSON file.
    
    Args:
        output_path: Path to write manifest JSON
        promoted_by: Admin user email
        source_environment: Source environment name
        
    Returns:
        Path to written manifest file
    """
    service = CuratedPromotionService(source_environment=source_environment)
    manifest = service.export_curated_set(promoted_by=promoted_by)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    
    log.info("curated_promotion.export_to_file", path=str(output_path), hash=manifest.get("manifest_hash"))
    
    return output_path


def import_curated_set_from_file(
    manifest_path: Path,
    target_environment: str = "production",
    dry_run: bool = True
) -> Tuple[bool, Dict]:
    """
    Import curated set from a JSON manifest file.
    
    Args:
        manifest_path: Path to manifest JSON
        target_environment: Target environment name
        dry_run: If True, validate but don't apply changes
        
    Returns:
        (success: bool, result: dict)
    """
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    
    service = CuratedPromotionService(target_environment=target_environment)
    return service.import_curated_set(manifest, dry_run=dry_run)
