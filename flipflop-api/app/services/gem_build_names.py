"""Astronomy-inspired names for Gem sourcing build drafts."""
import secrets


ASTRONOMICAL_BUILD_NAMES = (
    "Sirius", "Vega", "Polaris", "Betelgeuse", "Rigel", "Arcturus", "Altair", "Deneb",
    "Spica", "Antares", "Procyon", "Capella", "Fomalhaut", "Aldebaran", "Castor", "Pollux",
    "Regulus", "Bellatrix", "Alnilam", "Alnitak", "Mintaka", "Mizar", "Alcor", "Enif",
    "Sadr", "Mirach", "Algol", "Orion Nebula", "Crab Nebula", "Eagle Nebula", "Lagoon Nebula",
    "Helix Nebula", "Ring Nebula", "Carina Nebula", "Horsehead Nebula", "Rosette Nebula", "Veil Nebula",
    "Io", "Europa", "Ganymede", "Callisto", "Titan", "Enceladus", "Mimas", "Rhea", "Dione",
    "Tethys", "Iapetus", "Triton", "Charon", "Phobos", "Deimos", "Oberon", "Titania", "Ariel",
    "Umbriel", "Miranda", "Cressida", "Andromeda", "Sombrero Galaxy", "Whirlpool Galaxy",
    "Pinwheel Galaxy", "Cartwheel Galaxy", "Triangulum", "Pleiades", "Hyades", "Orion", "Cygnus",
    "Lyra", "Cassiopeia", "Perseus", "Centaurus", "Carina", "Vela", "Phoenix", "Draco",
    "Aquila", "Pegasus", "Cetus", "Lupus", "Corona Borealis", "Southern Cross", "Kepler",
    "Hubble", "Voyager", "Pioneer", "Juno", "Cassini", "Galileo", "New Horizons", "Artemis",
    "Aurora", "Zenith", "Eclipse", "Solstice", "Equinox", "Celestia", "Cosmos", "Stardust",
)


def choose_gem_build_name(used_names: set[str]) -> str:
    """Choose a random unused catalogue name, with a unique fallback if exhausted."""
    used = {name.casefold() for name in used_names}
    available = [name for name in ASTRONOMICAL_BUILD_NAMES if name.casefold() not in used]
    if available:
        return secrets.choice(available)
    base = secrets.choice(ASTRONOMICAL_BUILD_NAMES)
    suffix = 2
    while f"{base} {suffix}".casefold() in used:
        suffix += 1
    return f"{base} {suffix}"
