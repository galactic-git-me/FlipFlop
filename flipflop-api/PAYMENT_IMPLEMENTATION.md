# Payment Integration Implementation

## Overview

This document describes the Stripe payment integration for FlipFlop. The system enables customers to:

1. Generate quotes for custom PC builds
2. Create Stripe payment intents
3. Collect payment via Stripe Elements (frontend)
4. Confirm payment and automatically create orders
5. Receive order confirmation emails

## Architecture

### Payment Flow

```
Customer Quote
    ↓
Generate Quote (POST /api/quotes/generate)
    ↓
Create Payment Intent (POST /api/payments/intent)
    ↓
Frontend: Collect Card Details (Stripe Elements)
    ↓
Confirm Payment (POST /api/payments/confirm)
    ↓
Create Order + Email Confirmation
    ↓
Order Tracking (GET /api/orders/{id})
```

### Components

#### 1. PaymentService (app/services/payment_service.py)

Core service for Stripe integration:

- **create_payment_intent()**: Creates Stripe payment intent
- **handle_payment_success()**: Processes successful payments
- **verify_webhook_signature()**: Validates Stripe webhook signatures
- **refund_payment()**: Issues refunds
- **get_payment_intent()**: Retrieves payment status

```python
payment_service = PaymentService()

# Create payment intent
intent = await payment_service.create_payment_intent(
    customer_id=1,
    budget=1200.00,
    quote_data={}
)

# Handle successful payment
payment = await payment_service.handle_payment_success(
    intent_id="pi_...",
    customer_id=1,
    quote_data={}
)
```

#### 2. Payment Endpoints (app/routes/payments.py)

RESTful API for payment operations:

- `POST /api/payments/intent` - Create payment intent
- `POST /api/payments/confirm` - Confirm payment and create order
- `GET /api/payments/status/{intent_id}` - Check payment status
- `POST /api/payments/refund` - Issue refund

#### 3. Webhook Handler (app/routes/webhooks.py)

Processes Stripe events:

- `POST /api/webhooks/stripe` - Main webhook endpoint
- Handles: `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`

#### 4. Schemas (app/schemas/payment.py)

Pydantic models for request/response validation:

- `CreatePaymentIntentRequest`
- `PaymentIntentResponse`
- `ConfirmPaymentRequest`
- `PaymentConfirmation`
- `PaymentStatusResponse`
- `RefundRequest`
- `RefundResponse`

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Stripe keys from https://dashboard.stripe.com/apikeys
STRIPE_SECRET_KEY=sk_test_... or sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_test_... or pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_... (from webhook settings)

