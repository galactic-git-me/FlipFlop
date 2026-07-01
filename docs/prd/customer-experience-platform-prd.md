# FlipFlopOS — Customer Experience Platform
## Product Requirements Document (Implementation-Grade)

**Document status:** Draft v1.0 — Source of Truth
**Module owner:** Product / Engineering (FlipFlopOS)
**Depends on:** Build Playbooks, Inventory, MES, Build Tracking, Benchmark Recording, Customer Portal, Profit Calculator, Reporting & Analytics
**Extends, does not replace:** All modules listed above

---

## 1. Executive Summary

The Customer Experience Platform (CXP) is a new FlipFlopOS module that governs everything that happens to a build from the moment it is marked **Ready to Package** in the Manufacturing Execution System (MES) through to the customer completing their unboxing experience.

Today, FlipFlopOS treats packaging as an operational afterthought: a build passes QA, gets boxed by whoever is free, and ships. There is no standard for what goes in the box, no enforced photography, no generated documentation beyond an ad-hoc welcome guide, and no mechanism to guarantee that two customers who bought the same Build Playbook receive a comparably premium experience.

CXP fixes this by introducing **Packaging Playbooks** — a first-class sibling concept to Build Playbooks — that deterministically define every physical item, every generated document, every photograph, and every USB file that accompanies a build. It introduces a **Procurement subsystem** to manage the supply chain for packaging materials and accessories with the same rigor FlipFlopOS already applies to PC components. It introduces a **Customer Experience Generator** that produces a suite of branded documents per order. It introduces a **Final Quality Gate** that makes premium presentation a release blocker, not a nice-to-have. And it extends the Customer Portal so that the digital experience (3D viewer, benchmark report, warranty, downloads) is published automatically and in lockstep with the physical one.

The commercial thesis is simple: unboxing experience is a profit lever, not a cost center. Businesses running on FlipFlopOS should be able to charge a premium, generate organic word-of-mouth and social content, and increase repeat-purchase rate — because the last mile of the build process was engineered as deliberately as the PC itself.

This document specifies the module to implementation depth: schema, screens, workflows, business rules, validation, notifications, permissions, APIs, acceptance criteria, and rollout plan. No source code is included; every subsequent engineering decision should be traceable to a requirement in this document.

---

## 2. Product Philosophy

Packaging is conventionally scoped as "protect the product in transit and hand over accessories." CXP rejects that framing. The unboxing sequence is a **designed emotional arc**, structurally identical to opening a flagship phone, a luxury watch, or a Porsche configurator confirmation package. The customer has already waited (build lead time creates anticipation); the box is the payoff.

Three design commitments follow from this:

1. **Every layer of the box is authored.** Nothing is generic. The carton, the void fill, the order of items lifted out, the documents, the USB, even the tape — all are specified per Packaging Playbook, not left to whoever is packing that day.

2. **The build is personalized visibly, not just administratively.** A Captain's Log with the customer's name, their specific component choices, and a QR code linking to their private 3D model and benchmark report is not the same as a generic manual. The customer should be unable to mistake this build for someone else's.

3. **The system, not the operator, is responsible for consistency.** Operators are fast and well-intentioned but inconsistent under load. Every mandatory element in this document — photography, QC checks, document generation — is enforced by workflow gating, not by training or tribal knowledge.

Every chapter below is written against the test: **does this increase the customer's excitement, confidence, and emotional attachment to the product?** Where a feature exists purely for operational convenience, it is included, but subordinate to this test whenever the two are in tension (e.g., photography is procedurally slower but is a gate, because "documented and worth sharing" beats "fast to pack").

---

## 3. Business Objectives

| # | Objective | Rationale |
|---|---|---|
| B1 | Increase average order value via premium packaging tiers | Packaging Playbooks tied to price bands justify upsell (e.g., "Flagship Showcase" tier) |
| B2 | Increase 5-star review rate and reduce review latency | Unboxing is the highest-emotion touchpoint; capturing it well drives immediate review requests |
| B3 | Generate organic social content (UGC) | Deliberately "shareable" moments (reveal sequence, branded reveal card, QR-triggered AR) increase unpaid marketing reach |
| B4 | Increase repeat purchase rate | Perceived-value delta between "PC in a box" and "premium unboxing experience" drives loyalty |
| B5 | Reduce per-order packaging cost variance | Procurement + Packaging Playbooks standardize BOM and reduce over-ordering / improvisation |
| B6 | Reduce damage-in-transit claims | Playbook-defined protection levels matched to case weight/size/value |
| B7 | Provide full cost visibility per order | Cost Engine folds packaging/consumables/labour/documents into existing Profit Calculator |
| B8 | Make the module portable across FlipFlopOS tenants | Any business running FlipFlopOS should be able to define their own Packaging Playbooks without code changes |

---

## 4. Success Metrics

| Metric | Baseline (pre-CXP) | Target (6 months post-launch) |
|---|---|---|
| % of shipped orders with complete mandatory photo set | Not tracked (assume ~40%) | 100% (hard gate) |
| Average customer review rating (unboxing-tagged) | ~4.1 / 5 | ≥ 4.6 / 5 |
| % of orders generating customer-shared social content (self-reported / tagged) | Not tracked | ≥ 15% |
| Repeat purchase rate within 12 months | Baseline TBD from Reporting module | +20% relative improvement |
| Packaging cost variance (stdev / mean) per Packaging Playbook | Not tracked (ad hoc) | < 8% |
| Time from "Ready to Package" to "Shipped" | Baseline TBD | No net increase > 15% despite added steps (automation offsets manual load) |
| Damage-in-transit claim rate | Baseline TBD | -30% relative |
| Documentation generation manual effort (minutes/order) | ~20 min manual (Word/Excel) | < 2 min (fully automated, human review only) |

Metrics B2–B4 depend on the Reporting module surfacing tagged review/order data (see Chapter 26); CXP is responsible for tagging, not for review collection infrastructure, which already exists.

---

## 5. Goals & Non-Goals

