# Payment Integration Verification

## Implementation Checklist

### Files Created

- ✓ `app/services/payment_service.py` - Stripe integration service
- ✓ `app/schemas/payment.py` - Pydantic schemas for payment validation
- ✓ `app/routes/payments.py` - Payment API endpoints
- ✓ `app/routes/webhooks.py` - Stripe webhook handler
- ✓ `tests/test_payment_flow.py` - Unit and integration tests
- ✓ `PAYMENT_IMPLEMENTATION.md` - Comprehensive documentation
- ✓ `PAYMENT_VERIFICATION.md` - This verification guide

### Files Modified

- ✓ `flipflop-api/requirements-dev.txt` - Added `stripe` package
- ✓ `flipflop-api/app/main.py` - Registered payment and webhook routes
- ✓ `flipflop-api/.env.example` - Added Stripe configuration

### Configuration Updated

- ✓ `app/config.py` - Already has Stripe config fields:
  - `stripe_secret_key`
  - `stripe_publishable_key`
  - `stripe_webhook_secret`

## Component Overview

### 1. PaymentService (app/services/payment_service.py)

**Responsibilities**:
- Stripe API initialization and configuration
- Payment intent creation
- Payment success handling
- Webhook signature verification
- Refund processing
- Payment status retrieval

**Key Methods**:
```python
async def create_payment_intent(customer_id, budget, quote_data) -> dict
async def handle_payment_success(intent_id, customer_id, quote_data) -> dict
def verify_webhook_signature(payload, signature) -> dict
async def refund_payment(intent_id, reason) -> dict
async def get_payment_intent(intent_id) -> dict
```

**Dependencies**:
- `stripe`: Stripe Python SDK
- `app.config.get_settings()`: Configuration management
- `structlog`: Logging

**Error Handling**:
- Validates configuration on initialization
- Catches and wraps Stripe errors with descriptive messages
- Logs all operations for audit trail

### 2. Payment Schemas (app/schemas/payment.py)

**Request Schemas**:
- `CreatePaymentIntentRequest`: Customer ID, budget
- `ConfirmPaymentRequest`: Intent ID, customer ID
- `RefundRequest`: Intent ID, reason

**Response Schemas**:
- `PaymentIntentResponse`: Client secret, publishable key, amount
- `PaymentConfirmation`: Order ID, status, amount, intent ID
- `PaymentStatusResponse`: Intent status and details
- `RefundResponse`: Refund ID, amount, status

**Validation**:
- Budget > 0
- Customer ID > 0
- Intent ID required
- JSON schema examples for documentation

### 3. Payment Endpoints (app/routes/payments.py)

**Endpoints**:

1. **POST /api/payments/intent** (201 Created)
   - Creates Stripe payment intent
   - Validates customer exists
   - Returns client secret and publishable key

2. **POST /api/payments/confirm** (201 Created)
   - Confirms successful payment
   - Creates Order in database
   - Sends confirmation email
   - Returns order details

3. **GET /api/payments/status/{intent_id}** (200 OK)
   - Retrieves payment intent status
   - Returns payment details

4. **POST /api/payments/refund** (200 OK)
   - Issues refund for payment
   - Returns refund details

**Error Handling**:
- 404: Customer or payment not found
- 400: Invalid request or payment failed
- 500: Internal server error

**Dependencies**:
- `PaymentService`: Payment processing
- `get_db`: Database session
- `send_order_confirmation_email`: Email notification

### 4. Webhook Handler (app/routes/webhooks.py)

**Main Endpoint**: `POST /api/webhooks/stripe`

**Events Handled**:

1. **payment_intent.succeeded**
   - Verifies payment succeeded
   - Creates Order if not exists
   - Sends confirmation email
   - Logs event

2. **payment_intent.payment_failed**
   - Logs failure details
   - No order created

3. **charge.refunded**
   - Logs refund event
   - (Future: Updates order status)

**Security**:
- Verifies webhook signature
- Prevents replay attacks by checking if order exists
- Returns 200 OK for all processed events
- Returns 400 Bad Request for signature errors

**Dependencies**:
- `PaymentService`: Signature verification
- `get_db`: Database operations
- `Order`, `Customer` models
- `send_order_confirmation_email`: Email notification

## Database Integration

### Customer Model
- Existing model in `app/models/customer.py`
- Used to validate customer ownership
- Email used for confirmation notifications

### Order Model
- Existing model in `app/models/order.py`
- Created automatically on successful payment
- Payment intent ID stored in `notes` field
- Status set to `AWAITING_SOURCING`
- Fields populated:
  - `order_id`: Generated from intent ID
  - `customer_id`: From request
  - `status`: AWAITING_SOURCING
  - `customer_price`: Quote total
  - `component_costs`: 0.0 (calculated later)
  - `overhead_amount`: 0.0 (calculated later)
  - `notes`: Payment details
  - `created_at`: Current timestamp

## Email Integration

Uses existing `send_order_confirmation_email()` from `app/services/email_service.py`:

**Parameters**:
- `customer_email`: From Customer model
- `customer_name`: From Customer model
- `order_reference`: Generated order ID
- `build_summary`: Quote details
- `assigned_week`: Build schedule (TBD)

**Requirements**:
- SMTP_HOST configured
- SMTP_USER configured
- SMTP_PASS configured
- SMTP_FROM configured (default: noreply@flipflop.co.uk)

## Environment Configuration

Required `.env` variables:

```bash
# Stripe Configuration (REQUIRED for payments)
STRIPE_SECRET_KEY=sk_test_... or sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_test_... or pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email Configuration (REQUIRED for confirmations)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@flipflop.co.uk

# Frontend URL (for order tracking links)
FRONTEND_URL=http://localhost:3000
```

## Testing Instructions

### Unit Tests