# SMTP for confirmation emails
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@flipflop.co.uk
```

### Stripe Setup

1. **Get API Keys**:
   - Go to https://dashboard.stripe.com/apikeys
   - Copy Secret Key (sk_test_* or sk_live_*)
   - Copy Publishable Key (pk_test_* or pk_live_*)

2. **Configure Webhook**:
   - Go to https://dashboard.stripe.com/webhooks
   - Create endpoint: POST https://yourdomain.com/api/webhooks/stripe
   - Select events: `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`
   - Copy webhook secret (whsec_*)
   - Save to `STRIPE_WEBHOOK_SECRET` in `.env`

3. **Local Testing**:
   ```bash
   # Install Stripe CLI: https://stripe.com/docs/stripe-cli
   brew install stripe/stripe-cli/stripe  # macOS
   # or download from https://github.com/stripe/stripe-cli
   
   # Login to Stripe account
   stripe login
   
   # Forward webhooks to local server
   stripe listen --forward-to localhost:8000/api/webhooks/stripe
   
   # Copy signing secret from output and set STRIPE_WEBHOOK_SECRET
   ```

## API Documentation

### 1. Create Payment Intent

**Endpoint**: `POST /api/payments/intent`

**Request**:
```json
{
  "budget": 1200.00,
  "customer_id": 1
}
```

**Response** (201 Created):
```json
{
  "client_secret": "pi_1234567890_secret_abc123",
  "publishable_key": "pk_test_1234567890",
  "amount": 1200.00,
  "currency": "gbp",
  "intent_id": "pi_1234567890"
}
```

**Errors**:
- 404: Customer not found
- 400: Invalid budget or Stripe error

### 2. Confirm Payment

**Endpoint**: `POST /api/payments/confirm`

**Request**:
```json
{
  "intent_id": "pi_1234567890",
  "customer_id": 1
}
```

**Response** (201 Created):
```json
{
  "order_id": 42,
  "status": "awaiting_sourcing",
  "amount": 1200.00,
  "currency": "gbp",
  "payment_intent_id": "pi_1234567890",
  "created_at": "2024-06-29T12:00:00Z"
}
```

**Actions**:
- Creates Order in database
- Sends confirmation email to customer
- Sets order status to `awaiting_sourcing`

**Errors**:
- 404: Customer not found
- 400: Payment not succeeded or invalid intent ID
- 500: Order creation failed

### 3. Get Payment Status

**Endpoint**: `GET /api/payments/status/{intent_id}`

**Response**:
```json
{
  "intent_id": "pi_1234567890",
  "status": "succeeded",
  "amount": 1200.00,
  "currency": "gbp",
  "created_at": "2024-06-29T12:00:00Z"
}
```

**Errors**:
- 404: Payment intent not found

### 4. Refund Payment

**Endpoint**: `POST /api/payments/refund`

**Request**:
```json
{
  "intent_id": "pi_1234567890",
  "reason": "customer_request"
}
```

**Response**:
```json
{
  "refund_id": "re_1234567890",
  "amount": 1200.00,
  "status": "succeeded",
  "reason": "customer_request"
}
```

**Errors**:
- 400: No charge found or refund failed

### 5. Stripe Webhook

**Endpoint**: `POST /api/webhooks/stripe`

**Headers Required**:
- `stripe-signature`: Stripe signature for verification

**Events Handled**:

#### payment_intent.succeeded
```json
{
  "type": "payment_intent.succeeded",
  "data": {
    "object": {
      "id": "pi_1234567890",
      "status": "succeeded",
      "amount": 120000,
      "currency": "gbp",
      "metadata": {
        "customer_id": "1",
        "budget": "1200"
      }
    }
  }
}
```

**Actions**:
- Creates Order if not already exists
- Sends confirmation email
- Sets status to `awaiting_sourcing`

#### payment_intent.payment_failed
```json
{
  "type": "payment_intent.payment_failed",
  "data": {
    "object": {
      "id": "pi_1234567890",
      "last_payment_error": {
        "code": "card_declined",
        "message": "Your card was declined"
      }
    }
  }
}
```

**Actions**:
- Logs failure for monitoring
- No order created

#### charge.refunded
```json
{
  "type": "charge.refunded",
  "data": {
    "object": {
      "id": "ch_1234567890",
      "amount_refunded": 120000
    }
  }
}
```

**Actions**:
- Logs refund event
- (Future: Update order status)

**Response**:
- 200 OK: Webhook processed
- 400 Bad Request: Invalid signature or payload
- 500 Internal Error: Processing error

## Frontend Integration

### Example (React + TypeScript)

```typescript
import { loadStripe } from '@stripe/js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';

const stripePromise = loadStripe(publishableKey);

function PaymentForm() {
  const stripe = useStripe();
  const elements = useElements();
  const [clientSecret, setClientSecret] = useState('');
  const [customerId, setCustomerId] = useState(1);
  const [budget, setBudget] = useState(1200.00);

  // Step 1: Create payment intent
  async function handleCreateIntent() {
    const response = await fetch('/api/payments/intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        budget,
        customer_id: customerId,
      }),
    });
    const data = await response.json();
    setClientSecret(data.client_secret);
  }

  // Step 2: Confirm payment
  async function handleConfirmPayment() {
    const { error, paymentIntent } = await stripe?.confirmCardPayment(
      clientSecret,
      {
        payment_method: {
          card: elements!.getElement(CardElement)!,
        },
      }
    ) || {};

    if (error) {
      console.error(error.message);
      return;
    }

    // Step 3: Confirm with backend
    const response = await fetch('/api/payments/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent_id: paymentIntent.id,
        customer_id: customerId,
      }),
    });

    const data = await response.json();
    console.log('Order created:', data.order_id);
    // Redirect to order confirmation page
  }

  return (
    <Elements stripe={stripePromise}>
      <div>
        <input
          type="number"
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          placeholder="Budget (GBP)"
        />
        <button onClick={handleCreateIntent}>Create Payment Intent</button>

        {clientSecret && (
          <>
            <CardElement />
            <button onClick={handleConfirmPayment}>Pay £{budget.toFixed(2)}</button>
          </>
        )}
      </div>
    </Elements>
  );
}
```

## Database Schema

The payment integration uses existing models:

**Customer** (app/models/customer.py):
- `id`: Primary key
- `email`: Email address
- `name`: Customer name

**Order** (app/models/order.py):
- `id`: Primary key
- `order_id`: Unique reference (ORD-{intent_id})
- `customer_id`: Foreign key to Customer
- `customer_price`: Total price in GBP
- `status`: `awaiting_sourcing` (initial state)
- `notes`: Payment details
- `created_at`: Creation timestamp

## Testing

### Unit Tests

```python
# Test payment service
pytest tests/test_payment_flow.py::TestPaymentService -v

