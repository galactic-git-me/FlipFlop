# Authentication & Buying Flow Implementation

**Branch**: `cursor/curated-playbooks-storefront-13ea`  
**Status**: ✅ Backend Complete, Frontend Integration Pending  
**PR**: [#12](https://github.com/galactic-git-me/FlipFlop/pull/12)

## Overview

Implements customer registration and buying flow data collection for FlipFlop.shop curated journey, per Michael + AnalyticsBot requirements:

- **Reuses existing auth patterns** from personalised builds / customer account site
- **Enforces registration before checkout** to tie looks→books to a person
- **Progressive disclosure** - collect data across journey, not one long form
- **Analytics integration** - emit buying flow context with all events

---

## Backend Changes (flipflop-api)

### 1. Customer Model Extensions

**File**: `app/models/customer.py`

**New fields**:
```python
# Registration data (once)
year_of_birth = Column(Integer, nullable=True)  # Age band + birthday offers
marketing_opt_in = Column(Boolean, default=False)  # Separate from account
acquisition_source = Column(String(50), nullable=True)  # How they found us
acquisition_detail = Column(String(255), nullable=True)  # e.g., referral code
profile_metadata = Column(JSON, nullable=True)  # Extensible

# Magic link support (passwordless auth)
magic_link_token = Column(String(255), nullable=True, index=True)
magic_link_expires_at = Column(DateTime, nullable=True)
```

**Acquisition sources**:
- `search` - Found via search engine
- `youtube` - YouTube video/channel
- `reddit` - Reddit post/comment
- `referral` - Referral from friend
- `ebay` - eBay listing/profile
- `other` - Other source

### 2. Order Model Extensions

**File**: `app/models/order.py`

**New fields**:
```python
# Buying flow / curated journey data
is_gift = Column(Boolean, default=False)  # For self vs gift
recipient_age_band = Column(String(20), nullable=True)  # child/teen/adult/senior
discreet_packaging = Column(Boolean, default=False)
urgency = Column(String(20), nullable=True)  # asap/this_week/flexible
is_first_pc = Column(Boolean, nullable=True)  # First PC vs upgrade
current_gpu = Column(String(100), nullable=True)  # If upgrade
is_business_buyer = Column(Boolean, default=False)  # VAT invoice needed
wants_vat_invoice = Column(Boolean, default=False)
aesthetic_preference = Column(String(20), nullable=True)  # quiet/rgb

# Journey analytics (from wizard)
journey_budget_min = Column(Float, nullable=True)
journey_budget_max = Column(Float, nullable=True)
journey_customer_type = Column(String(50), nullable=True)  # "Great-value Gaming"
journey_tier = Column(String(20), nullable=True)  # budget/mid/high
```

### 3. Auth API Updates

**File**: `app/routes/auth.py` + `app/schemas/auth.py` + `app/services/auth_service.py`

#### POST /auth/signup (Enhanced)
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",  // Optional for magic link
  "name": "John Doe",
  "year_of_birth": 1995,  // Optional
  "marketing_opt_in": true,  // Optional, default false
  "acquisition_source": "reddit",  // Optional
  "acquisition_detail": "r/buildapc"  // Optional
}
```

**Response**:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

#### PATCH /auth/me (New)
Progressive profile updates - only send fields you want to update.

```json
{
  "year_of_birth": 1995,
  "marketing_opt_in": true,
  "acquisition_source": "reddit"
}
```

**Response**: Updated customer profile

#### GET /auth/me (Enhanced)
Now returns registration data:
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "year_of_birth": 1995,
  "marketing_opt_in": true,
  "acquisition_source": "reddit",
  "last_login": "2024-06-29T12:00:00Z",
  "created_at": "2024-06-28T10:30:00Z"
}
```

### 4. Analytics Endpoint

**File**: `app/api/public_catalogue.py`

#### POST /api/public/analytics/event
Track curated journey events with buying flow context.

```json
{
  "event_type": "playbook_tier_shown",
  "curated_build_id": "FF-GVG-02",
  "metadata": {
    "segment": "Great-value Gaming",
    "tier": "Mid-range",
    "price_gbp": 899
  },
  "buying_flow": {
    "is_gift": false,
    "aesthetic_preference": "rgb",
    "journey_budget_min": 800,
    "journey_budget_max": 1200,
    "journey_customer_type": "Great-value Gaming",
    "journey_tier": "mid"
  },
  "customer_id": 123
}
```

