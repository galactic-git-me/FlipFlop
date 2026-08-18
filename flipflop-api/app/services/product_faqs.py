"""Reusable customer FAQ bank and stable per-build default selection."""

from random import Random


FAQ_BANK = [
    {"id": "ready_to_use", "category": "Setup", "question": "Is the PC ready to use when it arrives?", "answer": "Yes. Windows, drivers and available updates are installed, and the completed PC is tested before dispatch. You only need to connect your display, keyboard, mouse and internet."},
    {"id": "tested", "category": "Quality", "question": "How has the PC been tested?", "answer": "The completed system is checked for startup, stability, temperatures, storage, memory and graphics operation. Any published benchmark card contains results measured on this specific build."},
    {"id": "windows", "category": "Software", "question": "Is Windows installed and activated?", "answer": "The listing specifications state the installed Windows edition. Activation status is checked before dispatch and no unlisted paid software subscription is included."},
    {"id": "wifi", "category": "Connectivity", "question": "Does it include Wi-Fi and Bluetooth?", "answer": "Check the item specifications for this build. Wi-Fi or Bluetooth is only described as included when the installed hardware supports it."},
    {"id": "upgradeable", "category": "Ownership", "question": "Can I upgrade it later?", "answer": "Yes. It uses standard desktop components wherever the specification allows. Compatibility, available slots, power requirements and case clearance should be checked before any upgrade."},
    {"id": "photos", "category": "Condition", "question": "Are the photographs of the actual PC?", "answer": "Yes. The build photographs show the actual completed machine unless an image is clearly labelled as an illustration or 3D view."},
    {"id": "component_condition", "category": "Condition", "question": "Are all of the components new?", "answer": "The exact condition is disclosed in the listing. Any component that was opened, tested or previously owned is identified rather than being represented as factory-sealed."},
    {"id": "packaging", "category": "Delivery", "question": "How is the PC packaged for delivery?", "answer": "The PC is secured with protective packaging designed to limit movement and protect the case. The buyer should remove any clearly marked internal transit protection before switching it on."},
    {"id": "delivery", "category": "Delivery", "question": "How long will delivery take?", "answer": "Ready-to-ship PCs normally have one working day handling followed by an estimated one to two working day tracked delivery window. Any different build lead time is shown before purchase."},
    {"id": "tracking", "category": "Delivery", "question": "Will I receive tracking information?", "answer": "Yes. Tracking is provided after dispatch when the courier booking has been completed."},
    {"id": "delivery_damage", "category": "Delivery", "question": "What should I do if it arrives damaged?", "answer": "Keep all packaging, photograph the parcel and PC before further handling, and contact FlipFlop promptly. Do not attempt a repair before receiving guidance."},
    {"id": "returns", "category": "Returns", "question": "Can I return the PC?", "answer": "The applicable returns period is shown with the product. For a change of mind the customer pays return postage; FlipFlop pays reasonable return costs when goods are faulty, damaged or misdescribed. Statutory rights are unaffected."},
    {"id": "warranty", "category": "Support", "question": "What warranty or consumer protection do I receive?", "answer": "UK statutory consumer rights apply. Any remaining transferable manufacturer warranty is identified with the build; no unsupported manufacturer cover is implied."},
    {"id": "support", "category": "Support", "question": "Can you help me set it up?", "answer": "Yes. Direct setup and troubleshooting support is available after purchase, including help with first connection and common configuration questions."},
    {"id": "noise", "category": "Performance", "question": "How noisy is the PC?", "answer": "Noise varies with workload, room temperature and fan settings. The system is configured for stable everyday operation, but no fixed decibel claim is made unless it has been measured and published."},
    {"id": "performance", "category": "Performance", "question": "What gaming performance should I expect?", "answer": "Use the measured results shown for this build where available. Frame rates also depend on the game, resolution, settings, updates and background software."},
    {"id": "monitor", "category": "Included", "question": "Is a monitor, keyboard or mouse included?", "answer": "Only the items explicitly listed in the included-items section and photographs are supplied. A monitor and peripherals are not assumed to be included."},
    {"id": "boxes", "category": "Included", "question": "Are the original component boxes included?", "answer": "Only packaging shown or explicitly listed is included. Large original boxes may be omitted where they cannot be shipped safely with the completed PC."},
    {"id": "customise", "category": "Buying", "question": "Can I change the specification before buying?", "answer": "Ready-to-ship machines are sold in their completed specification. For different parts, choose a Curated Build or request a Custom Build rather than altering this finished unit."},
    {"id": "collection", "category": "Delivery", "question": "Can I collect the PC?", "answer": "Collection is not available unless the individual listing explicitly says otherwise. The standard service is tracked delivery."},
]

FAQ_BY_ID = {item["id"]: item for item in FAQ_BANK}


def default_faq_ids(build_id: int, count: int = 10) -> list[str]:
    """Return a random-looking but stable selection so the UI never reshuffles."""
    ids = list(FAQ_BY_ID)
    Random(f"flipflop-faq-{build_id}").shuffle(ids)
    return ids[:count]


def selected_faqs(build_id: int, selected_ids: list[str] | None) -> list[dict]:
    ids = default_faq_ids(build_id) if selected_ids is None else selected_ids
    return [FAQ_BY_ID[item_id] for item_id in ids if item_id in FAQ_BY_ID]


def render_ebay_faq_html(items: list[dict]) -> str:
    rows = "".join(
        f'<div style="margin:0 0 10px;padding:12px;border:1px solid #d7dce2;border-radius:8px;">'
        f'<h3 style="margin:0;font-size:16px;">{item["question"]}</h3>'
        f'<p style="margin:9px 0 0;line-height:1.55;">{item["answer"]}</p></div>'
        for item in items
    )
    return (
        '<section data-flipflop-faq="true" style="margin-top:24px;">'
        '<h2 style="font-size:20px;">Frequently asked questions</h2>' + rows + "</section>"
    )