# Test payment endpoints
pytest tests/test_payment_flow.py::TestPaymentEndpoints -v

# Test webhook handlers
pytest tests/test_payment_flow.py::TestPaymentWebhooks -v
```

### Manual Testing (Local)

1. **Install Stripe CLI**:
   ```bash
   stripe login
   stripe listen --forward-to localhost:8000/api/webhooks/stripe
   ```

2. **Start backend**:
   ```bash
   cd flipflop-api
   uvicorn app.main:app --reload
   ```

3. **Test payment intent creation**:
   ```bash
   curl -X POST http://localhost:8000/api/payments/intent \
     -H "Content-Type: application/json" \
     -d '{"budget": 1200.00, "customer_id": 1}'
   ```

4. **Test with Stripe test card**:
   - Card: `4242 4242 4242 4242`
   - Expiry: `12/26` (any future date)
   - CVC: `123` (any 3 digits)

5. **Test webhook locally**:
   ```bash
   stripe trigger payment_intent.succeeded
   ```

## Error Handling

### Payment Intent Creation Errors

- **STRIPE_API_KEY not configured**: 400 Bad Request
- **Invalid budget**: 400 Bad Request
- **Stripe API error**: 400 Bad Request with details

### Payment Confirmation Errors

- **Customer not found**: 404 Not Found
- **Payment not succeeded**: 400 Bad Request
- **Order creation failed**: 500 Internal Server Error

### Webhook Errors

- **Missing stripe-signature**: 400 Bad Request
- **Invalid signature**: 400 Bad Request
- **Invalid payload**: 400 Bad Request

## Security Considerations

1. **API Keys**:
   - Secret key never sent to frontend
   - Publishable key is public (safe to expose)
   - Always use HTTPS in production

2. **Webhook Verification**:
   - All webhooks verified using signature
   - Replayed webhooks prevented by checking if order exists
   - Webhook secret stored in environment (never in code)

3. **PCI Compliance**:
   - Card details never touch backend
   - Collected by Stripe Elements (PCI-DSS compliant)
   - Backend only processes payment intents

4. **CSRF Protection**:
   - FastAPI CORS middleware configured
   - Frontend origin validation (FRONTEND_URL in config)

## Monitoring & Logging

All payment operations logged:

```
payment_intent.created
payment_intent.succeeded
payment.refunded
webhook.payment_intent.succeeded
webhook.order.created
webhook.email.sent
```

View logs:
```bash
# In production/staging
tail -f logs/flipflop.log | grep payment
```

## Troubleshooting

### Payment Intent Not Created
- Check STRIPE_SECRET_KEY in .env
- Verify customer exists in database
- Check Stripe dashboard for API errors

### Webhook Not Received
- Verify STRIPE_WEBHOOK_SECRET is correct
- Check webhook endpoint in Stripe dashboard
- Ensure backend is running and accessible
- Use `stripe listen --forward-to` for local testing

### Order Not Created After Payment
- Check webhook logs
- Verify order status in database
- Check customer_id in webhook metadata

### Email Not Sent
- Verify SMTP configuration in .env
- Check email service logs
- Ensure customer email is valid

## Next Steps

1. **Frontend Integration**:
   - Integrate Stripe Elements into quote checkout
   - Add loading states and error handling
   - Display order confirmation

2. **Admin Dashboard**:
   - View payment history
   - Issue refunds
   - Export transaction reports

3. **Enhanced Features**:
   - Automatic invoice generation
   - Payment plan support (installments)
   - Subscription orders
   - Multi-currency support

4. **Compliance**:
   - EU GDPR compliance for payment data
   - PCI-DSS audit
   - WCAG accessibility audit

## References

- Stripe API Docs: https://stripe.com/docs/api
- Stripe Testing: https://stripe.com/docs/testing
- Stripe CLI: https://stripe.com/docs/stripe-cli
- FastAPI: https://fastapi.tiangolo.com
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