**Response**:
```json
{
  "status": "tracked",
  "event_type": "playbook_tier_shown"
}
```

### 5. Database Migration

**File**: `alembic/versions/20260921_0001_customer_registration_buying_flow.py`

Adds all new columns to `customers` and `orders` tables with appropriate defaults and indexes.

**To apply**:
```bash
cd flipflop-api
alembic upgrade head
```

---

## Frontend Changes (FlipFlop.shop.new)

### 1. Auth Utilities

**File**: `lib/auth.ts`

**Functions**:
- `signup(data: SignupData)` - Create account
- `login(data: LoginData)` - Authenticate
- `getMe(token: string)` - Get profile
- `updateProfile(token, updates)` - Update profile
- `storeToken(token)` / `getToken()` / `clearToken()` - Token management
- `isAuthenticated()` - Check auth status

**Usage**:
```typescript
import { signup, storeToken } from '@/lib/auth'

const handleSignup = async () => {
  const { access_token } = await signup({
    email: 'user@example.com',
    password: 'SecurePass123',
    name: 'John Doe',
    acquisition_source: 'reddit',
  })
  storeToken(access_token)
}
```

### 2. Buying Flow Types & Helpers

**Files**: `lib/types.ts`, `lib/analytics.ts`

**Type**:
```typescript
interface BuyingFlowData {
  is_gift: boolean
  recipient_age_band?: 'child' | 'teen' | 'adult' | 'senior'
  discreet_packaging: boolean
  urgency?: 'asap' | 'this_week' | 'flexible'
  is_first_pc?: boolean
  current_gpu?: string
  is_business_buyer: boolean
  wants_vat_invoice: boolean
  aesthetic_preference?: 'quiet' | 'rgb'
  journey_budget_min?: number
  journey_budget_max?: number
  journey_customer_type?: string
  journey_tier?: 'budget' | 'mid' | 'high'
}
```

**Functions**:
- `getBuyingFlowData()` - Get current buying flow data
- `updateBuyingFlowData(updates)` - Update buying flow (progressive)
- `trackEvent(type, build_id, metadata)` - Now sends buying flow context to backend

**Usage**:
```typescript
import { updateBuyingFlowData } from '@/lib/analytics'

// User selects budget
updateBuyingFlowData({
  journey_budget_min: 800,
  journey_budget_max: 1200,
})

// User indicates it's their first PC
updateBuyingFlowData({
  is_first_pc: true,
})

// Analytics events now include this context automatically
```

### 3. Enhanced Analytics

**File**: `lib/analytics.ts`

The `trackEvent()` function now:
1. Stores events locally (sessionStorage)
2. Sends to backend with buying flow context
3. Includes customer_id if authenticated

**Events tracked** (in order):
1. `budget_chosen` - With budget range
2. `customer_type_picked` - With customer type
3. `playbook_tier_shown` - With recommended build
4. `case_chosen` - With selected case
5. `upsell_chosen` - With RAM/storage changes
6. `rgb_tweaked` - With ARGB preferences
7. `ar_opened` - AR viewer opened
8. `drop_off` - Session ended

---

## Progressive Disclosure Strategy

### Registration Flow (Once)

**Minimal signup** (required):
- Email
- Password (or magic link option)
- Name

**Optional at signup**:
- Year of birth (with clear consent)
- Marketing opt-in
- How did you find us?

**Can be updated later** via PATCH /auth/me

### Buying Flow (Per Order)

**During wizard** (budget → type → tier):
- Journey context captured automatically
- No user input required

**Before configurator**:
- "Is this for you or a gift?"
- If gift: recipient age band

**During configuration**:
- Aesthetic preference (quiet vs RGB)
- First PC vs upgrade?
- If upgrade: current GPU

**Before checkout**:
- Urgency (ASAP / this week / flexible)
- Discreet packaging?
- Business buyer? VAT invoice?

---

## Integration Points

### When to Enforce Auth

**Not required**:
- Browse curated builds
- Use wizard (budget → type → tier)
- View build details
- Add to cart

**Required before**:
- Checkout / payment
- Saving configuration
- Accessing order history

