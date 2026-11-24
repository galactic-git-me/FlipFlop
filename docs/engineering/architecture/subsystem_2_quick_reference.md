# Subsystem 2: Orders & Capacity Management — Quick Reference

**Full Plan:** See `/home/mac/CODING/FlipFlop/SUBSYSTEM_2_PLAN.md` (1,741 lines)

---

## Quick Links to Key Sections

### Planning & Overview
- [Architecture Overview](#subsystem-2-orders--capacity-management--implementation-plan) — Order flow diagram, system components
- [Technology Stack](#tech-stack) — FastAPI, SQLAlchemy, Stripe, PostgreSQL
- [Implementation Timeline](#8-implementation-timeline) — 23 hours total, 4-5 days

### Design
- [Database Schema](#2-database-schema) — 3 tables (orders, build_capacity, build_capacity_overrides) + migration
- [Pydantic Schemas](#3-pydantic-schemas) — Request/response models for validation
- [API Endpoints](#4-api-endpoints-7-total) — 9 endpoints with full implementation code

### Implementation Tasks (In Order)

| Task | Effort | Files | Deps |
|------|--------|-------|------|
| [S2-1: Database Schema](#task-s2-1-database-schema--migrations) | 2-4h | models/*.py, migration | alembic |
| [S2-2: Pydantic Schemas](#task-s2-2-pydantic-schemas) | 1-2h | schemas/order.py | — |
| [S2-3: Stripe Setup](#task-s2-3-stripe-integration-setup) | 1-2h | config.py | stripe pkg |
| [S2-4: GET /api/orders/slots](#endpoint-1-get-aporderslots) | 2-3h | api/orders.py | S2-1 |
| [S2-5: POST /api/orders/checkout](#endpoint-2-post-apordersch out) | 3-4h | api/orders.py | S2-1,2,3 |
| [S2-6: POST /api/stripe/webhook](#endpoint-4-post-apstripewebhook) | 2-3h | api/stripe_webhooks.py | S2-3,5 |
| [S2-7: GET /api/orders/[ref]](#endpoint-3-get-apordersreference) | 1-2h | api/orders.py | S2-1,2 |
| [S2-8: Admin Endpoints](#task-s2-8-admin-endpoints-5-endpoints) | 4-5h | api/admin/orders.py | S2-1,2 |
| [S2-9: Email Notifications](#task-s2-9-email-notifications) | 2-3h | services/email.py | S2-6 |

### Testing
- [Unit Tests](#unit-tests) — Pytest patterns, test scenarios
- [Integration Tests](#integration-tests) — End-to-end checkout flow
- [Manual Testing](#manual-testing) — Stripe CLI, curl examples

### Deployment
- [Deployment Checklist](#9-deployment-checklist) — Pre-launch, go-live, monitoring
- [External Dependencies](#external-dependencies) — Stripe account, email service, database

---

## Key File Locations

**Backend Root:** `/home/mac/CODING/FlipFlop/pc-flipper-backend/`

Files to Create:
```
app/models/order.py                      (Order, status lifecycle)
app/models/build_capacity.py             (BuildCapacity, default)
app/models/build_capacity_override.py    (BuildCapacityOverride, per-week)

app/schemas/order.py                     (Pydantic models)

app/api/orders.py                        (GET slots, POST checkout, GET confirmation)
app/api/stripe_webhooks.py               (POST webhook handler)
app/api/admin/orders.py                  (Admin CRUD)

services/email.py                        (SendGrid integration)

alembic/versions/XXX_add_orders.py       (Schema migration)

tests/test_orders.py                     (Unit + integration tests)
```

Files to Modify:
```
app/models/__init__.py                   (Import new models)
app/config.py                            (Add Stripe config)
app/main.py                              (Register routers)
.env.local                               (Add Stripe secrets)
```

---

## Database Schema Summary

### Table: `orders`
- `id` (PK), `reference` (UQ, human-readable: FF-2026-00042)
- Build config: `playbook_id`, `playbook_name`, `build_config` (JSON)
- Customer: `customer_name`, `customer_email`, `customer_phone`, `delivery_address` (JSON)
- Pricing: `subtotal_gbp`, `tax_gbp`, `total_gbp`, `discount_gbp`
- Payment: `stripe_session_id`, `stripe_payment_intent_id`
- Fulfillment: `status`, `assigned_build_week`, `estimated_arrival_date`, `delivery_at_risk`
- Metadata: `admin_notes`, `created_at`, `updated_at`, `payment_confirmed_at`

### Table: `build_capacity`
- `id` (PK), `default_per_week` (int, typically 3)

### Table: `build_capacity_overrides`
- `id` (PK), `week` (UQ, ISO format 2026-W27), `max_builds` (nullable = closed), `note`

---

## API Endpoints Summary

### Public (No Auth)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/orders/slots` | GET | Get available weeks (next 8) |
| `/orders/checkout` | POST | Create order + Stripe session |
| `/orders/{reference}` | GET | Get order confirmation (after payment) |
| `/stripe/webhook` | POST | Stripe payment notification |

### Admin (Auth Required)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/orders` | GET | List orders (filter, paginate) |
| `/admin/orders/{id}` | PATCH | Update order status/notes |
| `/admin/capacity` | GET | Read capacity settings |
| `/admin/capacity/default` | PATCH | Update global default |
| `/admin/capacity/overrides/{week}` | PUT | Set/remove per-week override |

---

## Order Status Lifecycle

```
pending_payment
    ↓ (Stripe webhook confirms payment)
confirmed
    ↓ (Admin or auto, when build starts)
building
    ↓ (Admin, when shipped)
shipped
    ↓ (Tracking confirms arrival)
delivered

    OR (At any point)
cancelled
```

---

## Testing Checklist

Unit Tests (pytest):
- ✓ Slots calculation (capacity, overrides, booked count)
- ✓ Order reference generation (unique, format)
- ✓ Checkout validation (playbook, week, variants)
- ✓ Webhook signature verification
- ✓ Idempotent webhook replays
- ✓ Email sending

Integration Tests:
- ✓ End-to-end checkout → payment → webhook → confirmation
- ✓ Concurrent checkouts (race conditions)
- ✓ Capacity limits enforcement

Manual Tests (Stripe test mode):
- ✓ Test card 4242 4242 4242 4242 → success
- ✓ Test card 4000 0000 0000 0002 → decline
- ✓ Stripe CLI webhook forwarding
- ✓ Order confirmation email

---

## Environment Variables Required

```bash
# Stripe
STRIPE_SECRET_KEY=sk_live_...                 # Or sk_test_... for dev
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (SendGrid or AWS SES)
SENDGRID_API_KEY=SG.xxx_...
SENDGRID_FROM_EMAIL=noreply@flipflop.co.uk

# Frontend (for success/cancel URLs)
FRONTEND_URL=http://localhost:3000            # Or production URL

# Admin
ADMIN_API_KEY=secret-key-for-admin-endpoints
```

---

## Code Examples (Copy-Paste Ready)

### Test: Verify Order Creation
```python
@pytest.mark.asyncio
async def test_create_order_checkout(db):
    response = await client.post("/api/orders/checkout", json={
        "playbook_id": 1,
        "build_config": {"gpu": {...}, "cpu": {...}},
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
        "delivery_address": {...},
        "chosen_week": "2026-W27",
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["reference"].startswith("FF-2026-")
    assert "stripe_url" in data
```

### Test: Verify Webhook Handling
```python
@pytest.mark.asyncio
async def test_stripe_webhook_confirms_order(db):
    order = Order(...)
    db.add(order)
    await db.commit()
    
    payload = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "metadata": {"order_id": order.id},
            "payment_intent": "pi_test_123",
        }}
    }
    
    response = await client.post(
        "/api/stripe/webhook",
        json=payload,
        headers={"stripe-signature": sign_webhook(payload)},
    )
    
    assert response.status_code == 200
    updated = await db.get(Order, order.id)
    assert updated.status == "confirmed"
```

---

## Manual Testing (Stripe Test Mode)

```bash
# 1. Start dev server
cd pc-flipper-backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. Start Stripe CLI (in another terminal)
stripe listen --forward-to localhost:8000/api/stripe/webhook

# 3. Test available slots
curl http://localhost:8000/api/orders/slots | jq .

# 4. Create order (returns Stripe URL)
curl -X POST http://localhost:8000/api/orders/checkout \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_id": 1,
    "build_config": {...},
    "customer_name": "Test User",
    "customer_email": "test@example.com",
    "delivery_address": {...},
    "chosen_week": "2026-W27"
  }' | jq .stripe_url

# 5. Paste Stripe URL in browser, use test card 4242 4242 4242 4242

# 6. Stripe CLI will show webhook delivery (no manual action needed)

# 7. Verify order confirmed
curl http://localhost:8000/api/orders/FF-2026-00001 | jq .
```

---

## Implementation Sequence

**Recommended order (dependencies matter):**

1. ✅ **S2-1** — Create models + migration (enables DB queries)
2. ✅ **S2-2** — Create schemas (used by all endpoints)
3. ✅ **S2-3** — Stripe setup (enables checkout + webhook)
4. ✅ **S2-4** — GET /slots (read-only, no Stripe)
5. ✅ **S2-5** — POST /checkout (creates orders, uses Stripe)
6. ✅ **S2-6** — POST /webhook (processes payments)
7. ✅ **S2-7** — GET /confirmation (read-only)
8. ✅ **S2-8** — Admin endpoints (optional for MVP)
9. ✅ **S2-9** — Email notifications (async, non-blocking)

**First MVP (min viable):** Tasks 1-7 (16 hours)  
**Production-ready:** Tasks 1-9 (23 hours)

---

## Known Gotchas

1. **Stripe webhook signature verification** — Don't skip this (security)
2. **Idempotent webhook handling** — Stripe may replay events
3. **Capacity race conditions** — Check capacity again before final commit
4. **Timezone handling** — Use UTC for all timestamps (ISO format)
5. **ISO week format** — 2026-W27 (not 2026-27 or week 27)
6. **Order reference uniqueness** — Use database constraint (not just random)
7. **Email delivery** — Non-blocking (don't wait for SendGrid in webhook)

---

## Success Criteria (When Done)

- [ ] All 9 endpoints working (manual test + Stripe test mode)
- [ ] All unit tests passing (pytest)
- [ ] All integration tests passing (end-to-end flow)
- [ ] Webhook handling idempotent + secure
- [ ] Email confirmations sent within 1 minute
- [ ] Capacity enforcement working (no overbooking)
- [ ] Admin can override capacity per week
- [ ] Database migration tested on staging
- [ ] Error handling tested (Stripe down, email fail, etc.)
- [ ] Logged for observability (order IDs, statuses, errors)

---

**Status:** 📋 Ready for Implementation  
**Start Date:** 2026-06-22  
**Estimated Completion:** 2026-06-26 (or 2026-06-27 with email)

For full details, see `/home/mac/CODING/FlipFlop/SUBSYSTEM_2_PLAN.md`
