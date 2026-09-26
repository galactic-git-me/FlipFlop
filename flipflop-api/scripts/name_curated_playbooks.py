"""Apply the Star Trek fleet naming scheme to the 24 draft playbooks."""
import json
from pathlib import Path


NAMES = {
    "FF-GVG-01": "Galileo", "FF-GVG-02": "Cerritos", "FF-GVG-03": "Voyager",
    "FF-HPG-01": "Columbus", "FF-HPG-02": "Defiant", "FF-HPG-03": "Titan",
    "FF-STU-01": "Copernicus", "FF-STU-02": "Equinox", "FF-STU-03": "Discovery",
    "FF-BOF-01": "Hawking", "FF-BOF-02": "Reliant", "FF-BOF-03": "Excelsior",
    "FF-CCR-01": "Goddard", "FF-CCR-02": "Stargazer", "FF-CCR-03": "Odyssey",
    "FF-AIW-01": "Chaffee", "FF-AIW-02": "Rhode Island", "FF-AIW-03": "Enterprise",
    "FF-SWD-01": "Sakharov", "FF-SWD-02": "Protostar", "FF-SWD-03": "Prometheus",
    "FF-FAM-01": "Cochrane", "FF-FAM-02": "Grissom", "FF-FAM-03": "Galaxy",
}


def main() -> None:
    source = Path(__file__).resolve().parents[2] / "tmp" / "curated-playbooks-v1-stub.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    playbooks = document["playbooks"]
    if {item["playbook_id"] for item in playbooks} != set(NAMES):
        raise ValueError("Draft playbook IDs differ from the naming plan")
    for item in playbooks:
        item["name"] = NAMES[item["playbook_id"]]
    naming_note = (
        "Fleet naming: Budget = shuttlecraft, Mid-range = smaller starships, "
        "High-end = major starships; Enterprise is the AI Workstation flagship."
    )
    if naming_note not in document["notes"]:
        document["notes"].append(naming_note)
    source.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Named 24 draft playbooks")


if __name__ == "__main__":
    main()