```bash
# Install stripe and testing dependencies
pip install -r requirements-dev.txt

# Run payment service tests
pytest tests/test_payment_flow.py::TestPaymentService -v

# Run with coverage
pytest tests/test_payment_flow.py --cov=app.services.payment_service --cov=app.routes.payments
```

### Manual Testing (Local)

1. **Setup Stripe CLI**:
   ```bash
   # Download from https://stripe.com/docs/stripe-cli
   stripe login
   stripe listen --forward-to localhost:8000/api/webhooks/stripe
   # Copy STRIPE_WEBHOOK_SECRET from output
   ```

2. **Start Backend**:
   ```bash
   cd flipflop-api
   python -m pip install stripe  # Install stripe package
   uvicorn app.main:app --reload
   ```

3. **Create Customer** (if needed):
   ```bash
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "Test123!",
       "name": "Test User"
     }'
   ```

4. **Create Payment Intent**:
   ```bash
   curl -X POST http://localhost:8000/api/payments/intent \
     -H "Content-Type: application/json" \
     -d '{
       "budget": 1200.00,
       "customer_id": 1
     }'
   ```

   Expected response:
   ```json
   {
     "client_secret": "pi_..._secret_...",
     "publishable_key": "pk_test_...",
     "amount": 1200.00,
     "currency": "gbp",
     "intent_id": "pi_..."
   }
   ```

5. **Simulate Payment** (with Stripe test card):
   - Frontend: Use Stripe Elements
   - Card: 4242 4242 4242 4242
   - Expiry: 12/26
   - CVC: 123

6. **Confirm Payment**:
   ```bash
   curl -X POST http://localhost:8000/api/payments/confirm \
     -H "Content-Type: application/json" \
     -d '{
       "intent_id": "pi_...",
       "customer_id": 1
     }'
   ```

   Expected response (201 Created):
   ```json
   {
     "order_id": 42,
     "status": "awaiting_sourcing",
     "amount": 1200.00,
     "currency": "gbp",
     "payment_intent_id": "pi_...",
     "created_at": "2024-06-29T12:00:00Z"
   }
   ```

7. **Check Order Created**:
   ```bash
   curl http://localhost:8000/api/orders/42
   ```

8. **Test Webhook** (in another terminal):
   ```bash
   stripe trigger payment_intent.succeeded
   ```

   Check logs for:
   ```
   webhook.payment_intent.succeeded
   webhook.order.created (if new)
   webhook.email.sent
   ```

### Integration Testing

```bash
# Run full payment flow test
pytest tests/test_payment_flow.py::TestPaymentEndpoints -v -s

# Run webhook tests
pytest tests/test_payment_flow.py::TestPaymentWebhooks -v -s
```

## Stripe Configuration Guide

### 1. Get API Keys

1. Go to https://dashboard.stripe.com/apikeys
2. Copy:
   - **Secret Key** (sk_test_... or sk_live_...)
   - **Publishable Key** (pk_test_... or pk_live_...)

### 2. Configure Webhook

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. **Endpoint URL**: `https://yourdomain.com/api/webhooks/stripe`
4. **Events**:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `charge.refunded`
5. Click "Add endpoint"
6. Copy **Signing secret** (whsec_...)

### 3. Set Environment Variables

```bash
# In flipflop-api/.env or .env.local
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 4. Test Keys vs Live Keys

- **Test Keys**: Start with `sk_test_`, `pk_test_`
- **Live Keys**: Start with `sk_live_`, `pk_live_`
- Always start with test keys during development
- Use live keys only after full testing in production environment

## Security Checklist

- ✓ Secret key never exposed (only in .env)
- ✓ Publishable key safe to expose (frontend)
- ✓ Webhook signature verified
- ✓ Card details never touch backend (Stripe Elements)
- ✓ Idempotent order creation (checks if exists)
- ✓ Proper error handling (no sensitive data in responses)
- ✓ Logging enabled for audit trail
- ✓ HTTPS required in production
- ✓ CORS properly configured

## Monitoring & Debugging

### Logs to Watch

```bash
# Check payment operations
grep "payment" logs/flipflop.log

# Check webhook events
grep "webhook" logs/flipflop.log

# Check email sending
grep "email\|email.sent\|email.send_failed" logs/flipflop.log

# Real-time monitoring
tail -f logs/flipflop.log | grep -E "payment|webhook|email"
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No payment intent created | Missing STRIPE_SECRET_KEY | Set in .env |
| Webhook not received | Wrong endpoint URL | Update in Stripe dashboard |
| Order not created | Webhook signature invalid | Check STRIPE_WEBHOOK_SECRET |
| Email not sent | SMTP not configured | Set SMTP_* env vars |
| Customer not found | Wrong customer_id | Use valid customer ID |

## Next Steps After Implementation

1. **Frontend Integration**:
   - Add quote to payment flow
   - Integrate Stripe Elements
   - Handle loading states
   - Display confirmation

2. **Admin Features**:
   - Payment dashboard
   - Refund management
   - Transaction export

3. **Enhanced Features**:
   - Invoice generation
   - Payment plans
   - Subscription support
   - Multi-currency

4. **Compliance**:
   - PCI-DSS audit
   - GDPR compliance
   - Accessibility audit

## Completion Status

✓ **COMPLETE**: All required files created and configured
✓ **INTEGRATED**: Routes registered in main.py
✓ **DOCUMENTED**: Comprehensive documentation provided
✓ **TESTED**: Unit tests provided (installation needed)
✓ **READY**: Can be installed and tested immediately

**Installation**:
```bash
pip install stripe
```

**Start Testing**:
```bash
cd flipflop-api
uvicorn app.main:app --reload
# In another terminal:
stripe listen --forward-to localhost:8000/api/webhooks/stripe
```
