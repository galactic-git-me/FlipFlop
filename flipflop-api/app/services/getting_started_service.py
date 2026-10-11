"""LLM-authored content for the reviewed build dispatch package.

The LLM is deliberately restricted to documentation and a typed content
manifest. Package assembly, installer generation, portal publication, and
dispatch gates remain deterministic application responsibilities.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from app.services.model_selection_service import model_selection_service
from app.services.software_catalogue import SOFTWARE_BY_ID, validate_package_ids, estimate_saved_minutes
from app.template_paths import dispatch_template_path


_TEMPLATE_PATH = dispatch_template_path("getting-ready-package-prompt.md")
GETTING_READY_TEMPLATE_VERSION = "1.7"
GETTING_READY_PROMPT_MAX_BYTES = 20_000
REQUIRED_GETTING_READY_PROMPT_INPUTS = frozenset({
    "build_name_json",
    "playbook_segment_json",
    "build_specification_json",
    "benchmark_results_json",
    "customer_software_selections_json",
    "software_install_scopes_json",
    "purchased_ai_services_json",
    "warranty_start_date_json",
    "support_base_url_json",
    "approved_research_bundle_json",
    "approved_component_manuals_json",
    "upgrade_policy_json",
})


class DriverReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    component_name: str
    action: Literal["review_required"]
    reason: str
    source_url: str | None = None
    source_title: str | None = None
    source_accessed_at: str | None = None
    administrator_approval_required: Literal[True] = True


class ManualMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    component_name: str
    manual_title: str | None = None
    manual_url: str | None = None
    match_status: Literal["needs_research", "needs_admin_confirmation"]
    administrator_approval_required: Literal[True] = True


class BuildPlaque(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    subtitle: str = ""
    build_name: str = ""
    segment_label: str | None = None


class CustomerCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_summary: str = ""
    getting_started_intro: str = ""
    ai_setup_summary: str | None = None
    upgrade_path_intro: str = ""


class SoftwareInstallPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_package_ids: list[str] = Field(default_factory=list)
    machine_scope_package_ids: list[str] = Field(default_factory=list)
    customer_profile_package_ids: list[str] = Field(default_factory=list)
    unresolved_package_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UpgradePathItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    component: str | None = None
    timing: str | None = None
    when: str | None = None
    reason: str | None = None
    description: str | None = None


class UpgradePath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["needs_policy_or_evidence"] = "needs_policy_or_evidence"
    items: list[UpgradePathItem] = Field(default_factory=list)


class GettingReadyManifest(BaseModel):
    """Validated LLM result. It is not itself a dispatch-complete package."""

    model_config = ConfigDict(extra="forbid")

    template_version: str
    build_name: str
    status: Literal["ready_for_admin_review"]
    plaque: BuildPlaque
    customer_copy: CustomerCopy
    software_install_plan: SoftwareInstallPlan
    driver_and_firmware_review: list[DriverReviewItem]
    manual_library_matches: list[ManualMatch]
    upgrade_path: UpgradePath
    portal_document_manifest: list[Literal[
        "plaque",
        "build_specification",
        "benchmark_results",
        "getting_started_guide",
        "startup_automation_status",
        "driver_and_firmware_review",
        "component_manuals",
        "upgrade_path",
    ]]
    warnings: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class GettingReadyGenerationError(RuntimeError):
    """Raised when the shared configured model or output validation fails."""


class GettingReadyPromptSizeError(GettingReadyGenerationError):
    """Raised when review inputs exceed the bounded model prompt budget."""


def save_customer_software_selection(job: Any, package_ids: list[str]) -> dict[str, Any]:
    """Accept only allow-listed free app choices and persist them on the job."""
    selected = validate_package_ids(package_ids)
    job.customer_software_selections = selected
    job.checklist = {**(job.checklist or {}), "software_selection_submitted": True}
    return {
        "software_package_ids": selected,
        "estimated_time_saved_minutes": estimate_saved_minutes(selected),
    }


def customer_software_selection_changed(job: Any, package_ids: list[str]) -> bool:
    """Return whether a valid selection is new or differs from the saved choice."""
    selected = validate_package_ids(package_ids)
    checklist = job.checklist or {}
    if checklist.get("software_selection_submitted") is not True:
        return True
    try:
        existing = validate_package_ids(list(job.customer_software_selections or []))
    except ValueError:
        # Treat invalid legacy state as changed so the normal save path repairs it.
        return True
    return set(selected) != set(existing)


def invalidate_ready_to_ship_reviewed_package(
    job: Any,
    build: Any,
    *,
    checklist_reset_keys: tuple[str, ...] = (
        "customer_selections_locked",
        "content_manifest",
        "artifacts_generated",
        "artifacts_reviewed",
        "customer_package",
    ),
) -> bool:
    """Retire reviewed ZIPs when a Ready-to-Ship package input changes."""
    artifacts = list(job.artifact_index or [])
    invalidated = False
    retained = []
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("category") == "customer_package":
            retired = dict(artifact)
            retired["category"] = "superseded_customer_package"
            retired["superseded_at"] = datetime.utcnow().isoformat()
            retained.append(retired)
            invalidated = True
        else:
            retained.append(artifact)
    job.artifact_index = retained
    if invalidated or job.reviewed_at:
        job.reviewed_at = None
        job.private_storage_key = None
    job.manifest = None
    job.generated_at = None
    checklist = dict(job.checklist or {})
    for key in checklist_reset_keys:
        checklist[key] = "not_ready"
    job.checklist = checklist
    if job.status != "cancelled":
        job.status = "awaiting_admin_review"

    evidence = dict(build.evidence_data or {})
    getting_ready = dict(evidence.get("getting_ready") or {})
    if "package" in getting_ready:
        getting_ready.pop("package", None)
        getting_ready["status"] = "awaiting_review"
        evidence["getting_ready"] = getting_ready
        build.evidence_data = evidence
    return invalidated


def _template_sections() -> tuple[str, str]:
    if not _TEMPLATE_PATH.is_file():
        raise GettingReadyGenerationError(
            f"Getting Ready prompt template is missing: {_TEMPLATE_PATH}"
        )
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    system_marker = "## System prompt"
    user_marker = "## User prompt"
    contract_marker = "## Output contract"
    system_heading = template.find(system_marker)
    user_start = template.find(user_marker)
    contract_start = template.find(contract_marker)
    if (
        system_heading < 0
        or user_start < 0
        or contract_start < 0
        or not system_heading < user_start < contract_start
    ):
        raise GettingReadyGenerationError(
            "Getting Ready prompt template must contain System prompt, User prompt, and Output contract sections in order"
        )
    declared_version = re.search(r"(?m)^Template version:\s*(\S+)\s*$", template)
    if not declared_version:
        raise GettingReadyGenerationError(
            "Getting Ready prompt template must declare its version"
        )
    if declared_version.group(1) != GETTING_READY_TEMPLATE_VERSION:
        raise GettingReadyGenerationError(
            "Getting Ready prompt template version does not match the active manifest contract"
        )
    system_start = system_heading + len(system_marker)
    system_prompt = (
        template[system_start:user_start]
        + "\n## Output contract\n"
        + template[contract_start + len("## Output contract"):]
    ).strip()
    user_template = template[user_start + len("## User prompt"):contract_start].strip()
    template_inputs = set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", user_template))
    missing_inputs = REQUIRED_GETTING_READY_PROMPT_INPUTS - template_inputs
    if missing_inputs:
        raise GettingReadyGenerationError(
            "Getting Ready prompt template is missing required inputs: "
            + ", ".join(sorted(missing_inputs))
        )
    return system_prompt, user_template


def _render_user_prompt(user_template: str, inputs: dict[str, Any]) -> str:
    encoded = {
        "build_name": inputs.get("build_name"),
        "playbook_segment": inputs.get("playbook_segment"),
        "build_specification": inputs.get("build_specification"),
        "benchmark_results": inputs.get("benchmark_results"),
        "customer_software_selections": inputs.get("customer_software_selections", []),
        "software_install_scopes": inputs.get("software_install_scopes", []),
        "purchased_ai_services": inputs.get("purchased_ai_services", []),
        "warranty_start_date": inputs.get("warranty_start_date"),
        "support_base_url": inputs.get("support_base_url"),
        "approved_research_bundle": inputs.get("approved_research_bundle", []),
        "approved_component_manuals": inputs.get("approved_component_manuals", []),
        "upgrade_policy": inputs.get("upgrade_policy", {}),
    }
    placeholders = {
        f"{name}_json": json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        for name, value in encoded.items()
    }

    def replace_template_placeholder(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in placeholders:
            raise GettingReadyGenerationError(
                f"Prompt template contains an unknown input placeholder: {name}"
            )
        return placeholders[name]

    # Substitute only tokens that are part of the template. Inserted JSON is
    # never scanned again, so customer/guide text containing braces remains
    # data and cannot trigger replacement using another input's value.
    return re.sub(r"\{\{([A-Za-z0-9_]+)\}\}", replace_template_placeholder, user_template)


def _component_records(specification: list[Any]) -> list[dict[str, str]]:
    records = []
    for index, component in enumerate(specification):
        if isinstance(component, dict):
            name = next((str(component[key]).strip() for key in ("component_name", "name", "title", "model") if component.get(key)), "")
            component_id = next((str(component[key]).strip() for key in ("component_id", "id", "sku", "mpn") if component.get(key)), f"component-{index + 1}")
        else:
            name = str(component).strip()
            component_id = f"component-{index + 1}"
        if name:
            records.append({"component_id": component_id, "component_name": name})
    return records


def _source_url_is_https(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 1000:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def _component_for_name(name: str, components: list[dict[str, str]]) -> dict[str, str] | None:
    from app.services.component_manual_library import normalize_manual_key

    candidate = normalize_manual_key(name)
    if not candidate:
        return None
    matches = [
        component for component in components
        if candidate == normalize_manual_key(component["component_name"])
    ]
    # Repeated identical parts (for example, a matched pair of DIMMs) share
    # one model-level driver/manual review. Preserve the first build-order row
    # as the representative so sources still bind to an exact model.
    return matches[0] if matches else None


def missing_component_manual_models(
    specification: list[Any],
    manifest: dict[str, Any] | None,
) -> list[str]:
    """Return distinct build models absent from the saved manual-review list."""
    from app.services.component_manual_library import normalize_manual_key

    components = _component_records(specification)
    if not components:
        return ["(no build components recorded)"]
    expected: dict[str, str] = {}
    for component in components:
        expected.setdefault(
            normalize_manual_key(component["component_name"]),
            component["component_name"],
        )
    rows = manifest.get("manual_library_matches") if isinstance(manifest, dict) else None
    represented: set[str] = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            component = _component_for_name(str(row.get("component_name") or ""), components)
            if component and str(row.get("component_id") or "") == component["component_id"]:
                represented.add(normalize_manual_key(component["component_name"]))
    return [name for model_key, name in expected.items() if model_key not in represented]


def missing_component_driver_models(
    specification: list[Any],
    manifest: dict[str, Any] | None,
) -> list[str]:
    """Return distinct build models absent from the saved driver/firmware review list."""
    from app.services.component_manual_library import normalize_manual_key

    components = _component_records(specification)
    if not components:
        return ["(no build components recorded)"]
    expected: dict[str, str] = {}
    for component in components:
        expected.setdefault(
            normalize_manual_key(component["component_name"]),
            component["component_name"],
        )
    rows = manifest.get("driver_and_firmware_review") if isinstance(manifest, dict) else None
    represented: set[str] = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            component = _component_for_name(str(row.get("component_name") or ""), components)
            if component and str(row.get("component_id") or "") == component["component_id"]:
                represented.add(normalize_manual_key(component["component_name"]))
    return [name for model_key, name in expected.items() if model_key not in represented]


def validate_component_driver_outcomes(
    specification: list[Any],
    manifest: dict[str, Any] | None,
    outcomes: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Validate one audited operator outcome for each distinct exact component model."""
    from app.services.component_manual_library import normalize_manual_key

    components = _component_records(specification)
    if not components:
        raise ValueError("The build has no component specification to review")
    missing = missing_component_driver_models(specification, manifest)
    if missing:
        raise ValueError("The driver and firmware manifest is incomplete: " + ", ".join(missing))

    expected: dict[str, dict[str, str]] = {}
    for component in components:
        expected.setdefault(normalize_manual_key(component["component_name"]), component)
    if not isinstance(outcomes, list):
        raise ValueError("Record an outcome for every distinct exact component model")

    approved_sources: dict[str, set[str]] = {}
    sources = manifest.get("sources") if isinstance(manifest, dict) else None
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict) or source.get("topic") not in {"driver_firmware", "compatibility"}:
            continue
        component = _component_for_name(str(source.get("component_name") or ""), components)
        url = source.get("source_url") or source.get("url")
        if component and _source_url_is_https(url):
            approved_sources.setdefault(normalize_manual_key(component["component_name"]), set()).add(str(url))

    normalized: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise ValueError("A driver/firmware outcome has an invalid shape")
        component = _component_for_name(str(outcome.get("component_name") or ""), components)
        if not component or str(outcome.get("component_id") or "") != component["component_id"]:
            raise ValueError("Driver/firmware outcomes must use the exact model and representative component ID")
        model_key = normalize_manual_key(component["component_name"])
        if model_key in normalized:
            raise ValueError(f"Duplicate driver/firmware outcome for {component['component_name']}")
        result = str(outcome.get("outcome") or "")
        if result not in {"updated", "no_update_applicable"}:
            raise ValueError(f"Choose an allowed driver/firmware outcome for {component['component_name']}")
        details = str(outcome.get("details") or "").strip()
        if len(details) < 12:
            raise ValueError(f"Add a meaningful source/version or no-update explanation for {component['component_name']}")
        if len(details) > 1200:
            raise ValueError(f"Keep the driver/firmware outcome for {component['component_name']} under 1,200 characters")
        source_url = outcome.get("source_url")
        if source_url:
            source_url = str(source_url)
            if source_url not in approved_sources.get(model_key, set()):
                raise ValueError(f"The source URL for {component['component_name']} is not in its approved research records")
        if result == "updated" and not source_url:
            raise ValueError(f"An installed update for {component['component_name']} needs an approved manufacturer source")
        normalized[model_key] = {
            "component_id": component["component_id"],
            "component_name": component["component_name"],
            "outcome": result,
            "source_url": source_url,
            "details": details,
        }

    missing_outcomes = [
        component["component_name"]
        for model_key, component in expected.items()
        if model_key not in normalized
    ]
    if missing_outcomes:
        raise ValueError("Record a driver/firmware outcome for every exact model: " + ", ".join(missing_outcomes))
    return [normalized[model_key] for model_key in expected]


