"""Deterministic single-catalogue range; ranking never grants sales approval."""
import re

RANGE_BUCKETS = ("cpu", "motherboard", "gpu", "ram", "nvme", "sata", "psu", "cooling", "case")


def pinned_catalogue_role(specs):
    """An explicit operator inclusion survives ranking changes, not deletion."""
    if not isinstance(specs, dict) or specs.get("catalogue_deleted"):
        return None
    pin = specs.get("curated_range_pin") or {}
    return pin.get("role") if isinstance(pin, dict) and pin.get("role") in {
        "cpu", "motherboard", "gpu", "ram", "storage", "psu", "cooling", "case"
    } and pin.get("reason") else None


def authored_requirements(build):
    for role, specification in (build.get("components") or {}).items():
        values = str(specification).split("+") if role in {"storage", "storage_secondary"} else [specification]
        for value in values:
            yield role, value.strip() if isinstance(value, str) else value


def range_bucket(category, title):
    role = {"cooler": "cooling", "ssd": "storage", "storage_secondary": "storage"}.get(category, category)
    if role == "storage":
        if re.search(r"\bsata\b", title, re.I):
            return "sata"
        if re.search(r"\bnvme\b|\bpci[- ]?e\b|\bpcie\b", title, re.I):
            return "nvme"
        return None  # M.2 alone does not establish SATA versus NVMe.
    return role if role in RANGE_BUCKETS else None


def _matches_requirement(role, title, specification):
    if not specification:
        return False
    if role in {"cpu", "gpu"}:
        from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu
        normalize = normalise_cpu if role == "cpu" else normalise_gpu
        wanted = normalize(specification)
        if role == "gpu":
            from app.services.curated_build_policy import _capacity_gb
            required_memory = _capacity_gb(specification)
            actual_memory = _capacity_gb(title)
            if actual_memory is None:
                short = re.search(r"\b(\d{1,2})G\b", title, re.I)
                actual_memory = float(short.group(1)) if short else None
            if required_memory and (actual_memory is None or actual_memory < required_memory):
                return False
        return bool(wanted and wanted == normalize(title))
    if role in {"storage", "storage_secondary"}:
        from app.services.curated_build_policy import _capacity_gb, _customer_option
        wanted = _customer_option('storage', specification, {})
        actual = _customer_option('storage', title, {})
        if not wanted.get('capacity_gb') or not actual.get('capacity_gb') or actual['capacity_gb'] < wanted['capacity_gb']:
            return False
        if wanted.get('interface') and wanted['interface'] != actual.get('interface'):
            return False
        if re.search(r'\bssd\b', specification, re.I) and not re.search(r'\bssd\b|solid state|\bnvme\b', title, re.I):
            return False
        return True
    if role in {"ram", "storage", "storage_secondary"}:
        from app.services.curated_build_policy import _matches_curated_spec
        if role == "ram" and any(re.search(rf"\b{term}\b", specification, re.I) and not re.search(rf"\b{term}\b", title, re.I) for term in ("ecc", "rdimm")):
            return False
        return _matches_curated_spec("storage" if role == "storage_secondary" else role, {"title": title}, specification)
    normalize = lambda text: re.sub(r"[^a-z0-9]", "", text.casefold())
    wanted = normalize(specification)
    return len(wanted) >= 8 and wanted in normalize(title)


def select_curated_range(observations, builds):
    """Top ten per hardware bucket, all ranked cases, plus authored exceptions.

    Input must already contain only eligible observations from each category's
    latest captured list. One best-ranked exact fallback is retained for each
    authored requirement that the normal range cannot cover.
    """
    selected, reasons, buckets = {}, {}, {}
    ordered = sorted(observations, key=lambda row: (row.rank or 100000, row.asin))
    for row in ordered:
        if row.rank is None:
            continue
        bucket = range_bucket(row.category, row.title)
        if bucket is None:
            continue
        items = buckets.setdefault(bucket, [])
        if row.asin in {item.asin for item in items}:
            continue
        items.append(row)
        # All eligible cases in the captured Best Sellers list are allowed;
        # other hardware families remain limited to their top ten.
        if bucket == "case" or len(items) <= 10:
            key = (row.category, row.asin)
            selected[key] = row
            reasons[key] = {"kind": "bestseller", "bucket": bucket, "rank": row.rank}
    for build in builds:
        used_storage_asins = set()
        for role, specification in authored_requirements(build):
            candidates = [row for row in ordered if
                {"cooler": "cooling", "ssd": "storage"}.get(row.category, row.category) == ("storage" if role == "storage_secondary" else role)
                and _matches_requirement(role, row.title, specification)
                and (role not in {'storage','storage_secondary'} or row.asin not in used_storage_asins)]
            existing = next((row for row in candidates if (row.category, row.asin) in selected), None)
            if existing:
                if role in {'storage','storage_secondary'}: used_storage_asins.add(existing.asin)
                continue
            if not candidates:
                continue
            if role in {'ram','storage','storage_secondary'}:
                from app.services.curated_build_policy import _capacity_gb
                minimum = _capacity_gb(specification) or 0
                candidates.sort(key=lambda item: ((_capacity_gb(item.title) or minimum)-minimum, item.rank or 100000, item.asin))
            row = candidates[0]
            if role in {'storage','storage_secondary'}: used_storage_asins.add(row.asin)
            key = (row.category, row.asin)
            selected[key] = row
            reasons[key] = {"kind": "playbook_requirement", "cell": build.get("name") or build.get("id"),
                "role": role, "requirement": specification, "rank": row.rank, "bucket": range_bucket(row.category, row.title)}
    return list(selected.values()), reasons
