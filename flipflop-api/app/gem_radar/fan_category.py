"""Guard against fan products being assigned to the PC-case cohort."""
import hashlib
import re


_FAN_PRODUCT = re.compile(
    r"\b(?:case\s+fan|pc\s+fan|cooling\s+fan|rgb\s+fan|uni\s+fan|"
    r"fan\s+(?:kit|pack)|(?:120|140|200)\s*mm\b.{0,65}\bfan\b|"
    r"\bfan\b.{0,25}\b(?:120|140|200)\s*mm\b)", re.I,
)
_CHASSIS = re.compile(r"\b(?:pc\s+case|computer\s+case|(?:atx|gaming|tower)\s+case|chassis|enclosure|mid[ -]?tower|full[ -]?tower|mini[ -]?tower)\b", re.I)


def is_standalone_fan(title: str, data: dict | None = None) -> bool:
    if _CHASSIS.search(title):
        return False
    if re.search(r"\bcontroller\b", title, re.I) and not re.search(r"\b(?:120|140|200)\s*mm\b", title, re.I):
        return False
    specs = (data or {}).get("specs") or {}
    # Model metadata alone is not proof: legacy case CPKs can have incorrect
    # specs too. A fan-only triple pack often omits the word "fan" in title.
    triple_pack = re.search(r"\b(?:120|140|200)\s*mm\b.{0,25}\b(?:pwm|argb|rgb)\b.{0,30}\b(?:triple|3[ -]?pack)\b", title, re.I)
    return bool(_FAN_PRODUCT.search(title) or (str(specs.get("type", "")).lower() == "fan" and triple_pack))


def correct_case_fan_cpk(title: str, data: dict) -> tuple[str, dict]:
    """Keep brand/model, but isolate confirmed fans in a fan CPK."""
    if data.get("category") != "case" or not data.get("brand") or not data.get("model") or not is_standalone_fan(title, data):
        return data.get("cpk"), data
    corrected = {**data, "category": "fan"}
    corrected["cpk"] = hashlib.sha256(
        f"fan|{data['brand']}|{data['model']}".encode()
    ).hexdigest()[:16]
    return corrected["cpk"], corrected
