# Active catalogue identity and supplier matching

Date: 2026-10-25  
Environment checked: local DEV PostgreSQL (`pcflipper`)

## Implemented

The hourly catalogue pipeline now reconciles Canonical Product Keys for active catalogue products and active listings across all hardware roles. It uses an exact ASIN identity first, then a unique existing CPK model alias, then the deterministic Gem Radar identity resolver. Remaining specific products use local Qwen only; no remote or paid tiers are called. The DEV Ollama URL now points to the working generation listener on port 11434, and local generation uses streamed responses. A provider failure cools down remaining eligible products for 24 hours; low-confidence or title-conflicting results retry after 7 days. Reconciliation does not change catalogue status, customer display price, or supplier price.

The Playbook candidate builder now reads the durable catalogue CPK. A CPK is passed to supplier matching only when its category and product identity agree with the catalogue title. Supplier offers are retained only when the exact UK retailer URL, recent observation, product family, and variant details pass the existing offer checks. The selector uses the lowest matched item cost; unknown delivery uses the existing £0 costing fallback and remains marked unverified.

The supplier data path uses recent new, buy-it-now captures from Amazon UK, Scan, Overclockers, Ebuyer, AWD-IT, and Computer Orbit. Known unavailable offers are excluded. The offer suggestion does not itself confirm stock or approve a Playbook for publication.

## DEV readback

- 3,144 catalogue variants remained active after reconciliation; the CPK job does not change variant status.
- 309 distinct products had both an active catalogue variant and an active listing.
- One additional active variant points to a `removed` listing (Kolink Observatory case); it was preserved and excluded from active product reconciliation.
- 258 products had a validated ASIN/CPK identity (83.5%). This includes 8 identities extracted by local Qwen and checked against their listing titles and catalogue roles.
- 51 products remain unresolved. Of these, 39 were withheld from model extraction because the title was too short, the role/category was ambiguous, or a hard identity conflict was present; 12 local Qwen outputs failed confidence or exact identity checks. They remain in their existing catalogue status and invalid legacy CPKs are not used by the Playbook supplier matcher.
- Local Qwen completed 20 extraction attempts; 8 were accepted. The 11435 gateway answered model-list calls but stalled on generation; DEV was switched to the generation listener on port 11434. Extraction is now streamed and local-only. The paid and remote tiers were not used for the accepted run.
- 148 active products had at least one current, identity-checked captured supplier offer in the DEV data. The captured offers included Amazon, AWD-IT, Computer Orbit, Ebuyer, Overclockers, and Scan.
- Across those 148 products, the runtime matcher accepted 245 current offer observations by identical CPK plus product identity and 27 through exact title/validated CPK identity. Those are offer observations, not unique products. Existing catalogue-price fallbacks remain separate from captured retailer offers.

A pre-change backup of existing CPK rows for active catalogue products is stored in `gem_radar_listing_cpk_catalogue_backup_20261025`.

## Remaining evidence limits

CPK and title matching identify the product; they do not prove that a supplier still has stock. Some captured offers have unknown stock or delivery, and postage remains unverified unless the source capture explicitly confirms it. The 51 unresolved identities should not be forced into supplier groups: their current evidence does not identify a single exact product safely.