### Goals
- Define Packaging Playbooks as a first-class, versioned entity linked 1:1 from Build Playbooks.
- Provide a Procurement subsystem for packaging materials, consumables, and accessories, reusable for any future non-PC-component supply need.
- Automatically generate a document suite (Build Certificate, Captain's Log, Benchmark Report, Getting Started Guide, Upgrade Guide, Warranty Pack, QR Code Card, Welcome Letter, Accessory Checklist, USB Manifest) per order.
- Automatically build a per-order USB image containing drivers, firmware, tools, documents, and photos.
- Enforce a mandatory photography workflow during and after assembly, gating shipment.
- Integrate the existing 3D capture pipeline into the packaging and Customer Portal publish flow.
- Provide a Final Quality Gate that blocks status transition to Shipped until all mandatory checks pass.
- Extend the Cost Engine / Profit Calculator to include packaging, consumables, documentation, USB, and CX labour costs.
- Extend the Customer Portal to auto-publish the full digital companion to the physical unboxing.
- Provide reporting on packaging cost, supplier spend, consumable usage, CX cost, fulfilment time, and profitability impact.

### Non-Goals (explicitly out of scope for v1)
- Redesigning Authentication, Dashboard, Marketplace Search, Auction Analysis, Component Catalogue, Inventory core, Build Playbooks core, MES core, Build Tracking core, Benchmark Recording core, Listing Generator, Profit Calculator core, Reporting core. CXP extends these; it does not rework their existing screens or data models beyond additive foreign keys and new tables.
- Physical robotics / automated packing machinery integration.
- Real courier label generation and carrier rate shopping (Shipping Workflow in this document covers only the CXP-relevant handoff — i.e., "what accompanies the box" — not carrier selection or label printing, which remains with existing fulfilment tooling if present, or is flagged as a future integration point).
- Augmented Reality rendering itself (the 3D Workflow chapter designs for AR-readiness — asset formats, storage, QR entry point — but AR viewer implementation is a Future Enhancement).
- Multi-currency / multi-warehouse procurement (v1 assumes single UK warehouse, consistent with existing FlipFlopOS deployment assumption).
- Automated supplier EDI/API integration (v1 procurement is manual-entry with structured fields designed for future integration).

---

## 6. Architecture Overview

CXP is implemented as a new set of FastAPI routers, SQLAlchemy models, and Next.js admin/portal screens layered onto the existing FlipFlopOS monorepo (`flipflop-api`, `flipflop-admin`, `flipflop-storefront`). It introduces no new services or infrastructure components; it uses the existing Postgres database, Redis cache, and file/blob storage conventions already used by `WelcomeGuide` (PDF blob) and `OrderPhoto` (photo URL) models.

### 6.1 Module boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│ Existing: Build Playbooks ──1:1──▶ Packaging Playbooks (NEW)     │
│                                         │                        │
│                                         ▼                        │
│ Existing: MES / Build Tracking ──▶ CXP Workflow Engine (NEW)     │
│   (status: READY_TO_PACKAGE)           │                        │
│                                         ├──▶ Photography (NEW)   │
│                                         ├──▶ 3D Capture (extend) │
│                                         ├──▶ Doc Generator (NEW) │
│                                         ├──▶ USB Builder (NEW)   │
│                                         ├──▶ Procurement (NEW)   │
│                                         ├──▶ Final QC Gate (NEW) │
│                                         │                        │
│                                         ▼                        │
│                          status: SHIPPED (existing OrderStatus)  │
│                                         │                        │
│                                         ▼                        │
│                     Customer Portal (extend) ◀── Cost Engine     │
│                                                   (extend Profit │
│                                                    Calculator)   │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Backend layout (`flipflop-api`)

New router modules under `app/routers/cxp/`:
- `packaging_playbooks.py`
- `procurement.py`
- `packaging_builder.py`
- `documents.py`
- `usb_builder.py`
- `photography.py`
- `capture_3d.py` (extends existing 3D router if present)
- `quality_gate.py`
- `cxp_reporting.py`

New service modules under `app/services/cxp/`:
- `packaging_playbook_resolver.py` — resolves Build Playbook → Packaging Playbook, applies overrides
- `document_generator.py` — orchestrates per-document generators (templated PDF/HTML → PDF render)
- `usb_manifest_builder.py` — assembles file manifest, validates against USB capacity
- `photo_gate.py` — validates mandatory photo set completeness
- `qc_gate.py` — evaluates mandatory/optional QC checklist completion
- `cost_rollup.py` — aggregates packaging/consumable/labour/document/USB cost into order cost record

New model modules under `app/models/cxp/` (detailed schema in Chapter 7):
- `packaging_playbook.py`
- `packaging_component.py` (join between Packaging Playbook and Procurement Product)
- `procurement_product.py`
- `procurement_supplier.py`
- `procurement_purchase.py`
- `cx_document.py`
- `usb_manifest.py`
- `photo_requirement.py` (extends `order_photo.py`)
- `capture_3d_asset.py` (extends any existing 3D model tracking)
- `quality_gate_check.py`
- `quality_gate_result.py`
- `cx_cost_record.py`

### 6.3 Frontend layout

**`flipflop-admin`** — new nav section "Customer Experience" containing:
- Packaging Playbooks (list/detail/editor)
- Procurement (Products, Suppliers, Purchases)
- Order Packaging (per-order packaging + document + USB + photo + QC screen — the operational heart of the module)
- CX Reporting dashboards

**`flipflop-storefront`** — Customer Portal extensions:
- Build detail page gains: 3D viewer embed, benchmark report viewer, document downloads, warranty status, upgrade path CTA
- New "Order Journey" timeline component showing packaging/QC/shipping milestones (reusing existing Build Tracking timeline component pattern)

### 6.4 Data flow for a single order (happy path)

1. MES transitions `Order.status` from `QA` → `READY_TO_PACKAGE` (new status value, Chapter 27 covers state machine change).
2. CXP Workflow Engine reads `Order.playbook_id`, resolves the linked `PackagingPlaybook` via `packaging_playbook_resolver`.
3. Operator opens "Order Packaging" screen. System pre-populates:
   - Packaging BOM (from Packaging Playbook components)
   - Mandatory photo checklist (from Photography Workflow requirements)
   - Mandatory QC checklist (from Quality Gate definitions)
   - Document list to be generated
4. Operator captures/upload photos → `photo_gate` validates completeness live.
5. Operator triggers 3D capture (or system auto-triggers if integrated with existing capture rig) → asset stored, preview generated.
6. System auto-generates documents on demand or on a "Generate All" action → PDFs rendered, stored, versioned.
7. System auto-builds USB manifest → validates against configured USB capacity → operator confirms USB written (or system flags "digital-only" fallback, Chapter 19).
8. Operator completes QC checklist with evidence (photo/signature/timestamp per check).
9. `qc_gate` + `photo_gate` both report "PASS" → `Order.status` transition to `READY_TO_SHIP` unlocked.
10. On ship confirmation, `Order.status` → `SHIPPED`; Customer Portal publish job fires; Cost Engine rollup fires; notification to customer fires.

---

## 7. Database Design

All new tables use the existing `Base` declarative pattern (see `app/database.py`), `datetime.utcnow` default timestamps, and `Enum` columns for status fields, consistent with existing models (`Order`, `Playbook`, `OrderPhoto`).

### 7.1 `packaging_playbooks`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| name | String, unique, indexed | e.g. "Flagship Showcase" |
| slug | String, unique, indexed | URL/API-safe identifier |
| version | Integer, default 1 | incremented on each published change |
| status | Enum(`DRAFT`, `ACTIVE`, `DEPRECATED`) | only one ACTIVE version per slug lineage at a time |
| description | Text, nullable | internal notes on intent/tier |
| carton_spec | JSON | dimensions, weight rating, supplier product ref |
| protection_spec | JSON | Instapak qty, inflatable bags, bubble wrap, corner protectors — structured list of `{procurement_product_id, quantity}` |
| void_fill_spec | JSON | same structure as protection_spec |
| security_spec | JSON | tape type/qty, tamper-evident seal flag |
| label_spec | JSON | fragile label, this-way-up label, custom branding sticker refs |
| documentation_pack | JSON | ordered list of `cx_document` type codes to generate/include |
| captains_log_spec | JSON | section list + tone/template ref (Chapter 18) |
| usb_content_spec | JSON | reference to USB template (Chapter 19) |
| welcome_gifts | JSON | list of `{procurement_product_id, quantity}`, optional |
| accessories | JSON | list of `{procurement_product_id, quantity}` |
| premium_extras | JSON | list of `{procurement_product_id, quantity}`, tier-gated |
| presentation_order | JSON | ordered array describing lift-out sequence (Chapter 16) |
| unboxing_sequence | JSON | narrative script reference used by Captain's Log / welcome letter tone |
| estimated_cost | Float, computed & cached | recalculated on save from component costs |
| created_by | Integer, FK → users.id | |
| created_at / updated_at | DateTime | |

Relationships: `orders` (via `Order.packaging_playbook_id`), `build_playbooks` (via `Playbook.packaging_playbook_id`), `packaging_components` (1:many join to procurement products for reporting granularity beyond the JSON spec — see 7.3).

### 7.2 `packaging_playbook_versions`

Append-only version history table (mirrors common audit pattern). Stores full JSON snapshot of a `packaging_playbooks` row at time of publish, `changed_by`, `changed_at`, `change_note`. Enables clone-from-version and rollback.

### 7.3 `packaging_playbook_components`

Normalizes the JSON BOM fields into queryable rows for cost/reporting joins (the JSON columns in 7.1 remain the authoring/editing source of truth for the builder UI; this table is derived on save for reporting performance).

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| packaging_playbook_id | FK | |
| category | Enum(`CARTON`, `PROTECTION`, `VOID_FILL`, `SECURITY`, `LABEL`, `GIFT`, `ACCESSORY`, `PREMIUM_EXTRA`) | |
| procurement_product_id | FK → procurement_products.id | |
| quantity | Integer | |
| unit_cost_snapshot | Float | cost at time of playbook save, for historical cost accuracy |

### 7.4 `procurement_suppliers`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| name | String, indexed | |
| contact_name | String, nullable | |
| contact_email | String, nullable | |
| contact_phone | String, nullable | |
| website | String, nullable | |
| notes | Text, nullable | |
| lead_time_days | Integer, default 0 | |
| shipping_cost | Float, default 0 | flat-rate assumption v1 |
| uk_warehouse | Boolean, default false | affects lead-time display/urgency badges |
| is_preferred | Boolean, default false | one preferred supplier per product enforced at app layer |
| created_at / updated_at | DateTime | |

### 7.5 `procurement_products`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| name | String, indexed | e.g. "Instapak Foam Sheet 400x600mm" |
| sku | String, unique, nullable | internal SKU if assigned |
| category | Enum (same as 7.3 category enum, reused) | |
| unit_of_measure | String | e.g. "each", "roll", "sheet" |
| unit_cost | Float | current effective cost |
| preferred_supplier_id | FK → procurement_suppliers.id, nullable | |
| purchase_url | String, nullable | |
| min_stock_level | Integer, default 0 | |
| reorder_level | Integer, default 0 | |
| current_stock | Integer, default 0 | reservation-aware (see 7.7) |
| active | Boolean, default true | soft-disable without deleting history |
| created_at / updated_at | DateTime | |

### 7.6 `procurement_product_suppliers`

Many-to-many join enabling "alternative suppliers" per product.

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| procurement_product_id | FK | |
| supplier_id | FK | |
| supplier_sku | String, nullable | |
| unit_cost | Float | supplier-specific price, may differ from `procurement_products.unit_cost` (which reflects preferred/effective) |
| lead_time_days_override | Integer, nullable | |

### 7.7 `procurement_purchases`

Purchase history / stock-in ledger.

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| procurement_product_id | FK | |
| supplier_id | FK | |
| quantity | Integer | |
| unit_cost_paid | Float | |
| total_cost | Float, computed | |
| purchase_date | DateTime | |
| received_date | DateTime, nullable | |
| reference | String, nullable | PO number / invoice ref |
| created_by | FK → users.id | |

### 7.8 `procurement_reservations`

Tracks stock committed to a specific order's packaging BOM before consumption, mirroring the existing `inventory_allocation.py` pattern used for components.

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| procurement_product_id | FK | |
| order_id | FK → orders.id | |
| quantity_reserved | Integer | |
| status | Enum(`RESERVED`, `CONSUMED`, `RELEASED`) | |
| created_at / updated_at | DateTime | |

### 7.9 `cx_documents`

One row per generated document instance (not per type — a type may regenerate, creating a new version row).

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id, indexed | |
| document_type | Enum(`BUILD_CERTIFICATE`, `CAPTAINS_LOG`, `BENCHMARK_REPORT`, `GETTING_STARTED_GUIDE`, `UPGRADE_GUIDE`, `WARRANTY_PACK`, `QR_CODE_CARD`, `WELCOME_LETTER`, `ACCESSORY_CHECKLIST`, `USB_MANIFEST`) | |
| version | Integer, default 1 | |
| status | Enum(`GENERATING`, `READY`, `FAILED`, `SUPERSEDED`) | |
| template_id | FK → cx_document_templates.id | |
| pdf_blob | LargeBinary, nullable | consistent with `WelcomeGuide.pdf_blob` pattern |
| pdf_url | String, nullable | if blob storage migrates to object storage later |
| content_json | JSON, nullable | structured content snapshot for re-render/debug |
| generated_at | DateTime, nullable | |
| generated_by | Enum(`SYSTEM`, `OPERATOR`) | |
| created_at / updated_at | DateTime | |

### 7.10 `cx_document_templates`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| document_type | Enum (same as 7.9) | |
| name | String | e.g. "Flagship Captain's Log v2" |
| version | Integer | |
| status | Enum(`DRAFT`, `ACTIVE`, `DEPRECATED`) | |
| layout_spec | JSON | section list, branding refs, tone/copy variables |
| created_at / updated_at | DateTime | |

### 7.11 `usb_manifests`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id, unique | one manifest per order |
| template_id | FK → usb_templates.id | |
| status | Enum(`PENDING`, `BUILT`, `VALIDATED`, `WRITTEN_TO_MEDIA`, `FAILED`, `DIGITAL_FALLBACK`) | |
| total_size_bytes | BigInteger | |
| capacity_bytes | BigInteger | from associated USB hardware SKU (procurement product) |
| file_manifest_json | JSON | ordered list of `{category, filename, source_ref, size_bytes}` |
| built_at | DateTime, nullable | |
| written_at | DateTime, nullable | operator confirmation timestamp |
| written_by | FK → users.id, nullable | |
| created_at / updated_at | DateTime | |

### 7.12 `usb_templates`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| name | String | |
| linked_playbook_id | FK → playbooks.id, nullable | driver/BIOS/RGB-software selection can be Build-Playbook-specific |
| content_categories | JSON | which categories to include (drivers, BIOS, firmware, recovery tools, manuals, RGB software, benchmarks, wallpapers, utilities, warranty, customer documents, build photographs) |
| static_file_refs | JSON | list of file storage refs for non-order-specific content (driver packages, manuals) |
| created_at / updated_at | DateTime | |

### 7.13 `order_photos` (extend existing)

Existing table (Chapter 6.1 excerpt above) already supports `order_id`, `stage`, `photo_url`, `notes`. CXP adds:

| New column | Type | Notes |
|---|---|---|
| requirement_id | FK → photo_requirements.id, nullable | links photo to the mandatory/optional requirement it satisfies |
| photo_type | Enum(`ASSEMBLY`, `COMPLETION`, `PACKAGING`, `FINAL_BOXED`) | supersedes free-text `stage` for gating logic while keeping `stage` for backward-compat display |
| captured_by | FK → users.id, nullable | |
| is_hero_shot | Boolean, default false | flags "glamour shot" candidates for Customer Portal hero image and social sharing kit |

### 7.14 `photo_requirements`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| packaging_playbook_id | FK, nullable | null = global requirement applying to all playbooks |
| photo_type | Enum (same as 7.13) | |
| label | String | e.g. "Empty case", "Front — completed build" |
| is_mandatory | Boolean, default true | |
| sort_order | Integer | controls checklist display order |
| active | Boolean, default true | |

Seed data (Chapter 20) populates the global mandatory set; Packaging Playbooks may add playbook-specific additional requirements (e.g., "Flagship Showcase" adds a mandatory turntable video-frame capture).

### 7.15 `capture_3d_assets` (extends existing 3D pipeline, if a table already exists it is extended in place; otherwise created net-new following this spec)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id, unique | |
| status | Enum(`PENDING`, `CAPTURED`, `OPTIMIZING`, `OPTIMIZED`, `PUBLISHED`, `FAILED`) | |
| raw_asset_ref | String, nullable | storage ref to raw scan/capture output |
| optimized_asset_ref | String, nullable | web-viewer-ready format (e.g. glTF/GLB) |
| preview_image_ref | String, nullable | static fallback thumbnail |
| ar_ready | Boolean, default false | flags assets meeting future-AR technical spec (poly count, texture size ceilings) — see Chapter 21 |
| captured_at / optimized_at / published_at | DateTime, nullable | |
| created_at / updated_at | DateTime | |

### 7.16 `quality_gate_checks` (definitions)

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| packaging_playbook_id | FK, nullable | null = global check |
| code | String, unique | e.g. `QC_CABLE_MGMT`, `QC_RGB_SYNC`, `QC_BURN_IN_PASS` |
| label | String | |
| description | Text, nullable | |
| is_mandatory | Boolean, default true | |
| requires_evidence | Enum(`NONE`, `PHOTO`, `SIGNATURE`, `PHOTO_AND_SIGNATURE`) | |
| sort_order | Integer | |
| active | Boolean, default true | |

### 7.17 `quality_gate_results`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id | |
| check_id | FK → quality_gate_checks.id | |
| passed | Boolean, nullable | null = not yet evaluated |
| evidence_photo_url | String, nullable | |
| evidence_signature_ref | String, nullable | |
| performed_by | FK → users.id, nullable | |
| performed_at | DateTime, nullable | |
| notes | Text, nullable | |
| created_at / updated_at | DateTime | |

Unique constraint on (`order_id`, `check_id`).

### 7.18 `cx_cost_records`

| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| order_id | FK → orders.id, unique | |
| packaging_cost | Float | rolled up from `packaging_playbook_components` snapshot costs |
| consumables_cost | Float | |
| accessories_cost | Float | |
| documentation_cost | Float | printing/material cost if physical docs printed, else 0 |
| usb_cost | Float | USB stick unit cost from procurement |
| shipping_handling_cost | Float | carton + protection weight-derived if available, else flat rate from Packaging Playbook |
| labour_cost | Float | packaging/QC time × labour rate, reusing `Order.labor_rate` pattern |
| total_cx_cost | Float, computed | sum of above |
| computed_at | DateTime | |
| created_at / updated_at | DateTime | |

Feeds into existing Profit Calculator by being added as a cost line alongside `Order.component_costs` and `Order.overhead_amount`.

### 7.19 Extensions to existing tables

- `playbooks.packaging_playbook_id` → FK → `packaging_playbooks.id`, nullable at DB level but enforced non-null at application layer for any playbook with `status = ACTIVE` (Chapter 27, Business Rule BR-1).
- `orders.packaging_playbook_id` → FK, nullable, snapshot of the resolved playbook at order-packaging time (may differ from the current Build Playbook's linked playbook if an override was applied, or if the Build Playbook's linked playbook changed after the order was placed).
- `orders.status` (Enum `OrderStatus`) gains new values: `READY_TO_PACKAGE`, `PACKAGING_IN_PROGRESS` inserted between existing `QA` and `READY_TO_SHIP`. See Chapter 27 for full state machine.

---

## 8. Entity Relationship Model

```
Playbook (existing) ──1:1──▶ PackagingPlaybook
PackagingPlaybook ──1:many──▶ PackagingPlaybookComponent ──many:1──▶ ProcurementProduct
PackagingPlaybook ──1:many──▶ PackagingPlaybookVersion (audit trail)
PackagingPlaybook ──1:many──▶ PhotoRequirement (playbook-specific additions)
PackagingPlaybook ──1:many──▶ QualityGateCheck (playbook-specific additions)

ProcurementProduct ──many:many──▶ ProcurementSupplier (via ProcurementProductSupplier)
ProcurementProduct ──1:many──▶ ProcurementPurchase
ProcurementProduct ──1:many──▶ ProcurementReservation ──many:1──▶ Order

Order (existing) ──many:1──▶ PackagingPlaybook (snapshot reference)
Order ──1:many──▶ OrderPhoto (extended) ──many:1──▶ PhotoRequirement
Order ──1:1──▶ Capture3DAsset
Order ──1:many──▶ CXDocument ──many:1──▶ CXDocumentTemplate
Order ──1:1──▶ USBManifest ──many:1──▶ USBTemplate
Order ──1:many──▶ QualityGateResult ──many:1──▶ QualityGateCheck
Order ──1:1──▶ CXCostRecord
Order ──1:1──▶ WelcomeGuide (existing, now one of the CXDocument types generated via unified pipeline — see Chapter 18 migration note)
```

---

## 9. Navigation Changes

### 9.1 `flipflop-admin` sidebar

New top-level nav group **"Customer Experience"** (positioned between "Build Tracking" and "Reporting & Analytics" in the existing nav order), containing:

- **Order Packaging** — the primary operational screen; badge shows count of orders in `READY_TO_PACKAGE` / `PACKAGING_IN_PROGRESS`
- **Packaging Playbooks** — list/editor
- **Procurement**
  - Products
  - Suppliers
  - Purchase History
- **Document Templates** — manage `cx_document_templates`
- **USB Templates**
- **CX Reporting** — sub-nav under existing Reporting & Analytics section instead, per objective of avoiding duplicate top-level reporting entry points (cross-reference Chapter 26)

### 9.2 Existing Build Tracking screen

Add a "Packaging Status" column/badge to the existing Build Tracking board (Kanban-style, presumed existing pattern) reflecting `READY_TO_PACKAGE`, `PACKAGING_IN_PROGRESS`, photo/QC gate completion percentage.

### 9.3 Build Playbook editor (existing)

Add a required field: "Linked Packaging Playbook" (dropdown, searchable) to the existing Build Playbook create/edit screen. Cannot save/activate a Build Playbook without this field set (Business Rule BR-1).

### 9.4 `flipflop-storefront` Customer Portal

Existing per-order/build detail page gains new tab or section: **"Your Build Journey"** containing:
- Order Journey timeline (packaging → QC → shipped milestones)
- 3D Viewer embed
- Benchmark Report viewer
- Document downloads (Warranty Pack, Getting Started Guide, Upgrade Guide)
- "Share your unboxing" CTA (deep link to social share kit, Chapter 25)

---

## 10. Screen Specifications

### 10.1 Order Packaging screen (`/admin/cxp/orders/:orderId`)

**Purpose:** Single operational surface for an operator to move one order from `READY_TO_PACKAGE` through to `READY_TO_SHIP`.

**Layout regions:**

1. **Header bar:** Order ID, customer name, Build Playbook name, linked Packaging Playbook name (with "Override" link), current status badge, overall gate progress ring (photo % / QC % / documents % / USB %).

2. **Packaging BOM panel:** Read-only list of the resolved Packaging Playbook's components (carton, protection, void fill, security, labels, gifts, accessories, premium extras) with quantities and live stock availability indicator (green/amber/red from `ProcurementProduct.current_stock` minus reservations). "Reserve stock" action creates `ProcurementReservation` rows.

3. **Photography panel:** Checklist of `PhotoRequirement` rows (grouped by `photo_type`: Assembly, Completion, Packaging, Final Boxed). Each row: label, mandatory/optional badge, upload control (drag-drop or capture-from-device), thumbnail once uploaded, "mark as hero shot" toggle. Progress bar: "12 / 14 mandatory photos captured."

4. **3D Capture panel:** Status of `Capture3DAsset` (Pending/Captured/Optimizing/Optimized/Published), "Trigger Capture" button (integration hook to existing capture rig/process), preview embed once optimized.

5. **Documents panel:** List of all `cx_document_type` rows for this order with status (Not generated / Generating / Ready / Failed), "Generate" / "Regenerate" per-document action, "Generate All" bulk action, preview/download link per ready document.

6. **USB Builder panel:** Manifest status, file list preview (categorized), total size vs. capacity bar, "Build Manifest" action, "Confirm Written to Media" checkbox (operator physically writes and confirms) or "Use Digital Fallback" toggle (Chapter 19.4).

7. **Final Quality Gate panel:** Checklist of `QualityGateCheck` rows with evidence capture inline (photo upload / signature pad / both, per `requires_evidence`). Each row shows pass/fail toggle, performed_by, timestamp once completed.

8. **Footer action bar:** "Save Progress" (always available), "Mark Ready to Ship" (disabled/greyed with tooltip explaining exactly which gates are incomplete, until all mandatory photo + QC + document + USB gates pass), "Mark Shipped" (only enabled once status is `READY_TO_SHIP` and a shipping confirmation, e.g., tracking number, is entered).

**States:** Loading, populated, saving (per-panel optimistic save with error rollback), gate-blocked (footer CTA disabled with explanatory tooltip listing outstanding items), complete.

### 10.2 Packaging Playbooks list (`/admin/cxp/playbooks`)

Table columns: Name, Slug, Version, Status (Draft/Active/Deprecated), Linked Build Playbooks count, Estimated Cost, Last Updated. Row actions: Edit, Clone, View Version History, Deprecate. "New Packaging Playbook" primary action.

### 10.3 Packaging Playbook editor (`/admin/cxp/playbooks/:id/edit`)

Tabbed editor:
- **Basics:** name, slug, description, status
- **Protection & Carton:** carton spec fields, protection spec builder (add/remove `{procurement_product, quantity}` rows with typeahead product search), void fill, security, labels
- **Documents & Log:** documentation pack ordered list (drag to reorder), Captain's Log section builder, welcome letter template link
- **USB:** linked USB template
- **Gifts & Extras:** welcome gifts, accessories, premium extras builders (same row-builder pattern as protection)
- **Presentation:** presentation order (drag-and-drop lift-out sequence editor — a simple ordered list with icons representing each item type), unboxing sequence narrative notes
- **Cost Summary:** live-computed estimated cost breakdown by category, refreshed on every BOM change
- **Save behavior:** Save as Draft (no version bump) vs. Publish (bumps version, snapshots to `packaging_playbook_versions`, becomes the ACTIVE version, prior ACTIVE version transitions to DEPRECATED)

### 10.4 Procurement — Products (`/admin/cxp/procurement/products`)

Table with filters (category, active/inactive, low-stock flag). Row actions: Edit, View Purchase History, Deactivate. Detail/edit drawer: name, SKU, category, unit of measure, unit cost, preferred supplier, purchase URL, min stock, reorder level, current stock (read-only, derived from purchases minus reservations/consumption), alternative suppliers sub-table.

### 10.5 Procurement — Suppliers (`/admin/cxp/procurement/suppliers`)

Table: Name, Contact, Lead Time, UK Warehouse (badge), Preferred-for (count of products), Last Purchase Date. Edit drawer: all fields from 7.4, plus read-only "Products supplied" list.

### 10.6 Procurement — Purchase History (`/admin/cxp/procurement/purchases`)

Filterable ledger table (by product, supplier, date range). "Record Purchase" action opens form: product (typeahead), supplier, quantity, unit cost paid, purchase date, reference. On save, increments `current_stock` (via derived calculation, not a stored mutable field, to avoid drift — see Business Rule BR-7).

### 10.7 Document Templates (`/admin/cxp/cxp-documents/templates`)

List by document type + version + status. Editor is a structured form (section list builder) rather than free-form HTML in v1, per Non-Goal scoping — full WYSIWYG template design is a Future Enhancement (Chapter 35).

### 10.8 USB Templates (`/admin/cxp/usb-templates`)

List + editor: name, linked Build Playbook (optional), content category checkboxes, static file reference manager (upload/link driver packages, manuals — these are shared across orders, not regenerated per-order).

### 10.9 CX Reporting dashboards (`/admin/reporting/customer-experience`)

See Chapter 26 for full metric list. Screen presents filterable date-range dashboards with chart + table views consistent with existing Reporting & Analytics screen patterns.

### 10.10 Customer Portal — "Your Build Journey" (storefront)

Public-but-authenticated (customer-scoped) page section:
- Timeline component (reuses existing Build Tracking visual pattern, customer-facing simplified version): Order Placed → Sourcing → Building → QA → Packaging → Shipped → Delivered
- 3D viewer (embed `Capture3DAsset.optimized_asset_ref`)
- Benchmark report (renders `CXDocument` of type `BENCHMARK_REPORT`, or links PDF)
- Downloads section: Warranty Pack, Getting Started Guide, Upgrade Guide (PDF links)
- Share kit CTA

---

## 11. User Stories

**Operator (Packing Technician)**
- As an operator, I want the correct packaging BOM to appear automatically when I open an order, so I don't have to remember which materials go with which build tier.
- As an operator, I want the system to block me from marking an order "Ready to Ship" if I've missed a mandatory photo, so quality is enforced without me needing to self-audit.
- As an operator, I want to see live stock levels for packaging materials so I don't start packing an order I can't complete.
- As an operator, I want to generate all customer documents with one click so I don't manually assemble PDFs.

**Operations Manager**
- As an operations manager, I want to define a new Packaging Playbook and link it to a Build Playbook so that new product tiers automatically get the right premium treatment.
- As an operations manager, I want to see packaging cost variance by playbook so I can catch material waste or supplier price drift.
- As an operations manager, I want to configure mandatory QC checks per playbook so higher-tier builds get additional scrutiny (e.g., burn-in test evidence) without slowing down budget-tier throughput.

**Procurement Coordinator**
- As a procurement coordinator, I want to record purchases against a product/supplier so stock levels and purchase history stay accurate.
- As a procurement coordinator, I want to be alerted when a packaging product falls below its reorder level so I don't run out mid-fulfilment.
- As a procurement coordinator, I want to compare suppliers for the same product so I can switch to a cheaper or faster alternative.

**Customer**
- As a customer, I want to receive a personalized Captain's Log with my exact build spec so I feel the machine was made specifically for me.
- As a customer, I want to scan a QR code on my box and immediately see a 3D model of my exact PC and its benchmark results, so I have something impressive to show friends.
- As a customer, I want my warranty and getting-started documentation available digitally at any time, so I don't need to keep a physical booklet.
- As a customer, I want an easy, guided way to share my unboxing on social media, so I can show off my new PC.

**Business Owner (multi-tenant FlipFlopOS operator)**
- As a business owner, I want to define my own packaging tiers and documents so my brand identity carries through the unboxing experience without needing custom engineering work.
- As a business owner, I want full cost visibility on packaging/CX spend per order so I can price my products correctly and protect margin.

---

## 12. Personas

**Priya — Packing Technician.** Works the fulfilment floor, packs 15-25 orders/day across build tiers. Time-pressured, moderately tech-comfortable, values clear checklists over dense documentation. Needs the system to tell her exactly what's missing, in-flow, without hunting through menus.

**Marcus — Operations Manager.** Owns the fulfilment process end-to-end, accountable for damage claims, cost variance, and customer satisfaction scores. Wants dashboards, not manual audits. Will be the primary author of Packaging Playbooks and QC checklists.

**Dana — Procurement Coordinator.** Part-time role alongside general admin duties. Needs simple, form-driven workflows (not a full ERP) — she is not a supply-chain specialist and the system should not assume that expertise.

**Alex — Customer.** Ordered a premium gaming PC, has waited 8 days for the build. High anticipation at delivery. Wants the unboxing to feel like an event. Will photograph/film if the experience earns it; will leave a mediocre review if the box feels like "just a computer."

**Sam — FlipFlopOS Business Owner (Tenant Admin).** Runs a PC-flipping business on FlipFlopOS, distinct from the FlipFlopOS platform team. Needs to configure the module to reflect their own brand without engineering support.

---

## 13. Packaging Playbooks

(Schema defined in Chapter 7.1–7.3; screens in 10.2–10.3.) This chapter specifies the **behavioral and business logic** layer.

### 13.1 Resolution logic

`packaging_playbook_resolver.resolve(order)`:
1. Look up `order.build_playbook_id` → `Playbook.packaging_playbook_id`.
2. If an operator-applied override exists for this specific order (`Order.packaging_playbook_override_id`, new nullable FK — added alongside `packaging_playbook_id`), use the override instead.
3. Snapshot the resolved playbook's **current ACTIVE version** into `Order.packaging_playbook_id` at the moment the order first enters `READY_TO_PACKAGE`. This snapshot does not change even if the Packaging Playbook is later edited/republished, ensuring cost and BOM integrity for orders already in flight (Business Rule BR-2).

### 13.2 Versioning & cloning

- Editing an ACTIVE playbook creates a Draft copy (does not mutate the live version) unless the operator explicitly chooses "Edit Live" for typo-level fixes with no BOM/cost impact (guarded by a confirmation modal warning about in-flight order impact).
- "Clone" always creates a new Draft with a new name/slug, fully decoupled — used for deriving e.g. "Flagship Showcase — Christmas Edition" from "Flagship Showcase."
- Publishing a Draft: validates all required fields are non-empty (carton spec, at least one protection item, at least one documentation pack entry), snapshots to `packaging_playbook_versions`, sets prior ACTIVE to DEPRECATED, sets new version to ACTIVE, increments `version`.

### 13.3 Defaults & overrides

- System ships with seed Packaging Playbooks matching the example tiers named in this document's source brief (Budget Gaming, Premium RGB, Creator Workstation, Silent Workstation, Flagship Showcase, Collector's Edition) as starting templates — tenants are expected to customize.
- Every Build Playbook must have exactly one linked Packaging Playbook (Business Rule BR-1) — no build ships without a defined premium treatment, however minimal for budget tiers.
- Per-order override is permitted (e.g., customer pays for a gift upgrade) and is fully audit-logged (who overrode, when, from what to what).

