"""Persisted customer policy copy shared by admin and the storefront."""
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from pydantic import BaseModel, ConfigDict, Field

POLICIES_PATH = Path(__file__).resolve().parents[2] / "data" / "storefront-policies.json"
POLICY_TYPES = ("delivery", "returns", "warranty", "payments", "cancellations", "faults", "delivery-damage")
BASELINE = {"policies": {
    "delivery": {"title": "Prices, postage and delivery", "content": "Displayed order prices include standard outbound postage and any delivery insurance FlipFlop chooses to purchase. Faster or customer-requested premium delivery may carry a clearly disclosed additional charge.\n\nFlipFlop remains responsible for the goods until delivered to you or your nominated recipient, subject to applicable law. Delivery estimates use current supplier, workshop and courier evidence. A date is a guarantee only when checkout explicitly says so."},
    "returns": {"title": "Change-of-mind returns", "content": "For online consumer orders, notify FlipFlop within 14 days after delivery that you wish to cancel, then return the goods within a further 14 days. Refunds are made within 14 days after the goods are returned or acceptable evidence of return is provided.\n\nStandard outbound delivery is refunded where it was separately charged. You normally pay change-of-mind return postage unless the order terms say otherwise. Any deduction for handling is limited to what the law permits. Faulty, damaged, misdescribed or incorrectly supplied goods follow statutory remedies."},
    "warranty": {"title": "FlipFlop commercial warranty", "content": "New complete FlipFlop builds include a 12-month FlipFlop warranty beginning on recorded customer delivery. This warranty is additional to your statutory rights and does not replace or shorten them.\n\nCoverage follows the complete-build terms supplied with your order, including parts and labour where stated. Flip Refresh work covers supplied parts and FlipFlop workmanship for the stated period; retained customer-owned components are not automatically covered as new components."},
    "payments": {"title": "Payment methods and third-party instalments", "content": "Checkout is processed by Stripe and displays the payment methods enabled for and eligible for your specific order. These may include cards, digital wallets, Amazon Pay and Klarna.\n\nKlarna alone decides eligibility, approval, payment schedule, interest or fees, and its applicable terms. FlipFlop does not lend or guarantee approval. Any Amazon Pay financing option is available only when Amazon Pay presents it with its terms. Approved refunds are sent to the original payment method; third-party providers control when their account and schedule reflect the refund."},
    "cancellations": {"title": "Cancellations and changes before build work", "content": "Before components are ordered, direct customers can cancel through self-service for an automatic full refund. Before components are ordered, a change request pauses sourcing and is reviewed for compatibility, timing and price before acceptance.\n\nAfter components are ordered, self-service cancellation or change closes and you should contact support. FlipFlop assesses supplier commitments, work already performed, contract terms and your statutory rights."},
    "faults": {"title": "Faults and your statutory rights", "content": "Goods must be of satisfactory quality, fit for purpose and as described. Your statutory remedies may include the short-term right to reject qualifying faulty goods within 30 days; repair or replacement where required after that period; and a price reduction or final rejection where repair or replacement fails or is not provided within a reasonable time without significant inconvenience.\n\nReasonable necessary return costs, including postage, are covered for faulty, damaged or misdescribed goods. Rights may apply for up to six years in England and Wales and five years in Scotland. This does not mean every product must last that long or that every later problem is an original fault."},
    "delivery-damage": {"title": "Delivery damage and delivery issues", "content": "If practical, photograph visible package damage before opening, retain all packaging, document product damage and contact FlipFlop promptly. For insured loss or damage, notify FlipFlop immediately, retain packaging and provide relevant photos and delivery or carrier evidence.\n\nInsurance terms govern the insurer relationship; they do not reduce your rights against FlipFlop. Please contact support promptly so we can explain the next steps for your order."},
}}

class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=30000)

class PolicySet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policies: dict[str, Policy]

def read_policies() -> dict:
    if not POLICIES_PATH.exists():
        return {"policies": {}}
    return json.loads(POLICIES_PATH.read_text(encoding="utf-8"))

def read_admin_policies() -> dict:
    """Show the documented, unpublished baseline in the editor until saved."""
    if not POLICIES_PATH.exists():
        return BASELINE
    return read_policies()

def save_policies(value: PolicySet) -> dict:
    unknown = set(value.policies) - set(POLICY_TYPES)
    if unknown:
        raise ValueError(f"Unknown policy types: {', '.join(sorted(unknown))}")
    POLICIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=POLICIES_PATH.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value.model_dump(), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(POLICIES_PATH)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return read_policies()