**Pattern** (recommended):
```typescript
// In checkout page/component
useEffect(() => {
  if (!isAuthenticated()) {
    // Show signup/login modal or redirect to /auth/signup
    // Pass return_to parameter to come back after auth
  }
}, [])
```

### Linking Auth to Analytics

When user authenticates:
```typescript
// After successful signup/login
const { access_token } = await signup(...)
storeToken(access_token)

// Get customer profile
const customer = await getMe(access_token)

// Store customer ID for analytics
localStorage.setItem('flipflop_customer_id', customer.id.toString())

// Now all analytics events include customer_id
```

---

## Data Flow Diagram

```
User Journey
     ↓
┌─────────────────────────────────────────┐
│ 1. Budget Selection                     │
│    updateBuyingFlowData({ budget... })  │
│    trackEvent('budget_chosen', ...)     │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ 2. Customer Type Selection              │
│    updateBuyingFlowData({ type... })    │
│    trackEvent('customer_type_picked')   │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ 3. Tier Selection                       │
│    updateBuyingFlowData({ tier... })    │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ 4. View Matching Builds                 │
│    trackEvent('playbook_tier_shown')    │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ 5. Progressive Questions                │
│    - Gift? Discreet packaging?          │
│    - First PC? Aesthetic preference?    │
│    updateBuyingFlowData({ ...answers }) │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ 6. Configure (case, RGB, AR)            │
│    trackEvent('case_chosen', ...)       │
│    trackEvent('rgb_tweaked', ...)       │
│    trackEvent('ar_opened', ...)         │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ 7. Checkout (auth required)             │
│    - If not auth: signup/login          │
│    - Create order with buying_flow data │
└─────────────────────────────────────────┘
     ↓
  Order Created
  (all data stored)
```

---

## Testing Checklist

### Backend
- [ ] Run alembic migration: `alembic upgrade head`
- [ ] Test POST /auth/signup with optional fields
- [ ] Test PATCH /auth/me for profile updates
- [ ] Test GET /auth/me returns new fields
- [ ] Test POST /api/public/analytics/event with buying_flow
- [ ] Verify customer and order tables have new columns

### Frontend
- [ ] Auth functions work (signup, login, getMe, updateProfile)
- [ ] Token storage/retrieval works
- [ ] Buying flow data persists in sessionStorage
- [ ] Analytics events include buying_flow context
- [ ] customer_id is included in events after auth

### Integration
- [ ] Wizard updates buying flow data automatically
- [ ] Progressive questions update buying flow data
- [ ] All analytics events sent to backend successfully
- [ ] Auth required before checkout
- [ ] Order creation includes all buying flow data

---

## Skipped (Per Requirements)

- Full address (collected during shipping, not registration)
- Gender (not collected)
- Detailed job title (not collected)
- Magic link implementation (schema ready, logic TBD)

---

## Next Steps

1. **Frontend UI Components**:
   - Signup/login modal or pages
   - Progressive buying flow questions (gift, packaging, etc.)
   - Auth gate before checkout

2. **Magic Link Auth**:
   - Generate and send magic link emails
   - Validate magic link tokens
   - Expire old tokens

3. **Analytics Backend**:
   - Store events in analytics table
   - Dashboard for analytics review
   - Funnel analysis (budget → checkout conversion)

4. **Business Logic**:
   - Birthday offers automation (using year_of_birth)
   - Marketing campaigns (using marketing_opt_in)
   - Age-appropriate recommendations (using age band)

---

## Files Changed

**Backend** (flipflop-api):
- `app/models/customer.py` - Extended Customer model
- `app/models/order.py` - Extended Order model
- `app/routes/auth.py` - Added PATCH /auth/me
- `app/schemas/auth.py` - Updated schemas
- `app/services/auth_service.py` - Updated signup()
- `app/api/public_catalogue.py` - Added POST /api/public/analytics/event
- `app/schemas/buying_flow.py` - NEW: Buying flow schemas
- `alembic/versions/20260921_0001_customer_registration_buying_flow.py` - NEW: Migration

**Frontend** (FlipFlop.shop.new):
- `lib/auth.ts` - NEW: Auth utilities
- `lib/types.ts` - Added BuyingFlowData type
- `lib/analytics.ts` - Enhanced with buying flow context

---

**Status**: ✅ Backend infrastructure complete  
**Ready for**: Frontend UI integration  
**Blockers**: None