### 13.4 Cost calculation

`estimated_cost` on the playbook = sum of `(procurement_product.unit_cost × quantity)` across all BOM categories, computed on every save and cached for fast list-screen display. The authoritative per-order cost is computed at packaging time by `cost_rollup` using cost snapshots (7.3 `unit_cost_snapshot`), not live product costs, so historical order cost accuracy is preserved even if supplier prices change later.

---

## 14. Procurement

(Schema in 7.4–7.8; screens in 10.4–10.6.)

### 14.1 Stock model

`current_stock` is **derived, not stored as a freely-mutable field**: it equals `SUM(procurement_purchases.quantity WHERE received_date IS NOT NULL) − SUM(procurement_reservations.quantity_reserved WHERE status IN ('RESERVED','CONSUMED'))`. This is computed on read (with Redis caching, TTL 60s, invalidated on purchase/reservation writes) to prevent drift between a stored counter and ledger reality — a common source of inventory bugs (Business Rule BR-7).

### 14.2 Reservation lifecycle

- `RESERVED`: created when an operator opens the Order Packaging screen's BOM panel and clicks "Reserve stock" (or automatically on order entering `READY_TO_PACKAGE`, configurable per-tenant setting — default: automatic).
- `CONSUMED`: transitions automatically when the order reaches `SHIPPED`.
- `RELEASED`: manual action if an order is cancelled or a packaging component is swapped before shipment; releases stock back to availability.

