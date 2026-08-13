"""Deterministic product identity resolution from listing titles (PRD §10).

Reuses the CPU/GPU regex patterns already proven in app.services.spec_parser
(built for full-PC listing titles) rather than re-deriving them, and adds
RAM-kit identity extraction (capacity/configuration/speed/latency) since
Gem Radar scans standalone component listings, not just complete PCs.

This is pure regex/heuristic extraction — no network calls, no LLM calls.
Claude is only invoked (see claude_screening.py) when this returns low
confidence, per PRD §29.1 "Claude should... resolve ambiguous product
identity" — it augments, it does not replace, this deterministic pass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.services.spec_parser import CPU_PATTERNS, GPU_PATTERNS

# RAM identity used to be one sequential pattern requiring capacity, then
# optional filler words, then DDR-generation, then optional speed — in that
# exact order. Real listing titles don't respect that order: major RAM
# brands (Kingston, Crucial, Corsair, G.Skill, KLEVV) routinely put speed
# BEFORE the DDR-generation token ("3600MHz DDR4"), put DDR-generation
# BEFORE capacity entirely ("Crucial DDR4 RAM 16GB..."), or interpose CAS
# latency between speed and DDR-gen ("6000MHz C30 DDR5") — a fixed sequence
# missed the overwhelming majority of real RAM titles from these brands
# (verified: 0/8 sampled real listings matched the old pattern; every RAM
# listing from a major brand was silently falling through with no category
# AND no model, showing up as "Other" on the dashboard and pricing against
# nothing). Matching each piece independently, then assembling whatever was
# found, is robust to word order because there simply isn't an order
# requirement anymore.
_RAM_CAPACITY_PATTERN = re.compile(r"(\d+)\s*gb\s*(?:\((\d+)\s*x\s*(\d+)\s*gb\))?", re.IGNORECASE)
_RAM_DDR_GEN_PATTERN = re.compile(r"\bddr([345])\b", re.IGNORECASE)
_RAM_SPEED_PATTERN = re.compile(r"\b(\d{3,5})\s*(?:mhz|mt/s)\b", re.IGNORECASE)
# Fallback for titles that state speed as a bare number right after the
# DDR-gen token with no MHz/MT/s unit at all (e.g. "DDR4 2666") — anchored
# to that position so it can't misfire on an unrelated number elsewhere in
# the title.
_RAM_SPEED_AFTER_DDR_PATTERN = re.compile(r"\bddr[345][\s-]+(\d{3,5})\b", re.IGNORECASE)
# Category-detection only: true if the title mentions BOTH a GB capacity and
# a DDR generation anywhere, regardless of order — a lightweight boolean
# check, not the full model-assembly logic below.
_RAM_CATEGORY_PATTERN = re.compile(r"(?=.*\d+\s*gb)(?=.*\bddr[345]\b)", re.IGNORECASE)
_CL_PATTERN = re.compile(r"cl\s?(\d{1,2})", re.IGNORECASE)

# SSD product-line/part-number patterns, ordered most-specific first (a
# manufacturer part number like "SSDPEKNU512GZ" or "MZ-VLB256B" identifies
# the exact SKU; a bare series name like "980 PRO" identifies the product
# line, which is enough to match against real market comps for that line).
# Added because resolve_identity() used to have NO model extraction at all
# for ssd/motherboard/cooler — every listing in these categories fell
# through to exact_sku_confidence=0 and a generic category-wide benchmark
# regardless of how clearly branded/identifiable the title was (see the Gem
# Radar classification audit — "Samsung 980 PRO", "ASUS ROG Strix B650-A",
# "Noctua NH-U9S" were all being priced against "any SSD"/"any motherboard"/
# "any cooler" instead of their own real market).
SSD_PATTERNS = [
    r"\bmz-[a-z0-9]{5,}\b",  # Samsung part numbers, e.g. MZ-VLB256B, MZ-V9S4T0BW
    r"\bssdpe[a-z0-9]{5,}\b",  # Intel part numbers, e.g. SSDPEKNU512GZ
    r"\b\d{3}\s*evo\s*plus\b",  # Samsung 970/990 EVO Plus (before the bare EVO pattern below)
    r"\b\d{3}\s*(?:pro|evo|qvo)\b",  # Samsung 980 PRO, 970 EVO, 870 QVO
    r"\bpm9[a-z0-9]{1,3}a?\b",  # Samsung OEM PM9x1/PM9A1 series
    r"\bpm8[a-z0-9]{1,3}\b",  # Samsung OEM PM8xx series
    r"\bsn\d{3,4}[a-z]?\b",  # WD/SanDisk Blue/Black SN series: SN500, SN550, SN730, SN850
    r"\bsnv\d[a-z]?s?(?:/\d+[a-z]?)?\b",  # Kingston NV-series part numbers, e.g. SNV2S/1000G
    r"\bnv\d\b",  # Kingston NV1/NV2 series name
    r"\bkc\d{3,4}\b",  # Kingston KC600/KC3000
    r"\bnv\d{4}\b",  # Netac NV2000/NV3000/NV7000
    r"\bxg\d(?:-p)?\b",  # Toshiba/Kioxia XG5, XG5-P, XG6, XG8
    r"\bmx\d{3}\b",  # Crucial MX500
    r"\bbx\d{3}\b",  # Crucial BX500
    # Crucial P-series (P2/P3/P5, and newer 3-digit lines like P310/P510).
    # Requires "Crucial" adjacent to the P-number rather than a bare "P3"
    # (too ambiguous on its own). The previous version of this check used a
    # forward lookahead "(?=.*\bcrucial\b)" from the P-number's position —
    # which only matches if "Crucial" appears AFTER the number in the
    # string. Every real Crucial listing has the brand name FIRST ("Crucial
    # P3 1TB..."), so that lookahead could never actually succeed; this
    # pattern has effectively never matched a real title. Matching brand
    # immediately followed by the model number fixes the direction and
    # covers the newer 3-digit P3xx/P5xx lines the old single-digit
    # "p[235]" character class didn't include either.
    r"\bcrucial\s+p\d{1,3}\b",
    r"\b\d{3,4}p\s*series\b",  # Intel 600p/660p/670p series
    r"\bmicron\s*\d{4}\b",  # Micron 2300/2450/2550 series
    r"\bmodel\s*1[789]\d{2}\b",  # Microsoft Surface internal SSD model numbers, e.g. "Model 1911"
    r"\b[a-z]{2,4}\d[a-z0-9]{2,}-[a-z0-9]{4,}\b",  # generic hyphenated part numbers, e.g. ADATA SM2P41C8-256GC
]

# Motherboard manufacturer part numbers (MSI "MS-xxxx", Gigabyte "GA-xxxx")
# — matched first since these identify the exact board unambiguously.
_MOBO_PART_NUMBER_PATTERN = re.compile(r"\b(ms-\d{3,5}|ga-[a-z0-9]{2,}(?:-[a-z0-9]+)*)\b", re.IGNORECASE)
# Chipset code that most motherboard model names are built around. AMD's A-
# and X-series chipsets are always exactly 3 digits (A320, A520, X570, X670
# — never "A13"), while Intel's H/B/Z/Q tiers run 2-3 digits (H110, B450,
# Z790, Q670) — enforcing that per-prefix, rather than accepting 2-3 digits
# after any of the six letters, is what keeps this from false-matching on
# unrelated model numbers that happen to start with one of those letters
# (e.g. an AIO liquid cooler's own "A13" product code inside a
# cross-compatibility blurb, which isn't a chipset at all). Matched, then
# extended with up to a few following words to capture the rest of the
# board name (e.g. "ROG Strix B650-A Gaming" or "PRIME A520M-A II"),
# stopping at words that describe the board generically rather than naming it.
_MOBO_CHIPSET_PATTERN = re.compile(r"\b(?:[ax]\d{3}|[bhzq]\d{2,3})[a-z]{0,2}(?:-[a-z0-9]+)?\b", re.IGNORECASE)
_MOBO_NAME_STOPWORDS = {
    "motherboard", "mobo", "mainboard", "atx", "matx", "m-atx", "micro", "mini-itx", "itx", "eatx",
    "ddr3", "ddr4", "ddr5", "socket", "am4", "am5", "lga1151", "lga1200", "lga1700", "lga1150",
    "for", "with", "supports", "and", "cpu", "cpus", "processor", "wifi", "wi-fi", "bluetooth",
    "used", "new", "tested", "working", "no", "i/o", "shield", "plate", "bundle", "combo",
    "amd", "intel",
}

# Cooler product-line names by brand. Brand match is required alongside the
# line name (unlike SSD/CPU/GPU part numbers, generic words like "rock",
# "alpine", or "elite" alone are too ambiguous to trust as an identity
# signal) — see COOLER_PATTERNS below, each entry pairs a brand with its
# line-name pattern.
COOLER_PATTERNS = [
    (r"be\s*quiet!?", r"(dark\s*rock\s*(?:pro|elite|slim|4|5)?|pure\s*rock\s*(?:slim|2|3)?|shadow\s*rock\s*\d?|silent\s*loop\s*\d?)"),
    (r"noctua", r"(nh-[a-z0-9]+)"),
    # `i{1,3}` covers Liquid Freezer II AND the newer III line — the
    # previous `(?:ii)?` only ever matched "II" or nothing, silently missing
    # every "Liquid Freezer III" listing (a distinct, differently-priced
    # generation, same failure mode as the Ryzen X3D truncation bug).
    # `(?:aio\s*)?` between the generation numeral and the radiator size
    # accounts for "Liquid Freezer III AIO 280mm" — real titles routinely
    # insert "AIO" there rather than putting the size directly after the
    # numeral.
    (r"arctic", r"(liquid\s*freezer\s*(?:i{1,3})?\s*(?:aio\s*)?\d{2,3}|freezer\s*\d{1,2}(?:\s*(?:x|a-rgb))?|alpine\s*\d{1,2})"),
    # Thermalright's own product-line names (Assassin X/King, AXP-series,
    # Aqua Elite, Peerless Assassin, Phantom Spirit, Frozen Warframe) are
    # distinctive and unambiguous enough in a PC-parts title to stand in for
    # the brand name itself — sampled real listings routinely drop
    # "Thermalright" entirely ("Assassin King 120 SE CPU Air Cooler...",
    # "AQUA ELITE 240 White V3 CPU Cooler...") since the requirement of
    # BOTH the literal brand name AND a line match meant these never
    # resolved at all despite being perfectly identifiable products.
    (
        r"thermalright|assassin\s*(?:x|king)|aqua\s*elite|axp\d{2,3}|peerless\s*assassin|phantom\s*spirit|frozen\s*warframe",
        r"(peerless\s*assassin\s*\d{2,3}|assassin\s*(?:x|king)\s*\d{2,3}[a-z0-9]*(?:\s*(?:se|plus))?|"
        r"frozen\s*warframe|phantom\s*spirit\s*\d{2,3}|aqua\s*elite\s*\d{2,3}(?:\s*v\d)?|axp\d{2,3}\s*[a-z0-9]*)",
    ),
    (r"cooler\s*master", r"(hyper\s*\d{2,3}|masterliquid\s*[a-z0-9]+|masterair\s*[a-z0-9]+)"),
    (r"deepcool", r"(ak\d{3}|gammaxx\s*[a-z0-9]+|castle\s*[a-z0-9]+|ag\d{3})"),
    # "Nautilus" is Corsair's newer AIO line (replacing the "H-series"
    # naming for recent models) — added alongside, not instead of, H-series.
    (r"corsair", r"(nautilus\s*\d{2,3}(?:\s*rs)?|h\d{2,3}[a-z]?(?:\s*(?:rgb|elite|capellix))*|a\d{3})"),
    # "T-series" (T120/T240) is NZXT's air-cooler line, distinct from the
    # Kraken AIO line already covered.
    (r"nzxt", r"(kraken\s*[a-z0-9]+|t\d{2,3})"),
    (r"asus", r"(proart\s*lc\s*\d{2,3})"),
    # Gigabyte's cooler part numbers ("GH-PDU21-MF") don't follow a
    # consumer-friendly product-line name the way most other brands do.
    (r"gigabyte", r"(gh-[a-z0-9]+(?:-[a-z0-9]+)?)"),
    (r"jonsbo", r"(cr-\d{3,4}(?:\s*evo)?)"),
    # AMD's own bundled stock coolers (Wraith Stealth/Prism/Spire) ship with
    # most retail-boxed Ryzen CPUs and are resold constantly on their own —
    # extremely common in sampled data (dozens of instances) but not a
    # third-party brand, so it needed its own entry rather than fitting
    # anywhere above.
    (r"amd|wraith", r"(wraith\s*(?:stealth|prism|spire|max)?)"),
    (r"montech", r"(sky\s*\d{3}|air\s*\d{3}|title\s*\d{2,3})"),
]

# Case model extraction — brand + line/part number, same "close enough for
# price comparability" trade-off as PSU/RAM (an exact SKU is not required,
# just enough to group same-or-similar-value cases together). Limited to
# the brands actually observed with real volume in sampled unmatched
# listings (Antec, Lian Li, Fractal Design, DeepCool, Phanteks, HYTE) —
# see _CASE_BRAND_NAMES above, which drives category detection for the
# same brand set.
CASE_PATTERNS = [
    (r"antec", r"(constellation\s*c\d{1,2}|flux\s*(?:pro)?|p7s|cx\d{3}|c\d{1,2}(?:\s*(?:argb|curve))?)"),
    (r"lian\s*li", r"(o11\s*dynamic(?:\s*(?:evo|mini(?:\s*v?\d)?))?|lancool\s*\d{2,3}[a-z]?|pc-\d{2}[a-z]?|uni\s*fan\s*[a-z0-9]+)"),
    (r"fractal(?:\s*design)?", r"(north(?:\s*momentum)?|define\s*\d(?:\s*xl)?|meshify\s*\d[a-z]?|core\s*\d{3,4})"),
    (r"deepcool", r"(ch\d{3}(?:\s*plus)?|matrexx\s*\d{2}[a-z]?)"),
    (r"phanteks", r"(xt\s*pro|eclipse\s*[a-z0-9]+)"),
    (r"hyte", r"(y\d{2}(?:\s*touch)?|x\d{2}\s*(?:air)?)"),
]
_BRAND_PATTERN = re.compile(
    r"\b(corsair|kingston|crucial|g\.?skill|adata|team\s?group|patriot|amd|intel|nvidia|asus|msi|gigabyte|"
    r"asrock|seagate|western\s?digital|wd|samsung|evga|zotac|palit|sapphire|xfx|powercolor|"
    # Cooler/case brands — previously missing entirely from this pattern
    # despite COOLER_PATTERNS/CASE_PATTERNS already gating model extraction
    # on these same brand names. That meant resolved.brand stayed None for
    # nearly every cooler/case listing (Arctic, Noctua, Thermalright,
    # DeepCool, be quiet!, Cooler Master, NZXT, ...), silently losing the
    # "model and brand" confidence bonus in resolve_identity for a whole
    # category of listings.
    r"be\s*quiet!?|noctua|arctic|thermalright|cooler\s*master|deepcool|nzxt|jonsbo|montech|"
    r"antec|lian\s*li|fractal(?:\s*design)?|phanteks|hyte)\b",
    re.IGNORECASE,
)

# PSU model extraction has no exact-SKU pattern per brand (too many product
# lines to enumerate individually, unlike coolers) — brand + wattage + 80
# PLUS tier is used as a "close enough for price comparability" proxy
# instead, same trade-off _extract_ram_model already makes for RAM (capacity
# + DDR gen + speed rather than a literal part number).
_PSU_BRAND_PATTERN = re.compile(
    r"\b(corsair|evga|seasonic|be\s*quiet!?|cooler\s*master|thermaltake|antec|fsp|silverstone|xfx|gigabyte|"
    r"msi|asus|super\s*flower|montech|deepcool|nzxt)\b",
    re.IGNORECASE,
)
_PSU_WATTAGE_PATTERN = re.compile(r"\b(\d{3,4})\s?w\b", re.IGNORECASE)
_PSU_TIER_PATTERN = re.compile(r"\b(bronze|silver|gold|platinum|titanium)\b", re.IGNORECASE)

# Packaging/protection/mounting-hardware titles frequently name the component
# they're FOR (e.g. "CPU Processor Protector Plastic Case Clamshell Intel AMD
# Motherboard Protector", "CPU Fan Cooler Bracket Radiator Mount AMD
# Motherboard Heatsink Mounting for AM4") even though the listing itself is
# not that component. Left unchecked, category detection below fires on the
# bare keyword match, the listing gets no extractable model number, and the
# pipeline falls back to searching real market benchmarks using the raw
# title — matching real motherboard/CPU/cooler listings and comparing them
# against a £3 accessory, producing a wildly inflated "deal score".
#
# A distinct but equally damaging variant: listings that explicitly disclaim
# containing the actual chip — "AMD Ryzen 7 9800X3D AM5 Socket CPU *BOX
# ONLY*" (an empty box, £13.37, matched against real £1,181 CPU prices —
# 8735% ROI, scored SUPER_GEM), "CPU Fan Cooler - Processor Not Included",
# "box with Cooler - NO CPU - Empty Box". These name the real product to
# describe what's MISSING, and are just as dangerous to price-match against
# real component data as a protector case is.
_ACCESSORY_KEYWORDS = re.compile(
    r"\b(protector|protective\s*case|clamshell|dust\s*cover|anti[\s-]?static\s*bag|"
    r"carry(?:ing)?\s*case|storage\s*box|stand\s*for|holder|pouch|sleeve|skin|decal|sticker|"
    r"bracket|backplate|mounting\s*kit|mounting\s*for|screw\s*kit|"
    r"thermal\s*(?:pad|paste|compound|grease|paste\s*syringe)|"
    # Same failure mode as bracket/backplate above: a WiFi antenna, BIOS
    # chip, or compatibility cable/adapter listing routinely names the real
    # component it's compatible with in its own title ("...Antenna For ASUS
    # Z390 Z490 X570 Motherboard", "USB Interface Cable for CORSAIR h80i",
    # "BIOS Chip For Asus H110M-A"), which is enough for both category
    # detection and model extraction to mistake the £5 accessory for the
    # component itself.
    r"(?:wifi|wi-fi|replacement)\s*antenna|antenna\s*for|"
    r"bios\s*chip|(?:usb\s*)?(?:interface\s*)?(?:cable|adapter)\s*for|"
    r"box\s*only|empty\s*box|not\s*included|no\s*(?:cpu|gpu|ram|processor|chip)|"
    # Same failure mode as "box only"/"empty box" but phrased as what IS
    # present rather than what's missing — "Motherboard Box And user
    # guide/CD's", "Box + Manual", "Box With Instructions" — real second-hand
    # components don't sell for a few pounds; a listing describing itself as
    # box/manual/CD contents is describing packaging, not the component,
    # regardless of whether it also happens to omit "only"/"empty".
    r"box\s*(?:and|with|\+)\s*(?:the\s*)?(?:user\s*)?(?:guide|manual|instructions?|cds?|discs?))\b",
    re.IGNORECASE,
)

# eBay's own accessibility text ("New listing", "Opens in a new window or
# tab") gets glued directly onto the real title with no separating space by
# some scrape paths — e.g. "...DDR4 MotherboardOpens in a new window or
# tab". Left unstripped, this breaks every \b word-boundary regex above and
# below (no boundary between two letters), which can silently misclassify
# or fail to flag a listing as an accessory. Mirrors the admin dashboard's
# own _stripScrapeArtifacts (flipflop-admin/app/sourcing/page.tsx) — kept in
# sync there rather than shared, since this is the only place both a Python
# and a TypeScript copy exist.
_SCRAPE_ARTIFACT_PREFIX = re.compile(r"^New listing", re.IGNORECASE)
_SCRAPE_ARTIFACT_SUFFIX = re.compile(r"Opens in a new window or tab$", re.IGNORECASE)
# "AMD Ryzen® 5 7600X" routinely comes back as "AMD Ryzensets 5 7600X" — the
# ® (or ™) trademark glyph appears to get mangled into the literal text
# "sets" somewhere upstream (scrape/encoding step outside this codebase),
# consistently and only after the word "Ryzen". This broke both category
# detection and CPU model extraction for every AMD Ryzen listing hit by it
# (confirmed: 74 listings in one sample, all with real, otherwise-complete
# spec info in the title — "Ryzensets 5 7600X" candidly parses as no CPU at
# all under CPU_PATTERNS). "Ryzensets" is not an English or product word, so
# this substitution is unambiguous.
_RYZEN_CORRUPTION = re.compile(r"\bryzensets\b", re.IGNORECASE)


def _strip_scrape_artifacts(title: str) -> str:
    title = _SCRAPE_ARTIFACT_SUFFIX.sub("", _SCRAPE_ARTIFACT_PREFIX.sub("", title)).strip()
    return _RYZEN_CORRUPTION.sub("Ryzen", title)


def is_likely_accessory(title: str) -> bool:
    """True when a title is clearly packaging/protection for a component
    rather than the component itself — callers must not price-compare this
    listing against real component market data."""
    return bool(_ACCESSORY_KEYWORDS.search(_strip_scrape_artifacts(title)))


# A full laptop/prebuilt/workstation routinely lists its own SSD/RAM/fan
# specs in the title ("Lenovo 15.6 Inch Laptop...512GB SSD", "HP Pavilion
# ...16GB RAM", "Asus X870 MAX GAMING WIFI7...4 DDR5..." — a motherboard
# whose spec sheet mentions RAM slots) — bare keyword category detection
# below has no way to tell "this listing IS an SSD" from "this listing
# MENTIONS an SSD as one spec of a much bigger product," so these were
# getting miscategorized as the cheap component they merely mention, then
# (harmlessly, since no comp existed) failing to price-match, or (more
# dangerously, if a coincidental comp DID exist) scored as an absurdly good
# "SSD" deal at a whole-laptop price. Checked first, same as accessories.
_FULL_SYSTEM_KEYWORDS = re.compile(
    r"\b(laptop|notebook|chromebook|ultrabook|macbook|"
    # Negative lookahead: "Desktop PC Case Fan"/"Gaming PC Cooler"/"Tower PC
    # PSU" are standalone accessories FOR a desktop PC, not a full system —
    # without it, "Desktop PC Case Fan 12cm" (a £3 case fan) matched
    # "desktop pc" and got its category force-cleared to None before the
    # category keyword scan ever ran, since this check short-circuits ahead
    # of it entirely.
    r"(?:desktop|gaming|workstation|tower)\s*pc(?!\s*(?:case(?:\s*fan)?|cooler|fan|psu|power\s*supply))|"
    r"prebuilt|pre-built|"
    r"all-in-one|aio\s*pc|mini\s*pc|complete\s*(?:pc|system|build)|"
    r"full\s*(?:pc|system|build)|"
    # Not every full-system listing names itself a "PC"/"laptop" (e.g. "HP
    # 285 G3 MT" — HP's own model naming for a micro-tower desktop, with no
    # generic system-type word at all) — but a genuine standalone SSD/RAM/
    # PSU/case/cooler/fan listing never states a pre-installed OS. A
    # Windows version mention is a strong, distinct signal that this is a
    # complete, bootable system, not a bare part.
    r"win(?:dows)?\s*(?:10|11))\b",
    re.IGNORECASE,
)

# Backstop for full systems that don't use any of the keywords above (e.g. a
# custom build sold as "Asus X870 Motherboard + Ryzen 9 + 32GB RAM bundle,
# cash on collection" with no single word flagging it as "a system"): if a
# listing resolves to one of these categories but its price is far beyond
# what a genuine standalone part of that type sells for, something is
# wrong — either it's a bundle/full system, or the price was mis-scraped.
# Deliberately excludes cpu/gpu: genuine standalone parts in those
# categories legitimately cost £1000+, so a price ceiling there would flag
# real high-end hardware as suspicious instead of catching bundles.
_CATEGORY_PRICE_CEILING: dict[str, float] = {
    "ram": 500.0,
    "ssd": 500.0,
    "psu": 400.0,
    "case": 400.0,
    "cooler": 300.0,
    "fan": 150.0,
    "motherboard": 800.0,
}


# Deliberately NOT folded into _ACCESSORY_KEYWORDS/_CATEGORY_KEYWORDS above,
# which govern category resolution for every single listing scraped. Riser
# cables and standalone fans are real, resolvable categories/pass the
# accessory check today, and re-litigating that for every listing (most of
# which are AVERAGE_DEAL/POOR_DEAL and nobody will ever look at) isn't worth
# the false-positive risk. This is a second, stricter pass applied ONLY to
# listings that already scored GEM/SUPER_GEM — the small, high-value subset
# a human will actually act on — to catch cases like a fan kit or riser
# cable slipping through as a "great find" before it's ever worth spending
# an LLM call confirming or denying it.
_GEM_JUNK_KEYWORDS = re.compile(
    r"\b(riser\s*cable|riser\s*card|pcie\s*riser|extension\s*cable|"
    r"case\s*fan|rgb\s*fan|cooling\s*fan|fan\s*kit|standalone\s*fan)\b",
    re.IGNORECASE,
)


def looks_like_non_component_despite_classification(title: str) -> bool:
    """Stricter secondary check for listings already classified GEM/SUPER_GEM
    — see module comment above _GEM_JUNK_KEYWORDS for why this isn't just
    part of is_likely_accessory()."""
    return bool(_GEM_JUNK_KEYWORDS.search(_strip_scrape_artifacts(title)))


# Order matters: this is a first-match-wins scan, so a category whose
# keywords are a strict subset of another's must be checked first (e.g. a
# CPU cooler's title also contains "cooler", but plain "cooler"/"fan"/"case"
# checks would false-positive on generic accessory listings, so those two
# stay last and CPU/GPU — which require an actual model-number match, not a
# bare keyword — stay safe to check first regardless of order).
_CASE_BRAND_NAMES = r"antec|lian\s*li|fractal(?:\s*design)?|deepcool|phanteks|hyte"

_CATEGORY_KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    ("cpu", re.compile("|".join(CPU_PATTERNS), re.IGNORECASE)),
    ("gpu", re.compile("|".join(GPU_PATTERNS), re.IGNORECASE)),
    ("ram", _RAM_CATEGORY_PATTERN),
    # Checked BEFORE motherboard: Corsair's AIO cooler naming (H70, H100i,
    # H115i) collides with _MOBO_CHIPSET_PATTERN's H-series chipset shape
    # ([bhzq]\d{2,3}), which would otherwise force-categorize e.g. "Corsair
    # Hydro Series H70 Dual-Fan CPU Liquid Cooler" as "motherboard" before a
    # cooler-specific phrase ever gets a chance to match. A real motherboard
    # listing essentially never contains "AIO"/"liquid cooling"/"water
    # cooler" language itself, so this ordering costs nothing the other way.
    #
    # "water cooler"/"water cooling" is a common phrasing for AIO liquid
    # coolers that doesn't contain "aio" or "liquid cooling" literally
    # (e.g. "ARCTIC Liquid Freezer II 240 A-RGB CPU Water Cooler") — without
    # it, real AIO listings using this wording never resolved to the
    # "cooler" category at all, regardless of how good the model-extraction
    # patterns below are.
    ("cooler", re.compile(r"\b(cpu cooler|aio|air cooler|heatsink|tower cooler|liquid cool(?:ing|er))\b|water\s*cool(?:ing|er)", re.IGNORECASE)),
    # Also fires on a bare chipset code or manufacturer part number (e.g.
    # "ASUS PRIME B760M-A D4-CSM" never says "motherboard" anywhere in the
    # title) — the literal word alone missed a large fraction of real
    # motherboard listings that only ever name the board by its chipset/SKU.
    # Safe to check broadly here since cpu/gpu/ram/cooler all take priority
    # earlier in this list, so a chipset or cooler-model mention in one of
    # those listing types already resolved before reaching this check.
    (
        "motherboard",
        re.compile(
            r"\b(motherboard|mobo|mainboard)\b"
            rf"|{_MOBO_PART_NUMBER_PATTERN.pattern}"
            rf"|{_MOBO_CHIPSET_PATTERN.pattern}",
            re.IGNORECASE,
        ),
    ),
    ("ssd", re.compile(r"\b(nvme|ssd|m\.2)\b", re.IGNORECASE)),
    # "80 PLUS <tier>" is PSU-specific certification language that's commonly
    # separated from the wattage by other words ("1000w - 80 Plus Gold"), so
    # it's checked as its own independent signal rather than requiring tight
    # wattage+tier adjacency (which the pattern below still also matches).
    (
        "psu",
        re.compile(
            r"\b(psu|power supply|80\s*\+?\s*plus|\d{3,4}\s?w\s?(bronze|gold|platinum|titanium))\b",
            re.IGNORECASE,
        ),
    ),
    # Compound fan phrases checked BEFORE "case" — unambiguous (a listing
    # titled "CPU Fan"/"Case Fan"/"RGB Fan" IS the fan). The bare "fan"
    # catch-all below is deliberately checked AFTER case instead, since a
    # bare mention of "fan" is often just a case's feature blurb (e.g.
    # "CORSAIR FRAME 4000D... InfiniRail™ Fan Mounting System" is a case,
    # not a fan) — case's much more specific phrases get first refusal.
    ("fan", re.compile(r"\b(case\s*fan|rgb\s*fan|cooling\s*fan|cpu\s*fan)\b", re.IGNORECASE)),
    # Tightened from a bare "case" (which false-positived on any unrelated
    # listing mentioning a phone case, sunglasses case, soap case, etc. —
    # sampled real examples of all three) to specific PC-case phrasing, plus
    # an alternate path via known case-brand names (mirrors the Thermalright
    # brand-as-signal trick already used for coolers below).
    (
        "case",
        re.compile(
            rf"\b(pc\s*case|computer\s*case|chassis|(?:mid|full|mini)[\s-]?tower)\b"
            rf"|\b(?:{_CASE_BRAND_NAMES})\b.{{0,60}}\bcase\b|\bcase\b.{{0,60}}\b(?:{_CASE_BRAND_NAMES})\b",
            re.IGNORECASE,
        ),
    ),
    ("fan", re.compile(r"\bfan\b", re.IGNORECASE)),
]


@dataclass
class ResolvedIdentity:
    brand: Optional[str]
    model: Optional[str]
    mpn: Optional[str]
    category: Optional[str]
    exact_sku_confidence: Optional[float]


def _detect_category(title: str) -> Optional[str]:
    if is_likely_accessory(title):
        return None
    clean_title = _strip_scrape_artifacts(title)
    if _FULL_SYSTEM_KEYWORDS.search(clean_title):
        return None
    for category, pattern in _CATEGORY_KEYWORDS:
        if pattern.search(clean_title):
            return category
    return None


def _extract_ram_model(title: str) -> tuple[Optional[str], float]:
    capacity_match = _RAM_CAPACITY_PATTERN.search(title)
    ddr_match = _RAM_DDR_GEN_PATTERN.search(title)
    if not (capacity_match and ddr_match):
        return None, 0.0
    total_gb, count, per_stick_gb = capacity_match.groups()
    ddr_gen = ddr_match.group(1)
    speed_match = _RAM_SPEED_PATTERN.search(title) or _RAM_SPEED_AFTER_DDR_PATTERN.search(title)
    speed = speed_match.group(1) if speed_match else None
    cl_match = _CL_PATTERN.search(title)
    parts = [f"{total_gb}GB"]
    if count and per_stick_gb:
        parts.append(f"({count}x{per_stick_gb}GB)")
    parts.append(f"DDR{ddr_gen}")
    if speed:
        parts.append(f"{speed}MHz")
    if cl_match:
        parts.append(f"CL{cl_match.group(1)}")
    # Confidence reflects how many identity-relevant fields were captured —
    # speed and CAS latency materially affect market value for RAM.
    confidence = 0.5 + (0.15 if speed else 0) + (0.15 if cl_match else 0) + (0.1 if count else 0)
    return " ".join(parts), min(confidence, 0.9)


def _extract_ssd_model(title: str) -> tuple[Optional[str], float]:
    for pattern in SSD_PATTERNS:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            return m.group(0).strip(), 0.75
    return None, 0.0


def _extract_psu_model(title: str) -> tuple[Optional[str], float]:
    # Wattage is the load-bearing signal — without it there's nothing to
    # group same-tier PSUs by at all.
    wattage_match = _PSU_WATTAGE_PATTERN.search(title)
    if not wattage_match:
        return None, 0.0
    brand_match = _PSU_BRAND_PATTERN.search(title)
    tier_match = _PSU_TIER_PATTERN.search(title)
    parts = []
    if brand_match:
        parts.append(re.sub(r"\s+", "", brand_match.group(1)).upper())
    parts.append(f"{wattage_match.group(1)}W")
    if tier_match:
        parts.append(tier_match.group(1).upper())
    confidence = 0.4 + (0.2 if brand_match else 0) + (0.15 if tier_match else 0)
    return " ".join(parts), min(confidence, 0.75)


def _extract_motherboard_model(title: str) -> tuple[Optional[str], float]:
    # A manufacturer part number (MS-7061, GA-H110M-S2H) identifies the
    # exact board on its own — no need to walk the surrounding words.
    part_match = _MOBO_PART_NUMBER_PATTERN.search(title)
    if part_match:
        return part_match.group(0).strip(), 0.75

    chipset_match = _MOBO_CHIPSET_PATTERN.search(title)
    if not chipset_match:
        return None, 0.0

    # Walk the words following the chipset code (e.g. "B650-A" -> "Gaming
    # WiFi", "PRIME A520M-A" -> "II") to capture the rest of the board name,
    # stopping at the first word that describes the board generically
    # (form factor, socket, RAM type, ...) rather than naming it — those
    # words are the same across every board of that chipset, so including
    # them wouldn't sharpen the match and letting the walk run past them
    # risks swallowing unrelated words from later in the title.
    rest = title[chipset_match.end():].strip()
    name_parts = [chipset_match.group(0).strip()]
    for word in rest.split()[:5]:
        bare = re.sub(r"[^\w-]", "", word).lower()
        if not bare or bare in _MOBO_NAME_STOPWORDS or bare.isdigit():
            break
        name_parts.append(word.strip(",."))
    return " ".join(name_parts), 0.7


def _extract_cooler_model(title: str) -> tuple[Optional[str], float]:
    for brand_pattern, line_pattern in COOLER_PATTERNS:
        if not re.search(brand_pattern, title, re.IGNORECASE):
            continue
        m = re.search(line_pattern, title, re.IGNORECASE)
        if m:
            return m.group(0).strip(), 0.75
    return None, 0.0


def _extract_case_model(title: str) -> tuple[Optional[str], float]:
    for brand_pattern, line_pattern in CASE_PATTERNS:
        if not re.search(brand_pattern, title, re.IGNORECASE):
            continue
        m = re.search(line_pattern, title, re.IGNORECASE)
        if m:
            return m.group(0).strip(), 0.75
    return None, 0.0


def resolve_identity(title: str, delivered_price: Optional[float] = None) -> ResolvedIdentity:
    """Best-effort deterministic identity extraction. Low/zero confidence
    signals to the caller that Claude-assisted ambiguity resolution (PRD
    §29.1) may be worth the API cost for this listing — never a signal to
    invent a model number.

    delivered_price is optional and used only as a backstop against full
    systems/bundles that slip past _FULL_SYSTEM_KEYWORDS (e.g. a custom
    build sold as "Asus X870 Motherboard + Ryzen 9 + 32GB RAM, collection
    only" with no single word flagging it as "a system") — see
    _CATEGORY_PRICE_CEILING. Omit it only when price genuinely isn't known
    yet; every real caller has it available and should pass it.
    """
    clean_title = _strip_scrape_artifacts(title)
    category = _detect_category(title)
    if (
        category is not None
        and delivered_price is not None
        and delivered_price > _CATEGORY_PRICE_CEILING.get(category, float("inf"))
    ):
        category = None
    brand_match = _BRAND_PATTERN.search(clean_title)
    brand = brand_match.group(1).title() if brand_match else None

    model: Optional[str] = None
    confidence = 0.0

    if category == "cpu":
        for pattern in CPU_PATTERNS:
            m = re.search(pattern, clean_title, re.IGNORECASE)
            if m:
                model = m.group(0).strip()
                confidence = 0.75
                break
    elif category == "gpu":
        for pattern in GPU_PATTERNS:
            m = re.search(pattern, clean_title, re.IGNORECASE)
            if m:
                model = m.group(0).strip()
                confidence = 0.75
                break
    elif category == "ram":
        model, confidence = _extract_ram_model(clean_title)
    elif category == "ssd":
        model, confidence = _extract_ssd_model(clean_title)
    elif category == "motherboard":
        model, confidence = _extract_motherboard_model(clean_title)
    elif category == "cooler":
        model, confidence = _extract_cooler_model(clean_title)
    elif category == "psu":
        model, confidence = _extract_psu_model(clean_title)
    elif category == "case":
        model, confidence = _extract_case_model(clean_title)

    if model and brand:
        confidence = min(confidence + 0.1, 0.95)

    return ResolvedIdentity(
        brand=brand,
        model=model,
        mpn=None,  # MPN/EAN require item-specifics data not present in search-result cards (PRD §10.3)
        category=category,
        exact_sku_confidence=confidence if model else 0.0,
    )
