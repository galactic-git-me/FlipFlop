"""Owner-approved pilot rules; observed business costs stay unknown."""
from copy import deepcopy
from decimal import Decimal

MINIMUM_PROFIT_MARGIN = Decimal("0.15")

APPROVED_TIER_FLOORS = {
    'Budget': ('60.00','0.15'),
    'Mid-range': ('100.00','0.15'),
    # Canonical catalogue name for the premium tier in the decision pack.
    'High-end': ('175.00','0.15'),
}
# Match the customer promise: approximately 3 working days for Fast Track and
# 5 for Standard. Supplier arrival is assessed together with workshop and
# courier time, so the procurement component must fit inside this total.
DELIVERY_CEILINGS = {'fast_track':3,'standard':5,'flexible':None}


def apply_pilot_rules(draft, tier):
    result = deepcopy(draft)
    floor = APPROVED_TIER_FLOORS.get(tier)
    result['warranty_rate'] = '0.05'
    result['returns_rate'] = '0.02'
    # Owner-confirmed 14 October 2026. Editable in each versioned cell policy.
    result['vat_rate'] = '0.00'  # Not VAT registered, not a zero-rated sale.
    # Published international GBP card rate used as a cautious pilot allowance;
    # custom account pricing, FX and non-card methods require separate review.
    result['payment_rate'] = '0.0315'
    for name,mode in result['modes'].items():
        if floor:
            mode['minimum_contribution_gbp'],mode['minimum_margin_fraction'] = floor
        mode['maximum_delivery_working_days'] = DELIVERY_CEILINGS[name]
        mode['costs'].update(build_labour='0.00', packaging='10.00',
                             insurance='15.00', payment_fixed='0.20')
        # Fast premium depends on an assessed Standard total; no invented total.
        if name != 'fast_track':
            mode['premium_gbp'] = '0.00'
    result['checkout_enabled'] = False
    return result