def _validate_and_bind_manifest_evidence(manifest: GettingReadyManifest, inputs: dict[str, Any]) -> None:
    """Bind model-suggested component/source references to the supplied records."""
    from app.services.component_manual_library import normalize_manual_key

    components = _component_records(inputs.get("build_specification") or [])
    research = [item for item in inputs.get("approved_research_bundle", []) if isinstance(item, dict)]
    manual_records = [item for item in inputs.get("approved_component_manuals", []) if isinstance(item, dict)]

    for source in manual_records:
        source_url = source.get("source_url") or source.get("manual_url")
        source_component = source.get("component_name") or source.get("component_key")
        if not _source_url_is_https(source_url) or not _component_for_name(str(source_component or ""), components):
            raise GettingReadyGenerationError("Approved component-manual input must use HTTPS and identify one build component")

    def approved_source(url: str | None, component_name: str, topics: set[str]) -> dict[str, Any] | None:
        if not url or not _source_url_is_https(url):
            return None
        normalized_component = _component_for_name(component_name, components)
        if not normalized_component:
            return None
        for source in research:
            if (
                source.get("source_url") == url
                and source.get("topic") in topics
                and _component_for_name(str(source.get("component_name") or ""), components) == normalized_component
            ):
                return source
        if "manual" in topics:
            for source in manual_records:
                source_url = source.get("source_url") or source.get("manual_url")
                source_component = source.get("component_name") or source.get("component_key")
                if source_url == url and _component_for_name(str(source_component or ""), components) == normalized_component:
                    return source
        return None

    def first_approved_source(component_name: str, topics: set[str]) -> dict[str, Any] | None:
        for source in research:
            if (
                source.get("topic") in topics
                and _source_url_is_https(source.get("source_url"))
                and _component_for_name(str(source.get("component_name") or ""), components)
                == _component_for_name(component_name, components)
            ):
                return source
        if "manual" in topics:
            for source in manual_records:
                source_url = source.get("source_url") or source.get("manual_url")
                source_component = source.get("component_name") or source.get("component_key")
                if (
                    _source_url_is_https(source_url)
                    and _component_for_name(str(source_component or ""), components)
                    == _component_for_name(component_name, components)
                ):
                    return source
        return None

    drivers = []
    seen_driver_models: set[str] = set()
    for item in manifest.driver_and_firmware_review:
        component = _component_for_name(item.component_name, components)
        if not component:
            raise GettingReadyGenerationError(
                f"Generated driver guidance refers to no exact component in this build: {item.component_name}"
            )
        model_key = normalize_manual_key(component["component_name"])
        if model_key in seen_driver_models:
            continue
        seen_driver_models.add(model_key)
        source = None
        if item.source_url:
            source = approved_source(item.source_url, component["component_name"], {"driver_firmware", "compatibility"})
            if not source:
                raise GettingReadyGenerationError(
                    f"Generated driver source is not in the approved research bundle for {component['component_name']}"
                )
        drivers.append(item.model_copy(update={
            "component_id": component["component_id"],
            "component_name": component["component_name"],
            "source_title": str(source.get("title")) if source else None,
            "source_accessed_at": str(source.get("accessed_at")) if source else None,
            "administrator_approval_required": True,
        }))
    for component in components:
        model_key = normalize_manual_key(component["component_name"])
        if model_key in seen_driver_models:
            continue
        seen_driver_models.add(model_key)
        source = first_approved_source(component["component_name"], {"driver_firmware", "compatibility"})
        drivers.append(DriverReviewItem(
            component_id=component["component_id"],
            component_name=component["component_name"],
            action="review_required",
            reason=(
                "Review whether manufacturer drivers, firmware, BIOS updates, or utilities apply to this exact component."
                if source else
                "Review whether manufacturer drivers, firmware, BIOS updates, or utilities apply to this exact component. No approved research record was supplied."
            ),
            source_url=(source.get("source_url") or source.get("url")) if source else None,
            source_title=str(source.get("title")) if source and source.get("title") else None,
            source_accessed_at=str(source.get("accessed_at")) if source and source.get("accessed_at") else None,
            administrator_approval_required=True,
        ))
    manifest.driver_and_firmware_review = drivers

    manuals = []
    seen_manual_models: set[str] = set()
    for item in manifest.manual_library_matches:
        component = _component_for_name(item.component_name, components)
        if not component:
            raise GettingReadyGenerationError(
                f"Generated manual match refers to no exact component in this build: {item.component_name}"
            )
        model_key = normalize_manual_key(component["component_name"])
        if model_key in seen_manual_models:
            continue
        seen_manual_models.add(model_key)
        source = None
        if item.manual_url:
            source = approved_source(item.manual_url, component["component_name"], {"manual"})
            if not source:
                raise GettingReadyGenerationError(
                    f"Generated manual URL is not in the approved sources for {component['component_name']}"
                )
        manuals.append(item.model_copy(update={
            "component_id": component["component_id"],
            "component_name": component["component_name"],
            "manual_title": (source.get("title") or source.get("manual_title")) if source else None,
            "manual_url": item.manual_url if source else None,
            "match_status": "needs_admin_confirmation" if source else "needs_research",
            "administrator_approval_required": True,
        }))
    for component in components:
        model_key = normalize_manual_key(component["component_name"])
        if model_key in seen_manual_models:
            continue
        seen_manual_models.add(model_key)
        source = first_approved_source(component["component_name"], {"manual"})
        manuals.append(ManualMatch(
            component_id=component["component_id"],
            component_name=component["component_name"],
            manual_title=(source.get("title") or source.get("manual_title")) if source else None,
            manual_url=(source.get("source_url") or source.get("manual_url")) if source else None,
            match_status="needs_admin_confirmation" if source else "needs_research",
            administrator_approval_required=True,
        ))
    manifest.manual_library_matches = manuals

    approved_urls = set()
    approved_source_records = []
    for source in [*research, *manual_records]:
        url = source.get("source_url") or source.get("manual_url")
        if _source_url_is_https(url):
            approved_urls.add(str(url))
            approved_source_records.append(dict(source))
    for source in manifest.sources:
        url = source.get("source_url") or source.get("url") if isinstance(source, dict) else None
        if url and (not _source_url_is_https(url) or url not in approved_urls):
            raise GettingReadyGenerationError("Generated source list includes a URL outside the approved evidence bundle")
    manifest.sources = approved_source_records