### 14.3 Low-stock alerting

When `current_stock <= reorder_level` for any active product, a notification fires (Chapter 29) to users with the Procurement Coordinator role, and the product row displays an amber/red badge on the Products list screen. This check runs as a scheduled job (reusing the existing APScheduler-based worker pattern already present in the codebase, e.g., `app/workers/scheduler.py`) every 15 minutes, plus is recalculated synchronously whenever a reservation is created against that product.

### 14.4 Alternative suppliers

The Products edit screen surfaces all rows from `procurement_product_suppliers` for the product, sorted by `unit_cost` ascending, with the preferred supplier flagged. Switching preferred supplier is a one-click action that updates `procurement_products.preferred_supplier_id` and `unit_cost` to match the newly preferred entry (with a confirmation showing the cost delta).

### 14.5 Future integration seam

Every `ProcurementSupplier` row has a reserved (nullable, currently unused) `integration_config` JSON column intended for future EDI/API auto-ordering integrations — included now to avoid a breaking schema migration later, but not implemented or exposed in any v1 UI (Future Enhancement, Chapter 35).

---

## 15. Inventory Integration

CXP's Procurement subsystem is deliberately **parallel to, not merged with**, the existing PC-component Inventory module — components (CPUs, GPUs, RAM) and packaging/consumables have different lifecycles (components are sourced per-build from marketplace listings via Marketplace Search/Auction Analysis; packaging materials are bulk-purchased consumables). However, three integration points are required:

1. **Shared cost rollup:** `CXCostRecord` (7.18) sits alongside `Order.component_costs` in the Profit Calculator's total cost computation — both flow into the same `Order.profit` calculation, just from different subsystems.
2. **Shared reservation pattern:** `ProcurementReservation` mirrors the existing `inventory_allocation` table's status enum and lifecycle exactly, so any future unified "what's committed to Order X" reporting view can UNION both tables with consistent semantics.
3. **Shared low-stock alerting infrastructure:** reuse the existing `alert_event.py` model/notification pipeline (evidenced by the presence of `app/models/alert_event.py`) rather than building a second alerting mechanism.

No component data is duplicated into Procurement tables, and no packaging data is duplicated into Inventory tables — the two remain cleanly separated at the schema level, joined only at the Order and cost-reporting layer.

---

## 16. Packaging Builder

The "Packaging Builder" is the authoring experience within the Packaging Playbook editor (Chapter 10.3) responsible for the BOM and — critically — the **presentation order**, which is the single highest-leverage lever for emotional impact.

### 16.1 Presentation order model

`presentation_order` (JSON array on `packaging_playbooks`) is an ordered list of steps, each `{step_type, item_ref, reveal_note}`, where `step_type` is one of: `OUTER_UNBOX`, `TOP_DOCUMENT`, `ACCESSORY_LAYER`, `PROTECTIVE_LAYER_REMOVE`, `HERO_REVEAL`, `GIFT_REVEAL`, `FINAL_ITEM`.

Rationale: the single biggest difference between "a PC arrived in a box" and "a Porsche-configurator-grade reveal" is **sequencing** — what the customer sees first, second, and last. A Welcome Letter sitting on top (not buried under foam) that says "Hi Alex, here's your Titan Ridge build — here's what to expect when you open this box" primes the entire experience before a single component is visible. The Packaging Builder makes this sequence an explicit, editable, versioned artifact rather than an unwritten habit of whichever technician packs the order.

### 16.2 Builder UX

