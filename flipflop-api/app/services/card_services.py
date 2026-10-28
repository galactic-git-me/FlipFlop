"""
Shared card generation services for both pre-builts and curated playbooks.

Three reusable card generators:
1. Performance Card: performance.json → HTML → images
2. Spec Card: build.json → HTML → images  
3. Registration Card: build metadata → card image

Used in two phases:
- Pre-generation: Standard recommended BOM for catalogue/site/indirect channels
- Post-purchase: Regenerate with as-bought BOM (including upsells) for personalised portal

config_hash ties catalogue looks to as-bought books/portal.

PUBLIC DISPLAY NAMING:
- Budget tier: Just ship name (e.g., "Reliant")
- Mid-range tier: Ship name + " Pro" (e.g., "Reliant Pro")
- High-end tier: Ship name + " Ultra" (e.g., "Reliant Ultra")
- DO NOT use "Base" in customer-facing cards
"""
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
import structlog

log = structlog.get_logger(__name__)


def compute_config_hash(components: dict) -> str:
    """
    Compute a stable hash of the component configuration.
    
    Used to tie catalogue SKU "looks" to the as-bought configuration.
    When customer chooses upsells (e.g., 64GB RAM instead of 32GB),
    the config_hash changes, triggering card regeneration.
    
    Args:
        components: Dict of component slot → component spec
    
    Returns:
        SHA256 hash (first 16 chars) of normalized component JSON
    """
    # Sort keys for stable hashing
    normalized = json.dumps(components, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class PerformanceCardGenerator:
    """
    Generate performance card from performance.json data.
    
    Reuses existing Personalised Website/performance-data.json schema.
    Used by both pre-builts and curated playbooks.
    """
    
    @staticmethod
    def generate_performance_json(
        build_id: str,
        pc_name: str,
        ship_name: Optional[str],
        benchmarks: list[dict],
        games: list[dict],
        specs: list[dict],
        config_hash: Optional[str] = None
    ) -> dict:
        """
        Generate performance-data.json structure.
        
        Args:
            build_id: Build ID (e.g., "FF-GVG-02" or manual build ID)
            pc_name: Display name (e.g., "Atlas Pulse")
            ship_name: Star Trek ship name (e.g., "Reliant Pro")
            benchmarks: List of benchmark results
            games: List of gaming FPS estimates
            specs: List of key specs
            config_hash: Hash of component configuration
        
        Returns:
            Dict matching Personalised Website/performance-data.json schema
        """
        return {
            "meta": {
                "build_id": build_id,
                "pc_name": pc_name,
                "ship_name": ship_name,
                "config_hash": config_hash,
                "generated_at": datetime.utcnow().isoformat()
            },
            "hero": {
                "tagline": f"Benchmark-proven performance",
                "subtitle": ship_name if ship_name else pc_name
            },
            "benchmarks": benchmarks,
            "games": games,
            "specs": specs,
            "everyday": [
                {"task": "Web Browsing", "rating": "Instant", "tier": "excellent"},
                {"task": "Office Work", "rating": "Seamless", "tier": "excellent"},
                {"task": "Video Streaming", "rating": "Flawless 4K", "tier": "excellent"},
            ]
        }
    
    @staticmethod
    async def render_performance_card_html(
        performance_data: dict,
        template_path: Path
    ) -> str:
        """
        Render performance card HTML from performance.json and template.
        
        Reuses Personalised Website/index.html template.
        
        Args:
            performance_data: Dict from generate_performance_json()
            template_path: Path to Personalised Website/index.html
        
        Returns:
            Rendered HTML string
        """
        # TODO: Implement HTML rendering with template
        # - Load template from template_path
        # - Inject performance_data as JSON
        # - Return full HTML with inline styles/scripts
        log.info("performance_card.render_html", build_id=performance_data.get("meta", {}).get("build_id"))
        return "<html><!-- Performance Card HTML --></html>"
    
    @staticmethod
    async def convert_html_to_images(
        html_content: str,
        output_dir: Path,
        viewports: list[tuple[str, int, int]] = None
    ) -> list[Path]:
        """
        Convert performance card HTML to images using Playwright.
        
        Args:
            html_content: Rendered HTML
            output_dir: Directory to save images
            viewports: List of (name, width, height) for different sizes
        
        Returns:
            List of generated image paths
        """
        if viewports is None:
            viewports = [
                ("desktop", 1200, 630),
                ("mobile", 800, 600),
            ]
        
        # TODO: Implement Playwright screenshot
        # - Launch browser
        # - Load HTML
        # - Take screenshots at each viewport size
        # - Save to output_dir
        log.info("performance_card.convert_to_images", output_dir=str(output_dir))
        return []


class SpecCardGenerator:
    """
    Generate spec card from build.json data.
    
    Lists all components with icons and highlights key specs.
    Used by both pre-builts and curated playbooks.
    """
    
    @staticmethod
    def generate_spec_json(
        build_id: str,
        pc_name: str,
        ship_name: Optional[str],
        components: dict,
        tier: Optional[str] = None,
        config_hash: Optional[str] = None
    ) -> dict:
        """
        Generate spec card data structure.
        
        Args:
            build_id: Build ID
            pc_name: Display name
            ship_name: Star Trek ship name
            components: Dict of slot → component name
            tier: Budget/Mid-range/High-end
            config_hash: Hash of component configuration
        
        Returns:
            Dict for spec card rendering
        """
        return {
            "meta": {
                "build_id": build_id,
                "pc_name": pc_name,
                "ship_name": ship_name,
                "tier": tier,
                "config_hash": config_hash,
                "generated_at": datetime.utcnow().isoformat()
            },
            "components": [
                {"slot": slot, "name": name}
                for slot, name in components.items()
            ]
        }
    
    @staticmethod
    async def render_spec_card_html(
        spec_data: dict,
        template_path: Path
    ) -> str:
        """
        Render spec card HTML from spec.json and template.
        
        Args:
            spec_data: Dict from generate_spec_json()
            template_path: Path to spec card HTML template
        
        Returns:
            Rendered HTML string
        """
        # TODO: Implement HTML rendering
        log.info("spec_card.render_html", build_id=spec_data.get("meta", {}).get("build_id"))
        return "<html><!-- Spec Card HTML --></html>"
    
    @staticmethod
    async def convert_html_to_images(
        html_content: str,
        output_dir: Path
    ) -> list[Path]:
        """
        Convert spec card HTML to images.
        
        Args:
            html_content: Rendered HTML
            output_dir: Directory to save images
        
        Returns:
            List of generated image paths
        """
        # TODO: Implement Playwright screenshot
        log.info("spec_card.convert_to_images", output_dir=str(output_dir))
        return []


class RegistrationCardGenerator:
    """
    Generate registration card/plate with build metadata.
    
    Shows ship name, tier, key specs in a visual "registration plate" format.
    Used by both pre-builts and curated playbooks.
    """
    
    @staticmethod
    def generate_registration_json(
        build_id: str,
        pc_name: str,
        ship_name: Optional[str],
        tier: Optional[str],
        key_specs: list[tuple[str, str]],
        config_hash: Optional[str] = None
    ) -> dict:
        """
        Generate registration card data.
        
        Args:
            build_id: Build ID
            pc_name: Display name
            ship_name: Star Trek ship name
            tier: Budget/Mid-range/High-end
            key_specs: List of (label, value) tuples for key specs
            config_hash: Hash of component configuration
        
        Returns:
            Dict for registration card rendering
        """
        return {
            "meta": {
                "build_id": build_id,
                "pc_name": pc_name,
                "ship_name": ship_name,
                "tier": tier,
                "config_hash": config_hash,
                "generated_at": datetime.utcnow().isoformat()
            },
            "registration": {
                "ship_name": ship_name if ship_name else pc_name,
                "registry": build_id,
                "tier": tier,
                "key_specs": key_specs
            }
        }
    
    @staticmethod
    async def render_registration_card_image(
        registration_data: dict,
        output_path: Path
    ) -> Path:
        """
        Render registration card directly to image.
        
        Args:
            registration_data: Dict from generate_registration_json()
            output_path: Path to save image
        
        Returns:
            Path to generated image
        """
        # TODO: Implement registration card rendering
        # - Could use PIL/Pillow for direct image generation
        # - Or HTML template → Playwright screenshot
        log.info("registration_card.render_image", 
                build_id=registration_data.get("meta", {}).get("build_id"),
                output_path=str(output_path))
        return output_path


class CardOrchestrator:
    """
    Orchestrates card generation for builds.
    
    Handles both phases:
    1. Pre-generation: Standard recommended BOM for catalogue
    2. Post-purchase: Regenerate with as-bought BOM (including upsells)
    """
    
    def __init__(self, output_base_dir: Path):
        self.output_base_dir = output_base_dir
        self.perf_gen = PerformanceCardGenerator()
        self.spec_gen = SpecCardGenerator()
        self.reg_gen = RegistrationCardGenerator()
    
    async def generate_all_cards(
        self,
        build_id: str,
        pc_name: str,
        ship_name: Optional[str],
        components: dict,
        tier: Optional[str],
        performance_data: Optional[dict] = None,
        phase: str = "pre_generation"
    ) -> dict:
        """
        Generate all three cards for a build.
        
        Args:
            build_id: Build ID
            pc_name: Display name
            ship_name: Star Trek ship name
            components: Component configuration
            tier: Budget/Mid-range/High-end
            performance_data: Optional benchmark data
            phase: "pre_generation" or "post_purchase"
        
        Returns:
            Dict with paths to all generated assets
        """
        config_hash = compute_config_hash(components)
        output_dir = self.output_base_dir / build_id / phase / config_hash
        output_dir.mkdir(parents=True, exist_ok=True)
        
        log.info("card_orchestrator.generate_all",
                build_id=build_id,
                ship_name=ship_name,
                config_hash=config_hash,
                phase=phase)
        
        results = {
            "build_id": build_id,
            "config_hash": config_hash,
            "phase": phase,
            "performance_card": None,
            "spec_card": None,
            "registration_card": None
        }
        
        # Generate performance card if data provided
        if performance_data:
            perf_json = self.perf_gen.generate_performance_json(
                build_id, pc_name, ship_name,
                performance_data.get("benchmarks", []),
                performance_data.get("games", []),
                performance_data.get("specs", []),
                config_hash
            )
            # Save JSON and generate images
            perf_json_path = output_dir / "performance-data.json"
            perf_json_path.write_text(json.dumps(perf_json, indent=2))
            results["performance_card"] = {
                "json": str(perf_json_path),
                "images": []  # TODO: Add image paths after rendering
            }
        
        # Generate spec card
        spec_json = self.spec_gen.generate_spec_json(
            build_id, pc_name, ship_name, components, tier, config_hash
        )
        spec_json_path = output_dir / "spec-data.json"
        spec_json_path.write_text(json.dumps(spec_json, indent=2))
        results["spec_card"] = {
            "json": str(spec_json_path),
            "images": []
        }
        
        # Generate registration card
        key_specs = [
            ("CPU", components.get("cpu", "N/A")),
            ("GPU", components.get("gpu", "N/A")),
            ("RAM", components.get("ram", "N/A")),
            ("Storage", components.get("storage", "N/A")),
        ]
        reg_json = self.reg_gen.generate_registration_json(
            build_id, pc_name, ship_name, tier, key_specs, config_hash
        )
        reg_json_path = output_dir / "registration-data.json"
        reg_json_path.write_text(json.dumps(reg_json, indent=2))
        results["registration_card"] = {
            "json": str(reg_json_path),
            "image": None
        }
        
        return results