def _authoritative_software_install_plan(inputs: dict[str, Any]) -> dict[str, Any]:
    """Bind selected app IDs and timing to the reviewed software allow-list."""
    selected_ids = validate_package_ids(inputs.get("customer_software_selections", []))
    scopes = {
        item.get("package_id"): item.get("scope")
        for item in inputs.get("software_install_scopes", [])
        if isinstance(item, dict)
    }
    machine_scope_ids: list[str] = []
    customer_profile_ids: list[str] = []
    for package_id in selected_ids:
        expected_scope = SOFTWARE_BY_ID[package_id].get("install_scope", "machine")
        if expected_scope not in {"machine", "customer_profile"}:
            raise GettingReadyGenerationError(f"Unsupported install scope for approved package {package_id}")
        if package_id in scopes and scopes[package_id] != expected_scope:
            raise GettingReadyGenerationError(f"Install scope input does not match the software allow-list for {package_id}")
        if expected_scope == "customer_profile":
            customer_profile_ids.append(package_id)
        else:
            machine_scope_ids.append(package_id)
    return {
        "selected_package_ids": selected_ids,
        "machine_scope_package_ids": machine_scope_ids,
        "customer_profile_package_ids": customer_profile_ids,
        "unresolved_package_ids": [],
        "notes": (
            ["Selected machine-scope apps are prepared during workshop setup."] if machine_scope_ids else []
        ) + (
            ["Selected user-scope apps are scheduled for the signing-in Windows profile."]
            if customer_profile_ids else []
        ),
    }


