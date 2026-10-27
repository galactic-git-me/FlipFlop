# Playbook tier pricing investigation - 22 October 2026

Database snapshot; prices below are proposals/estimates, not verified live sale prices. No pricing or component assignments changed during this investigation.

| User type | Budget | Mid-range | High-end |
|---|---:|---:|---:|
| Great-value Gaming | Incomplete (parts GBP 1026.87) | GBP 2896.46 | GBP 3316.57 |
| High-performance Gaming | GBP 2993.96 | GBP 3346.37 | Incomplete (parts GBP 10804.78) |
| Student Hybrid | GBP 4492.88 | GBP 2649.04 | GBP 5687.09 |
| Business & Office | GBP 2154.67 | GBP 2377.56 | GBP 4795.46 |
| Content Creation | GBP 5194.54 | GBP 6802.85 | Incomplete (parts GBP 12257.49) |
| AI Workstation | GBP 5394.04 | GBP 16737.48 | Incomplete (parts GBP 1265.11) |
| Software Development | GBP 4925.49 | GBP 5030.83 | GBP 9324.57 |
| Family & Home | GBP 2152.35 | GBP 2924.72 | GBP 6589.26 |

## Confirmed causes

- Student Hybrid: Copernicus Budget GBP 4492.88 exceeds Equinox Mid-range GBP 2649.04 by GBP 1843.84. Budget selects 128GB RAM at GBP 2199 instead of its authored 32GB LPDDR5X. Mid-range uses 32GB at GBP 499.99 in the snapshot. Current candidate inspection subsequently showed that 32GB offer at GBP 479.99, so captured prices are moving.
- RAM matching enforces minimum capacity but not the authored memory family/form factor. LPDDR5X has no token overlap with the inspected desktop kits. The shared candidate key ranks complete evidence, ETA and bestseller rank before price. The 128GB kit has a two-day ETA versus three days for cheaper 32GB kits.
- Copernicus is authored as a compact integrated-APU system but draft selection substitutes a desktop CPU, motherboard, desktop memory, case, PSU and cooler. Performance substitution is insufficient to preserve this architecture. Compatibility remains blocked.
- AI Workstation Rhode Island: GBP 16737.48 estimate includes an RTX 5090 at GBP 7499, replacing the authored Radeon AI PRO R9700, plus 128GB RAM at GBP 2199. Generic performance comparisons do not establish equivalent professional GPU capabilities.
- Enterprise High-end shows only GBP 1265.11 of partial parts. CPU, GPU, RAM, PSU and secondary storage are absent. This subtotal must never be compared with complete-PC prices.
- Several 4TB internal SSD requirements select a Crucial X10 8TB external USB SSD at GBP 819.99. Storage filtering checks minimum capacity and generic storage identity without enforcing the authored interface/internal role.
- Software Development: Budget GBP 4925.49 is only GBP 105.34 below Mid-range GBP 5030.83. Budget uses the same GBP 2199 128GB RAM kit despite an authored 64GB requirement; Mid-range uses 96GB at GBP 1118.99.
- No cross-cell ascending tier-price validation exists in the inspected assembly, estimate or quote paths. Cell-specific margin floors cannot guarantee ordered prices.

## Recommended correction

1. Preserve architecture, memory family/form factor, storage interface/internal role and workload capabilities before ranking candidates.
2. Prefer the closest adequate capacity and economically sensible landed cost among candidates that meet the required delivery commitment.
3. Validate complete comparable prices per user type: Budget < Mid-range < High-end. Flag and withhold inconsistent proposals for re-selection; do not fabricate prices or breach margin floors.
4. Keep incomplete costs visibly separate from complete-build price comparisons.
5. Rebuild proposals and repeat the tier audit before publication.