Drag-and-drop ordered list, each item showing an icon (document/gift/accessory/protective-layer/hero) and a short editable "reveal note" — an internal instruction to the packer describing intent (e.g., "Place folded on top, logo facing up, before any foam"). This is not customer-visible copy; it is operator guidance ensuring presentation fidelity regardless of who packs the order.

### 16.3 Cost-vs-presentation trade-off surfacing

The builder's live cost summary (13.4) is shown alongside the presentation order editor so that Operations Managers can see immediately when an addition (e.g., a branded welcome gift) pushes a tier over its target margin — supporting Business Objective B7 (cost visibility) without requiring a separate screen round-trip.

---

## 17. Customer Experience Generator

This is the orchestration service (`document_generator.py`) responsible for producing the full document suite. It does not own layout logic per-document (each document type's layout lives in Chapter 18); it owns **sequencing, dependency resolution, and failure handling** across the whole suite.

### 17.1 Generation triggers

- **Automatic:** fires when `Order.status` enters `READY_TO_PACKAGE`, generating all documents whose `document_type` is present in the resolved Packaging Playbook's `documentation_pack` list, using each type's currently-ACTIVE `cx_document_template`.
- **Manual (Regenerate):** operator-triggered from the Order Packaging screen if underlying data changed (e.g., a component swap occurred after initial generation) or the customer's name was corrected.
- **Manual (Generate All):** convenience bulk action for cases where automatic generation was skipped or failed.

### 17.2 Dependency resolution

Some documents depend on other CXP artifacts existing first:
- `BENCHMARK_REPORT` depends on Benchmark Recording module data being present for this order (existing module) — generation is blocked with a clear error state ("Waiting on benchmark data") rather than producing an incomplete document.
- `QR_CODE_CARD` depends on the Customer Portal build-detail URL being resolvable (requires `order_id` and, ideally, `Capture3DAsset.status = PUBLISHED` for the QR's target page to be fully populated — if not yet published, the QR still generates but links to a page showing "3D model publishing soon").
- `USB_MANIFEST` (as a *document*, i.e., the printed insert listing USB contents) depends on `USBManifest.status >= BUILT`.

The generator evaluates a simple dependency graph per order and generates documents in dependency order, surfacing per-document status (Generating/Ready/Failed/Blocked) rather than failing the whole batch if one document's dependency isn't ready.

### 17.3 Failure handling

On render failure (template error, missing data field), the `CXDocument` row is marked `FAILED` with an error message stored in `content_json.error`, and the Order Packaging screen surfaces this with a "Retry" action. A failed document does **not** block the Final Quality Gate by default, but each document type can be flagged (`is_shipment_blocking: true`) in its `cx_document_templates` config — v1 seed configuration marks `WARRANTY_PACK` and `BUILD_CERTIFICATE` as shipment-blocking (legal/compliance and provenance-critical documents), all others as non-blocking (Business Rule BR-4).

### 17.4 Rendering pipeline

Documents are authored as structured JSON content (per template `layout_spec`) and rendered to PDF via a server-side HTML-to-PDF pipeline (reusing whatever rendering approach the existing `WelcomeGuide.pdf_blob` generation already uses, for consistency — if none exists yet, standardize on a headless-browser-based renderer, e.g., Playwright/Chromium print-to-PDF, noting the codebase's `flipflop-api` `Dockerfile.dev` already provisions Playwright browser dependencies per Chapter 6.2 of the deployment history, making this a natural fit with zero new infrastructure).

---

## 18. Documentation Generator

Per-document specification. Each entry: purpose, mandatory content fields, personalization fields, tone, and shareability consideration.

### 18.1 Build Certificate
**Purpose:** Formal, certificate-styled single page — "This build was assembled and quality-tested for [Customer Name] on [Date] by [Builder Name / FlipFlopOS Business Name]." Includes a unique build serial number and QC pass confirmation.
**Personalization:** customer name, build name/nickname if customer supplied one at order time, builder name, completion date, unique serial.
**Shareability:** Designed to look good photographed — this is explicitly one of the "frameable" documents, using premium typography and the tenant's brand color scheme (pulled from existing brand/theme settings, e.g. `desktop_theme.py` / `app_settings.py` if these hold tenant branding — confirm and wire to existing theme model rather than introducing a second brand-config source, Business Rule BR-5).

### 18.2 Captain's Log
**Purpose:** The emotional centerpiece document — a narrative-styled log of the build's journey, structured per `captains_log_spec` sections (e.g., "Sourcing," "Assembly," "Testing," "Ready for Departure"), written in a tone matching the `unboxing_sequence` narrative reference. Includes real photos captured during Photography Workflow (selected hero shots), real benchmark highlights, and the exact component list with plain-language framing (not just a spec sheet — e.g., "Your RTX 4070 will handle 1440p gaming at high settings with room to spare").
**Personalization:** customer name, build nickname, component list, key photo inserts, key benchmark highlight, delivery date.
**Shareability:** Highest-priority shareable document — designed to be the item a customer photographs and posts. Includes the branded QR code linking to the full digital experience.

### 18.3 Benchmark Report
**Purpose:** Pulls directly from the existing Benchmark Recording module's data for this order, formatted as a clean, branded one-pager (or more, if multiple benchmark suites were run) showing scores, comparisons to reference builds, and plain-language interpretation.
**Personalization:** actual recorded scores for this specific unit (not the Build Playbook's generic spec sheet).
**Note:** This document is generated from existing Benchmark Recording data — CXP adds formatting/branding/generation, not new benchmark capture logic.

### 18.4 Getting Started Guide
**Purpose:** Practical first-boot guide — power on, initial OS setup steps (given existing OS/theme selection flow evidenced by `os_component.py`/`desktop_theme.py`), where to find drivers (on the included USB), how to contact support.
**Personalization:** OS chosen, theme/RGB software installed (if applicable) referencing the actual selection made in the storefront configurator.

### 18.5 Upgrade Guide
**Purpose:** Forward-looking, low-pressure upsell — "Your build has 2 free RAM slots" / "Your PSU supports a GPU upgrade up to X wattage" — grounded in the actual build's spec/case constraints, not generic marketing.
**Personalization:** actual empty slots/headroom computed from the order's component list and case spec (data already available from Component Catalogue / Build Playbook specs — CXP computes headroom, does not re-author component data).

### 18.6 Warranty Pack
**Purpose:** Terms, duration, what's covered, how to claim, contact details. Legally/compliance-relevant — hence shipment-blocking by default (17.3).
**Personalization:** warranty start date, duration (from Build Playbook or tenant-level default), unique claim reference tied to build serial number.

### 18.7 QR Code Card
**Purpose:** A single physical card (or integrated into the Captain's Log/Build Certificate as a printed element) with a QR code linking to the customer's private Customer Portal build page (3D viewer + benchmark + docs + share kit).
**Personalization:** unique per-order QR target URL (signed/expiring token pattern consistent with existing Authentication module's session/token approach, not a public guessable order ID).

### 18.8 Welcome Letter
**Purpose:** Short, warm, first-thing-you-see letter (per Presentation Order, 16.1) welcoming the customer, previewing what's in the box, setting the tone for the unboxing before any protective layer is removed.
**Personalization:** customer name, build nickname, a one-line "why we chose these components for you" note pulling from the Build Playbook's `target_use_case`/`what_they_want_from_build` fields (already present in the existing Playbook seed data structure, per the codebase's `_INITIAL_PLAYBOOKS` pattern) — reusing existing data rather than requiring new authored copy per order.

### 18.9 Accessory Checklist
**Purpose:** Operational/customer-dual-purpose checklist confirming everything that should be in the box is in the box — doubles as a customer-facing "did I receive everything" reference.
**Personalization:** exact accessory/gift list from the resolved Packaging Playbook.

### 18.10 USB Manifest
**Purpose:** Printed insert listing exactly what's on the included USB drive, with categories and brief descriptions, so the customer isn't left guessing what to explore.
**Personalization:** derived directly from `USBManifest.file_manifest_json` (17.2 dependency).

### 18.11 Migration note re: existing `WelcomeGuide`
The existing `welcome_guide.py` model/table is functionally a predecessor of the `GETTING_STARTED_GUIDE` document type. Migration approach: introduce the new `cx_documents` pipeline for all new orders; existing `WelcomeGuide` rows remain readable (no data loss) via a read-compatibility shim in the Customer Portal, and new orders generate `GETTING_STARTED_GUIDE` via the unified pipeline instead. No forced backfill/migration of historical `WelcomeGuide` rows is required for launch (Business Rule BR-6, minimizing rollout risk).

---

## 19. USB Builder

(Schema in 7.11–7.12; screen in 10.8, panel in 10.1.6.)

### 19.1 Manifest assembly

`usb_manifest_builder.build(order)`:
1. Resolve `USBTemplate` (from the linked Build Playbook if set, else a tenant-level default template).
2. For each `content_category` enabled in the template: pull static files (drivers, BIOS, firmware, recovery tools, manuals, RGB software, benchmarks, wallpapers, utilities — all pre-uploaded, shared assets referenced by `static_file_refs`) plus order-specific dynamic content (warranty PDF, customer documents = the just-generated `cx_documents` PDFs, build photographs = selected `order_photos`, prioritizing hero shots).
3. Compute `total_size_bytes`; compare against `capacity_bytes` (resolved from the USB hardware's `ProcurementProduct` record, which itself should carry a capacity spec — extend `procurement_products` category `USB_MEDIA` with an optional `capacity_bytes` field, or store in existing `unit_of_measure`/a small `spec_json` addition; recommend adding a generic nullable `spec_json` column to `procurement_products` for exactly this kind of category-specific attribute, avoiding a proliferation of nullable single-purpose columns).
4. If manifest exceeds capacity: flag `status = FAILED` with a clear message identifying which category is oversized (typically build photographs — full-res originals vs. web-optimized versions matter here; USB builder should default to web-optimized/compressed photo variants, not originals, unless a "premium extras" flag in the Packaging Playbook requests full-resolution inclusion).

### 19.2 Validation

Before allowing "Confirm Written to Media," the system validates: manifest `status = BUILT`, `total_size_bytes <= capacity_bytes`, and — Business Rule BR-3 — that all shipment-blocking documents (17.3) are `READY` (not `FAILED`/`GENERATING`) before they can be included, preventing a USB with a half-broken PDF from shipping.

### 19.3 Physical write confirmation

v1 does not automate physical USB flashing (no hardware integration in scope). The operator flashes the USB using existing floor tooling/process, then checks "Confirm Written to Media," which timestamps `written_at`/`written_by` and transitions `status = WRITTEN_TO_MEDIA`. This status is one of the inputs to the Final Quality Gate if the Packaging Playbook's `usb_content_spec` marks USB as a mandatory inclusion for that tier (some budget tiers may intentionally omit a physical USB and rely on the digital fallback).

### 19.4 Digital fallback

For tiers/situations where a physical USB is not included (cost-sensitive tiers, or hardware supply shortage), operator selects "Use Digital Fallback" — the manifest content becomes available via the Customer Portal downloads section instead (Chapter 10.10), and `USBManifest.status = DIGITAL_FALLBACK`, which counts as satisfied for gating purposes as long as the Packaging Playbook did not mark physical USB as strictly mandatory (`usb_content_spec.physical_required: true/false` flag).

---

## 20. Photography Workflow

(Schema in 7.13–7.14; panel in 10.1.3.)

### 20.1 Seed mandatory requirements (global, `packaging_playbook_id = null`)

**During assembly (`ASSEMBLY`):** Empty case; Motherboard installed; CPU + cooler mount; RAM installed; GPU installed; Cable management (post-tidy); RGB lit (if applicable to build).

**After completion (`COMPLETION`):** Front; Rear; Left panel; Right panel (glass/window side if present); Interior (lit); Glamour shot (angled, styled lighting) — flagged `is_hero_shot` candidate by default.

**Packaging (`PACKAGING`):** Packaging materials laid out pre-pack; Box interior mid-pack (showing protective layering, for QA/damage-claim evidence value).

**Final boxed (`FINAL_BOXED`):** Sealed box, labels visible.

Playbook-specific additions layer on top — e.g., "Flagship Showcase" adds a mandatory 360° turnaround photo set (a fixed number of angle shots, e.g., 8, stored as a single `PhotoRequirement` row with a `quantity_required` extension field, or as 8 discrete requirement rows for simplicity in v1 — recommend the latter to keep the gating logic uniformly "one requirement = one photo" rather than introducing a parallel quantity-based gating path).

### 20.2 Gating logic

`photo_gate.evaluate(order)` returns `{mandatory_total, mandatory_captured, optional_total, optional_captured, missing: [requirement_labels]}`. The Order Packaging screen's footer "Mark Ready to Ship" action is disabled whenever `mandatory_captured < mandatory_total`, with the tooltip listing `missing` by label.

### 20.3 Capture UX

Upload control supports drag-drop (desktop admin) and direct camera capture (if admin accessed from a mobile/tablet device on the fulfilment floor — standard `<input type="file" capture>` pattern, no custom native app required for v1). Each upload immediately updates the checklist and re-evaluates the gate (optimistic UI, server-confirmed).

### 20.4 Hero shot selection and social kit linkage

Any photo flagged `is_hero_shot` becomes a candidate for: (a) the Customer Portal's primary build image, (b) inclusion in the Captain's Log, (c) the social share kit (Chapter 25). At least one `COMPLETION`-stage photo must be flagged hero by the operator before shipment — enforced as its own lightweight rule ("at least 1 hero shot selected") rather than a full mandatory `PhotoRequirement` row, since it's a selection-among-existing-photos action rather than a new capture.

---

## 21. 3D Capture Workflow

(Schema in 7.15; panel in 10.1.4.)

### 21.1 Integration with existing 3D pipeline

CXP does not reimplement 3D capture — it wraps and sequences the existing process (referenced in prior deployment work as `MotherboardViewer3D.tsx` and general 3D model handling in the storefront configurator). The `Capture3DAsset` table is the CXP-side tracking record; the actual capture mechanism (photogrammetry rig, manual 3D scan, or pre-rendered model swapped with actual component selections) is whatever already exists — CXP's job is orchestration: trigger, track status, store references, and gate publication.

### 21.2 Pipeline stages

`PENDING → CAPTURED → OPTIMIZING → OPTIMIZED → PUBLISHED` (or `FAILED` at any stage). "Trigger Capture" in the Order Packaging screen calls into the existing capture process/service; on completion webhook or polled status, CXP updates `raw_asset_ref`. An optimization step (mesh decimation / texture compression to a web-viewer-safe budget) produces `optimized_asset_ref` + `preview_image_ref`. "Publish" (automatic on `OPTIMIZED`, or manual gate if a tenant wants operator review first — configurable) sets `status = PUBLISHED` and makes the asset visible via the Customer Portal 3D viewer.

### 21.3 AR-readiness (not implementation)

`ar_ready` boolean is computed against a defined technical ceiling (e.g., poly count ≤ 150k, texture atlas ≤ 4K, file format glTF/GLB/USDZ available) so that when AR viewing is built (Future Enhancement, Chapter 35), a backlog of already-AR-ready assets exists rather than requiring a reprocessing pass. No AR rendering, no ARKit/ARCore integration, no `<model-viewer>` AR-mode wiring is in scope for v1 — this section defines data readiness only.

### 21.4 Gating

3D capture is **not** a shipment-blocking gate by default (a build should not wait for 3D asset optimization if that pipeline has latency) — it publishes asynchronously and the QR Code Card (18.7) gracefully degrades ("3D model publishing soon") if not yet ready at ship time, then updates live once published, since the QR links to a live portal page, not a static snapshot.

---

## 22. Final Quality Gate

(Schema in 7.16–7.17; panel in 10.1.7.)

### 22.1 Check definitions

Global mandatory checks (seed data), evidence type in parentheses: Cable management meets standard (Photo); Component seating verified/no play (None — visual operator confirmation); Cooling mounted per spec/no gaps (Photo); RGB sync verified if applicable (Photo); Burn-in/stress test passed (None, but requires linkage to existing Benchmark Recording pass/fail result — QC check `QC_BURN_IN_PASS` should read the actual benchmark module's stress-test outcome rather than duplicating pass/fail entry, wiring into existing data, Business Rule BR-8); OS boots and activates correctly (None); All drivers installed (None); Packaging integrity — box seals correctly, no gaps (Photo); Final visual inspection sign-off (Signature).

Playbook-specific additions layer on (e.g., Flagship Showcase adds "Turntable video captured" — Photo/video evidence — and "Second operator sign-off" — Signature — for a four-eyes premium QC standard).

### 22.2 Evidence capture

Inline per check: Photo → same upload control pattern as Photography Workflow; Signature → lightweight signature-pad component (canvas-based, standard pattern) capturing the performing operator's confirmation, stored as an image ref in `evidence_signature_ref`; both → both controls shown.

### 22.3 Gating logic

`qc_gate.evaluate(order)` mirrors `photo_gate` shape: `{mandatory_total, mandatory_passed, missing: [check_labels]}`. "Mark Ready to Ship" requires `mandatory_passed == mandatory_total` **and** the photo gate to also be satisfied **and** any shipment-blocking documents (17.3) to be `READY` **and** (if the Packaging Playbook marks USB physical-required) the USB gate satisfied. All four gate conditions are evaluated together and surfaced as a single combined checklist in the footer tooltip so an operator sees one unified "what's left" list rather than four separate panels' worth of scattered state (UX principle: minimize cognitive load for a floor operator under time pressure).

### 22.4 Audit log

Every `QualityGateResult` write is timestamped and attributed (`performed_by`, `performed_at`); combined with `Order` status transition timestamps, this constitutes a full audit trail sufficient for damage-claim disputes or internal quality investigations — no separate audit log table is needed since the existing rows already carry full provenance (Business Rule BR-9: prefer enriching existing tables with audit fields over introducing a parallel generic audit log, consistent with the rest of the schema's pattern of per-table timestamp/actor columns).

---

## 23. Shipping Workflow

CXP's shipping scope is intentionally narrow (see Non-Goals, Chapter 5): it governs the **handoff moment**, not carrier integration.

### 23.1 Status transition

`READY_TO_SHIP → SHIPPED` requires: all Final Quality Gate conditions met (22.3), and entry of a shipping reference (tracking number / carrier name — simple text fields on the existing `Order` model, or a new minimal `orders.tracking_number` / `orders.carrier` pair if not already present; if a shipping/fulfilment system already exists elsewhere in FlipFlopOS, CXP should call into it rather than duplicate fields — flagged here as an integration checkpoint for the engineering team to confirm against current codebase state at implementation time).

### 23.2 Post-ship triggers

On transition to `SHIPPED`: (a) Customer Portal publish job fires (Chapter 24) if not already published incrementally; (b) `CXCostRecord` rollup computed/finalized (Chapter 24 cost engine, ensures shipping-stage costs like final packaging weight are captured); (c) customer notification fires (Chapter 29) including tracking info and a preview/teaser of the Customer Portal build page ("Your build journey — and a first look at your PC in 3D — is ready to view").

### 23.3 Delivery confirmation (soft, non-blocking)

If carrier tracking webhook/status data is available (existing or future integration), a "Delivered" sub-status can update `Order.actual_delivery_date` (existing field) automatically. If unavailable, this remains a manual entry — CXP does not require building carrier webhook integration for v1.

---

## 24. Cost Engine

(Schema in 7.18.) `cost_rollup.compute(order)`:

```
packaging_cost      = Σ (packaging_playbook_components.unit_cost_snapshot × quantity)  [carton + protection + void_fill + security + label categories]
consumables_cost    = Σ (same, for any category flagged consumable rather than durable — v1 treats all BOM as consumed per-order, no distinction needed unless a future reusable-packaging program is introduced)
accessories_cost    = Σ (ACCESSORY + GIFT + PREMIUM_EXTRA categories)
documentation_cost  = 0 by default (digital PDFs have no marginal material cost) unless a tenant enables physical printing, in which case a per-page/per-document print cost from a tenant setting is applied
usb_cost            = unit_cost_snapshot for the USB_MEDIA product actually used (0 if DIGITAL_FALLBACK)
shipping_handling_cost = Packaging Playbook's flat carton/shipping estimate, or computed from carton weight class if that data is populated
labour_cost         = (time spent in Order Packaging screen, approximated via first-panel-open to Mark-Shipped timestamp delta, or a simpler fixed per-tier estimate configured on the Packaging Playbook if precise time tracking is judged too fragile for v1) × Order.labor_rate
total_cx_cost       = sum of all above
```

This total feeds into the existing Profit Calculator alongside `Order.component_costs` and `Order.overhead_amount`, giving `true_profit = customer_price − component_costs − total_cx_cost − overhead_amount`. The Profit Calculator screen (existing) gains a new cost-breakdown line item "Customer Experience Cost" — additive UI change only, no redesign of that module (respecting Non-Goals).

Recommendation on labour time tracking precision: given operator multitasking is common on a fulfilment floor, first-open-to-shipped elapsed time will overstate true labour minutes. **Recommended approach for v1: use a fixed per-Packaging-Playbook labour-minutes estimate** (a new `packaging_playbooks.estimated_labour_minutes` field) rather than wall-clock tracking, revisiting precise time-tracking as a Future Enhancement if cost accuracy demands it. This is a deliberate simplification flagged for stakeholder sign-off, not an oversight.

---

## 25. Customer Portal Integration

(Screens in 10.10.)

### 25.1 Publish trigger

A `customer_portal_publish` job runs incrementally as artifacts become ready (3D asset published, documents ready, order shipped) rather than as a single big-bang publish at ship time — so a customer whose 3D model finishes optimizing before the box even ships could, if desired by tenant configuration, get an early "sneak peek" notification (configurable per-tenant; default off, since early reveal may reduce unboxing surprise — Business Rule BR-10, tenant-configurable to respect the philosophy in Chapter 2 that anticipation is intentional, not accidental).

### 25.2 "Your Build Journey" page content

- Timeline (Chapter 10.10) sourced from `Order.status` history (reuse whatever status-history tracking pattern the existing Build Tracking module already has; if none exists, add a minimal `order_status_history` table as a straightforward audit table — flagged as a possible existing-module extension rather than new CXP-owned concept, since status history logically belongs to Build Tracking, not CXP).
- 3D viewer embed (standard web 3D viewer component, e.g., `<model-viewer>` or Three.js canvas, consistent with whatever the existing `MotherboardViewer3D.tsx` component already uses as its rendering approach — reuse that component/library rather than introducing a second 3D rendering dependency).
- Benchmark report viewer (renders `CXDocument` `BENCHMARK_REPORT` content, either as embedded PDF viewer or as a structured HTML re-render of `content_json` for a nicer in-browser experience than a raw PDF embed).
- Downloads section (direct links/downloads for non-blocking documents the tenant chooses to expose digitally — Warranty Pack, Getting Started Guide, Upgrade Guide by default).
- **Share kit CTA:** opens a lightweight modal offering pre-cropped, pre-branded image assets (from hero shots, Chapter 20.4) sized for Instagram/Twitter/TikTok, plus a short suggested caption, plus the customer's own QR-linked page URL for tagging — removing friction from the "I want to share this" impulse identified in Chapter 2/Objective B3. This is a static asset-serving feature (no auto-posting/OAuth integration to social platforms in v1 — Non-Goal).

### 25.3 Access control

The build journey page is accessed via the customer's existing authenticated Customer Portal session (existing Authentication module) **or** via the QR code's signed token for pre-login/gift-recipient scenarios (e.g., someone bought a PC as a gift; the QR should work for the recipient without requiring them to have platform credentials) — token scoped read-only to that single order's public-safe fields (Business Rule BR-11: QR token access must never expose other orders, account settings, or payment data — read-only, single-order-scoped, expiring after a configurable window, default 1 year).

---

## 26. Reporting

(Screen in 10.9.) Extends existing Reporting & Analytics module rather than duplicating its shell.

| Report | Dimensions | Key metrics |
|---|---|---|
| Packaging Cost by Playbook | Playbook, date range | Avg cost/order, cost variance (stdev/mean), trend over time |
| Supplier Spend | Supplier, product, date range | Total spend, avg unit cost, lead time adherence |
| Consumable Usage | Product, date range | Units consumed, burn rate, days-of-stock-remaining projection |
| Customer Experience Cost | Playbook, date range | Total CX cost, CX cost as % of order value, breakdown by cost category (7.18) |
| Fulfilment Time | Playbook, date range | Time in `READY_TO_PACKAGE`→`SHIPPED`, broken down by gate (photo/QC/doc/USB) to identify bottlenecks |
| Photo/QC Gate Compliance | Playbook, operator, date range | % mandatory items completed on first pass vs. requiring follow-up, flags recurring gaps for training |
| Profitability Impact | Playbook, date range | Correlate CX cost against B2–B4 proxy metrics (review rating, repeat purchase) where Reporting module can join order-level review/repeat-purchase data — CXP supplies the cost/tagging side, Reporting module supplies the correlation view, avoiding CXP reimplementing existing analytics infrastructure |

All reports respect existing Reporting module date-range/filter/export UX conventions (assume CSV export exists already; CXP data sources plug into that shared export mechanism rather than building a parallel exporter).

---

## 27. Business Rules

| ID | Rule |
|---|---|
| BR-1 | Every ACTIVE Build Playbook must have exactly one linked Packaging Playbook. Cannot activate/save a Build Playbook without this. |
| BR-2 | An order's `packaging_playbook_id` is snapshotted at first entry to `READY_TO_PACKAGE` and does not change if the source Packaging Playbook is later edited/republished. |
| BR-3 | A USB manifest cannot be marked `WRITTEN_TO_MEDIA` if any shipment-blocking document (per BR-4) is not `READY`. |
| BR-4 | Document types can be flagged `is_shipment_blocking` per template config. Seed default: `WARRANTY_PACK` and `BUILD_CERTIFICATE` are blocking; all others are non-blocking. |
| BR-5 | Document branding (colors, logo, tenant name) pulls from the existing tenant brand/theme configuration source (confirm exact model at implementation time — likely `app_settings.py`/`desktop_theme.py`), not a new CXP-local brand config. |
| BR-6 | Existing `WelcomeGuide` rows are not backfilled/migrated; new orders use the unified `cx_documents` pipeline going forward. |
| BR-7 | `procurement_products.current_stock` is always derived from purchase/reservation ledgers, never directly writable via API. |
| BR-8 | The `QC_BURN_IN_PASS` quality gate check reads its pass/fail state from the existing Benchmark Recording module's stress-test result for the order, rather than requiring separate manual entry. |
| BR-9 | Audit trail is achieved via per-table actor/timestamp columns (existing codebase convention), not a separate generic audit-log table, unless a cross-cutting need emerges later. |
| BR-10 | Early "sneak peek" Customer Portal publication ahead of shipment is tenant-configurable and defaults to OFF, preserving the deliberate anticipation design principle (Chapter 2). |
| BR-11 | QR-token-based Customer Portal access is read-only, single-order-scoped, and time-limited (default 1 year expiry); it must never expose data beyond that order's public-safe fields. |
| BR-12 | An order cannot transition to `READY_TO_SHIP` unless: all mandatory `PhotoRequirement`s are satisfied, all mandatory `QualityGateCheck`s pass, all shipment-blocking documents are `READY`, and (if the resolved Packaging Playbook marks USB as `physical_required: true`) the USB manifest is `WRITTEN_TO_MEDIA` or the Packaging Playbook explicitly permits `DIGITAL_FALLBACK`. |
| BR-13 | An order cannot transition to `SHIPPED` without a shipping reference (tracking number/carrier) recorded. |
| BR-14 | At least one `COMPLETION`-stage photo must be flagged `is_hero_shot` before shipment. |
| BR-15 | Packaging Playbook publish validation requires: non-empty carton spec, at least one protection BOM line, at least one documentation pack entry. A playbook cannot be published (only saved as Draft) if these are missing. |

---

## 28. Validation Rules

- **Packaging Playbook editor:** `name`/`slug` required, unique; `slug` auto-derived from `name` (kebab-case) but editable; numeric quantity fields on BOM rows must be positive integers; at least one row required per BR-15-covered categories before publish (Draft save has no such restriction, to support incremental authoring).
- **Procurement Product form:** `name` required; `unit_cost` ≥ 0; `min_stock_level` ≤ `reorder_level` is *not* enforced as an error (a business may intentionally set reorder above min for buffer) but a warning is shown if `reorder_level` < `min_stock_level` (likely a data-entry mistake, reorder should typically be ≥ min).
- **Procurement Purchase form:** `quantity` > 0; `unit_cost_paid` ≥ 0; `purchase_date` cannot be in the future.
- **Photography upload:** accepted formats (JPEG/PNG/HEIC with server-side conversion), max file size configurable (default 25MB per photo, since these may be high-res for hero-shot/print quality), minimum resolution warning (not hard block) if below a print-quality threshold for `is_hero_shot`-flagged images.
- **Quality Gate evidence:** if `requires_evidence` includes `PHOTO`, cannot mark `passed = true` without an `evidence_photo_url` present; same for `SIGNATURE` requiring `evidence_signature_ref`.
- **USB Manifest:** cannot mark `WRITTEN_TO_MEDIA` if `total_size_bytes > capacity_bytes` (hard validation error, not a warning).
- **Order Packaging screen "Mark Ready to Ship":** client-side disables the action and server-side additionally re-validates all BR-12 conditions on submit (never trust client-only gating for a state transition with downstream consequences).
- **QR token generation:** must reject generation if the target order's customer-facing fields include no valid `customer_id` linkage (defensive check against orphaned/test orders leaking a portal link).

---

## 29. Notifications

| Trigger | Recipient | Channel | Content |
|---|---|---|---|
| Order enters `READY_TO_PACKAGE` | Fulfilment/Packing team (role-based) | In-app + existing notification channel (email/Slack, whichever existing `alert_event` pipeline supports) | "Order #X ready to package — [Playbook name]" |
| Mandatory photo/QC/doc/USB gate blocked for > configurable threshold (default 4 business hours) while order sits in `PACKAGING_IN_PROGRESS` | Operations Manager | In-app + email | "Order #X has been in packaging for Nh, blocked on: [missing items]" — surfaces bottlenecks proactively rather than only at shift-end review |
| Procurement product `current_stock <= reorder_level` | Procurement Coordinator | In-app + email | "Reorder needed: [Product name], current stock X, reorder level Y" |
| Document generation `FAILED` | Assigned operator / Operations Manager | In-app | "[Document type] failed to generate for Order #X: [error summary]" |
| Order transitions to `SHIPPED` | Customer | Email (existing customer comms channel) | Tracking info + "Your build journey page is ready" CTA linking to Customer Portal |
| 3D asset `PUBLISHED` (if tenant enables early sneak-peek, BR-10) | Customer | Email | "A first look at your PC in 3D is ready" |
| Packaging Playbook published with a cost delta exceeding a configurable threshold (e.g., >10% cost change) vs. prior version | Operations Manager | In-app | "Playbook '[name]' republished — estimated cost changed from £X to £Y" — cost-governance safeguard |

All notifications reuse the existing alerting/notification infrastructure (`alert_event.py` and whatever delivery mechanism it already wires to) rather than introducing a new notification system.

---

## 30. Security & Permissions

New role-scoped permissions, layered onto the existing Authentication/authorization model (assume existing role-based access control, extend rather than replace):

| Permission | Roles (default) |
|---|---|
| `cxp.packaging_playbook.view` | All admin roles |
| `cxp.packaging_playbook.edit` | Operations Manager, Admin |
| `cxp.packaging_playbook.publish` | Operations Manager, Admin (edit alone does not imply publish — publishing affects live orders and cost baselines, warranting a stricter gate) |
| `cxp.procurement.view` | All admin roles |
| `cxp.procurement.edit` | Procurement Coordinator, Operations Manager, Admin |
| `cxp.order_packaging.operate` | Packing Technician, Operations Manager, Admin — covers photo upload, QC evidence entry, document generation trigger, USB confirm |
| `cxp.order_packaging.mark_shipped` | Operations Manager, Admin (a deliberately narrower set than general packaging operation, since this is the final irreversible-in-practice gate) |
| `cxp.reporting.view` | Operations Manager, Admin, Business Owner |
| `cxp.document_template.edit` | Admin only (templates affect brand-critical legal documents like Warranty Pack) |

**Customer-facing security:** QR-token access (BR-11) uses signed, expiring tokens (JWT or equivalent, consistent with existing Authentication module's token approach) scoped to a single order ID, with no ability to enumerate or pivot to other orders/customer data. All document PDF downloads via the Customer Portal require either an authenticated customer session matching the order's `customer_id`, or a valid QR token for that specific order — never an unauthenticated-by-order-ID-guessing pattern.

**Data sensitivity:** `procurement_purchases.unit_cost_paid` and all cost-related fields are internal-only (never exposed via any customer-facing API/page) — customers see finished documents (Warranty, Getting Started, etc.), never raw cost data.

---

## 31. API Design

RESTful, consistent with existing FlipFlopOS FastAPI router conventions (path-versioned under existing API prefix, e.g., `/api/v1/...`).

```
# Packaging Playbooks
GET    /api/v1/cxp/packaging-playbooks
POST   /api/v1/cxp/packaging-playbooks
GET    /api/v1/cxp/packaging-playbooks/{id}
PUT    /api/v1/cxp/packaging-playbooks/{id}          # saves draft or edits live per rules
POST   /api/v1/cxp/packaging-playbooks/{id}/publish
POST   /api/v1/cxp/packaging-playbooks/{id}/clone
GET    /api/v1/cxp/packaging-playbooks/{id}/versions

# Procurement
GET/POST      /api/v1/cxp/procurement/products
GET/PUT       /api/v1/cxp/procurement/products/{id}
GET/POST      /api/v1/cxp/procurement/suppliers
GET/PUT       /api/v1/cxp/procurement/suppliers/{id}
GET/POST      /api/v1/cxp/procurement/purchases
GET           /api/v1/cxp/procurement/products/{id}/stock   # derived stock calc (BR-7)

# Order Packaging (operational)
GET    /api/v1/cxp/orders/{order_id}/packaging            # full aggregate view: BOM, photo gate, qc gate, docs, usb
POST   /api/v1/cxp/orders/{order_id}/packaging/override    # apply Packaging Playbook override
POST   /api/v1/cxp/orders/{order_id}/photos                # upload photo against a requirement
GET    /api/v1/cxp/orders/{order_id}/photos/gate-status
POST   /api/v1/cxp/orders/{order_id}/capture-3d/trigger
GET    /api/v1/cxp/orders/{order_id}/capture-3d
POST   /api/v1/cxp/orders/{order_id}/documents/generate         # body: {document_type} or {all: true}
GET    /api/v1/cxp/orders/{order_id}/documents
POST   /api/v1/cxp/orders/{order_id}/usb/build-manifest
POST   /api/v1/cxp/orders/{order_id}/usb/confirm-written
POST   /api/v1/cxp/orders/{order_id}/usb/digital-fallback
POST   /api/v1/cxp/orders/{order_id}/quality-gate/{check_id}/result
GET    /api/v1/cxp/orders/{order_id}/quality-gate/status
POST   /api/v1/cxp/orders/{order_id}/mark-ready-to-ship        # re-validates all gates server-side (BR-12)
POST   /api/v1/cxp/orders/{order_id}/mark-shipped              # requires tracking ref (BR-13)

# Reporting
GET    /api/v1/cxp/reporting/packaging-cost
GET    /api/v1/cxp/reporting/supplier-spend
GET    /api/v1/cxp/reporting/consumable-usage
GET    /api/v1/cxp/reporting/cx-cost
GET    /api/v1/cxp/reporting/fulfilment-time
GET    /api/v1/cxp/reporting/gate-compliance

# Customer Portal (public/customer-scoped, distinct auth)
GET    /api/v1/portal/orders/{order_id}/journey            # requires customer session or valid QR token
GET    /api/v1/portal/orders/{order_id}/documents
GET    /api/v1/portal/orders/{order_id}/capture-3d
GET    /api/v1/portal/qr/{signed_token}                     # resolves token → order journey, read-only
```

Standard response envelope matches existing FlipFlopOS API conventions (success flag, data payload, error message, pagination meta where applicable — per the established API Response Format pattern already used across the codebase).

---

## 32. Acceptance Criteria

- [ ] Every ACTIVE Build Playbook has a non-null linked Packaging Playbook; attempting to save/activate one without a link is rejected with a clear validation error (BR-1).
- [ ] Opening the Order Packaging screen for any order in `READY_TO_PACKAGE` correctly displays the resolved BOM, photo checklist, QC checklist, and document list matching the snapshot Packaging Playbook.
- [ ] Uploading all mandatory photos updates the gate status to fully satisfied and removes the corresponding block from "Mark Ready to Ship."
- [ ] Attempting "Mark Ready to Ship" with any mandatory photo, QC check, or shipment-blocking document incomplete is rejected both client-side (disabled control) and server-side (API returns validation error) — server-side rejection is independently verified even if client-side is bypassed.
- [ ] "Generate All" documents produces all documents in the resolved Packaging Playbook's `documentation_pack`, each downloadable as PDF, each correctly personalized with the order's actual customer name, component list, and benchmark data.
- [ ] USB manifest build correctly aggregates static + dynamic content and blocks confirmation if oversized, with a clear error naming the offending category.
- [ ] Quality Gate checks requiring photo/signature evidence cannot be marked passed without that evidence attached.
- [ ] Marking an order `SHIPPED` requires a tracking reference and triggers Customer Portal publish + customer notification.
- [ ] Customer Portal "Your Build Journey" page renders correctly for an authenticated customer viewing their own order, and via a valid QR token, and correctly denies/errors for a mismatched/expired token.
- [ ] Procurement `current_stock` value matches manual ledger calculation (purchases minus reservations) in a reconciliation test across at least 3 products with mixed purchase/reservation/release history.
- [ ] Low-stock notification fires within the scheduled job interval when a product crosses its reorder threshold.
- [ ] CX Reporting dashboards return correct aggregate figures against a seeded test dataset with known expected totals for at least Packaging Cost by Playbook and Fulfilment Time reports.
- [ ] Editing an ACTIVE Packaging Playbook does not alter the BOM/cost of any order whose packaging was already snapshotted prior to the edit (BR-2 regression test).
- [ ] All new admin screens respect existing role-based permission checks — a user without `cxp.order_packaging.mark_shipped` cannot successfully call the mark-shipped endpoint even via direct API call.

---

## 33. Testing Strategy

**Unit tests:**
- `packaging_playbook_resolver` resolution logic (default vs. override vs. snapshot-immutability).
- `photo_gate` / `qc_gate` evaluation logic across combinations of mandatory/optional/global/playbook-specific requirements.
- `cost_rollup` arithmetic against known fixture BOMs.
- `usb_manifest_builder` size validation and category-oversized error identification.
- Stock derivation calculation (BR-7) across purchase/reservation/release sequences.

**Integration tests:**
- Full order lifecycle: seed order → enter `READY_TO_PACKAGE` → upload all mandatory photos → complete all mandatory QC checks → generate all documents → build/confirm USB → `mark-ready-to-ship` succeeds → `mark-shipped` succeeds → Customer Portal journey endpoint returns expected published state.
- Negative-path integration test: attempt each gate-bypass scenario (missing photo, missing QC, missing blocking document, oversized USB, no tracking ref) and assert correct rejection at the API layer.
- Document generation dependency ordering: assert `BENCHMARK_REPORT` generation correctly blocks/retries when benchmark data is not yet present, then succeeds once it is.
- Cross-module integration: verify `QC_BURN_IN_PASS` correctly reads from existing Benchmark Recording module data rather than requiring separate manual entry (BR-8).

**Contract tests:**
- API response envelope shape consistency with existing FlipFlopOS conventions across all new endpoints.

**Manual/UAT:**
- End-to-end floor-operator walkthrough of the Order Packaging screen with a real (or realistic staging) order, timed, to validate the "no net increase >15% in fulfilment time" success metric assumption (Chapter 4) before general rollout.
- Document visual QA: render each of the 10 document types for a sample order and manually review branding, personalization accuracy, and print/photograph-ability (for Build Certificate and Captain's Log specifically, given their shareability design intent).
- Customer Portal QR token flow tested on at least 2 mobile browsers (iOS Safari, Android Chrome) given this is the primary real-world access path (customer scanning a physical card).

**Performance:**
- Load-test document generation and 3D asset optimization pipelines to ensure they do not become a fulfilment-floor bottleneck under peak daily order volume (define target volume with Operations stakeholder before rollout).

---

## 34. Rollout Plan

**Phase 0 — Foundations (no operator-facing change):**
Schema migrations for all new tables; seed Packaging Playbooks (tier examples from Chapter 13.3) as Drafts only; seed global `PhotoRequirement` and `QualityGateCheck` rows; Procurement Products/Suppliers populated with current known packaging materials by an Operations Manager before go-live.

**Phase 1 — Shadow mode:**
Order Packaging screen available and usable, but `READY_TO_SHIP` gating (BR-12) is **advisory only** (warnings shown, not enforced) for a defined pilot period (e.g., 2 weeks) — allows operators to build familiarity and surfaces any seed-data gaps (missing photo requirement labels, misconfigured QC checks) without blocking real fulfilment.

**Phase 2 — Enforced gating, single Packaging Playbook tier:**
Enable hard gating (BR-12 enforced) for orders on exactly one Build Playbook tier (recommend starting with the highest-value/lowest-volume tier, e.g., "Flagship Showcase," where the premium-experience payoff is highest and volume risk is lowest) to validate the full loop under real shipping pressure.

**Phase 3 — Full rollout:**
Enable enforced gating across all Build Playbook tiers; enable Customer Portal "Your Build Journey" publish for all shipped orders going forward; enable customer notifications (Chapter 29).

**Phase 4 — Reporting & optimization:**
CX Reporting dashboards go live once at least 4-6 weeks of Phase 3 data exists to be meaningful; review Success Metrics (Chapter 4) against baseline at the 3-month and 6-month marks; tune labour-minute estimates (Chapter 24) and cost assumptions based on observed data.

**Rollback plan:** Because `Order.status` gains new enum values inserted between existing `QA` and `READY_TO_SHIP`, and because the resolver snapshot pattern (BR-2) means historical orders are unaffected by playbook changes, rollback at any phase is limited to: (a) disabling hard gate enforcement (revert to Phase 1 shadow mode), or (b) fully disabling the new Order Packaging screen and reverting operators to whatever manual packing process preceded it, with existing `Order.status` values (`QA`, `READY_TO_SHIP`, `SHIPPED`, etc.) remaining valid and unaffected since no existing status values are removed, only new ones inserted in the sequence.

---

## 35. Future Enhancements

- **Augmented Reality viewer:** build on `Capture3DAsset.ar_ready` data readiness (Chapter 21.3) to ship an actual AR "view your PC in your room" experience from the QR Code Card.
- **Full WYSIWYG document template designer:** replace the v1 structured-form template editor (10.7) with a drag-and-drop visual builder for non-technical brand/marketing staff.
- **Supplier EDI/API integration:** activate the reserved `integration_config` seam (14.5) for automated purchase order transmission and stock-level sync with real suppliers.
- **Carrier integration for automated tracking/delivery confirmation:** replace manual tracking entry (23.1) and manual delivery-date entry (23.3) with real carrier webhook integration.
- **Automated social posting:** extend the share kit (25.2) from asset-download to direct OAuth-based posting to Instagram/TikTok/X, with customer opt-in.
- **Precise labour time tracking:** replace the fixed per-playbook labour-minute estimate (Chapter 24) with actual operator time-tracking once floor workflows and multitasking patterns are better understood, if cost accuracy demands it.
- **Reusable/returnable packaging program:** for sustainability-focused tenants, introduce a packaging-return/deposit workflow, requiring new consumable-vs-durable tracking distinction flagged as deferred in Chapter 24.
- **Multi-warehouse procurement:** extend Procurement schema (currently single-UK-warehouse assumption) to support per-warehouse stock and supplier routing for tenants operating multiple fulfilment locations.
- **Video capture as a first-class Photography Workflow artifact:** extend beyond static photos (e.g., mandatory short unboxing-simulation video clips for premium tiers) once storage/bandwidth cost models are evaluated.
- **A/B testing of Packaging Playbook variants:** measure incremental review-rating/repeat-purchase impact of specific presentation-order or document-copy variations directly within the CX Reporting module, closing the loop between Chapter 2's philosophy and Chapter 4's success metrics with real experimental evidence rather than correlation alone.

---

*End of document.*