async def generate_getting_ready_manifest(inputs: dict[str, Any]) -> GettingReadyManifest:
    """Generate a review-only manifest using the globally configured LLM order.

    Research is injected as a source-bounded evidence bundle by callers. This
    service does not browse or execute LLM-generated scripts.
    """
    system_prompt, user_template = _template_sections()
    user_prompt = _render_user_prompt(user_template, inputs)
    prompt_size = len((system_prompt + user_prompt).encode("utf-8"))
    if prompt_size > GETTING_READY_PROMPT_MAX_BYTES:
        raise GettingReadyPromptSizeError(
            "Getting Ready prompt exceeds the configured input budget; reduce build or reviewed source material"
        )
    try:
        result = await model_selection_service.complete(
            task="Getting Ready dispatch package content",
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            max_tokens=8000,
            timeout=180,
            json_mode=True,
        )
        payload = json.loads(result.text)
        manifest = GettingReadyManifest.model_validate(payload)
    except Exception as exc:
        raise GettingReadyGenerationError(
            f"Could not produce a valid Getting Ready content manifest: {exc}"
        ) from exc

    expected_name = str(inputs.get("build_name") or "")
    if manifest.build_name != expected_name:
        raise GettingReadyGenerationError(
            "The generated manifest build name does not match the source build."
        )
    manifest.software_install_plan = SoftwareInstallPlan.model_validate(
        _authoritative_software_install_plan(inputs)
    )
    if manifest.template_version != GETTING_READY_TEMPLATE_VERSION:
        raise GettingReadyGenerationError(
            "The generated manifest does not match the active prompt-template version."
        )
    try:
        _validate_and_bind_manifest_evidence(manifest, inputs)
    except GettingReadyGenerationError:
        raise
    except Exception as exc:
        raise GettingReadyGenerationError(f"Generated evidence references could not be validated: {exc}") from exc
    return manifest
