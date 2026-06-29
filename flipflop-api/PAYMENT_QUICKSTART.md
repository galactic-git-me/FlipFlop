# Payment Integration Quick Start

## 30-Minute Setup Guide

### Step 1: Install Stripe Package (2 minutes)

```bash
cd flipflop-api
pip install stripe
```

### Step 2: Get Stripe API Keys (5 minutes)

1. Go to https://dashboard.stripe.com/apikeys
2. Copy **Secret Key** (starts with `sk_test_`)
3. Copy **Publishable Key** (starts with `pk_test_`)

### Step 3: Configure Environment (3 minutes)

Create or update `flipflop-api/.env` or `flipflop-api/.env.local`:

```bash
# Stripe
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE

# Email (if not already configured)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@flipflop.co.uk
```

### Step 4: Start Backend (2 minutes)

```bash
cd flipflop-api
uvicorn app.main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 5: Test Payment Intent (3 minutes)

```bash
curl -X POST http://localhost:8000/api/payments/intent \
  -H "Content-Type: application/json" \
  -d '{
    "budget": 1200.00,
    "customer_id": 1
  }'
```

Expected response (201 Created):
```json
{
  "client_secret": "pi_1234567890_secret_...",
  "publishable_key": "pk_test_...",
  "amount": 1200.00,
  "currency": "gbp",
  "intent_id": "pi_1234567890"
}
```

### Step 6: Test Payment Confirmation (5 minutes)

```bash
curl -X POST http://localhost:8000/api/payments/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "intent_id": "pi_1234567890",
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
  "payment_intent_id": "pi_1234567890",
  "created_at": "2024-06-29T12:00:00Z"
}
```

Order created! Check it:
```bash
curl http://localhost:8000/api/orders/42
```

## Testing with Frontend (Stripe Elements)

### Install Stripe.js (in frontend)

```bash
npm install @stripe/js @stripe/react-stripe-js
```

### Add Payment Form

```tsx
import { loadStripe } from '@stripe/js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';

const stripePromise = loadStripe('pk_test_YOUR_KEY');

export function CheckoutForm() {
  const stripe = useStripe();
  const elements = useElements();
  const [clientSecret, setClientSecret] = useState('');

  // Step 1: Create payment intent
  const handleCreateIntent = async () => {
    const res = await fetch('/api/payments/intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        budget: 1200.00,
        customer_id: 1,
      }),
    });
    const data = await res.json();
    setClientSecret(data.client_secret);
  };

  // Step 2: Confirm payment
  const handlePay = async () => {
    const { paymentIntent } = await stripe!.confirmCardPayment(clientSecret, {
      payment_method: {
        card: elements!.getElement(CardElement)!,
      },
    });

    if (paymentIntent.status === 'succeeded') {
      // Step 3: Confirm with backend
      const res = await fetch('/api/payments/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intent_id: paymentIntent.id,
          customer_id: 1,
        }),
      });
      const order = await res.json();
      console.log('Order created:', order.order_id);
    }
  };

  return (
    <Elements stripe={stripePromise}>
      <button onClick={handleCreateIntent}>Start Payment</button>
      {clientSecret && (
        <>
          <CardElement />
          <button onClick={handlePay}>Pay £1200.00</button>
        </>
      )}
    </Elements>
  );
}
```

## Testing Webhooks Locally (Optional)

### Install Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Linux
curl https://files.stripe.com/stripe-cli/releases/linux/v1.19.2/stripe_linux_x86_64.tar.gz | tar xz
sudo mv stripe /usr/local/bin

# Windows
choco install stripe-cli
```

### Forward Webhooks to Local Backend

Terminal 1: Start backend
```bash
cd flipflop-api
uvicorn app.main:app --reload
```

Terminal 2: Forward webhooks
```bash
stripe login
stripe listen --forward-to localhost:8000/api/webhooks/stripe
```

Copy the signing secret (whsec_...) and add to .env:
```bash
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET
```

Terminal 3: Trigger test webhook
```bash
stripe trigger payment_intent.succeeded
```

Check logs for:
```
webhook.payment_intent.succeeded
webhook.order.created
webhook.email.sent
```

## Test Credit Cards

| Card | Result | Notes |
|------|--------|-------|
| 4242 4242 4242 4242 | Succeeds | Standard test card |
| 4000 0000 0000 0002 | Declines | Card declined |
| 4000 0000 0000 9995 | Requires 3D Secure | Advanced testing |

**Expiry**: Any future date (e.g., 12/26)
**CVC**: Any 3 digits (e.g., 123)

## Troubleshooting

### "Missing STRIPE_SECRET_KEY"
```bash
# Check .env file
grep STRIPE_SECRET_KEY flipflop-api/.env.local flipflop-api/.env

# Add to .env.local if missing
echo "STRIPE_SECRET_KEY=sk_test_..." >> flipflop-api/.env.local
```

### "Customer not found"
```bash
# Ensure customer exists with ID 1
curl http://localhost:8000/api/customers/1

# If not, create a customer first
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!",
    "name": "Test User"
  }'
```

### "Webhook signature invalid"
```bash
# Check STRIPE_WEBHOOK_SECRET matches stripe-cli output
grep STRIPE_WEBHOOK_SECRET flipflop-api/.env.local

# Compare with output from:
stripe listen --forward-to localhost:8000/api/webhooks/stripe
```

### "Email not sent"
```bash
# Check SMTP configuration
grep SMTP flipflop-api/.env.local

# For Gmail, use app password (not regular password)
# https://support.google.com/accounts/answer/185833
```

## Running Tests

```bash
# Unit tests
pytest flipflop-api/tests/test_payment_flow.py -v

# With coverage
pytest flipflop-api/tests/test_payment_flow.py --cov=app.services.payment_service --cov=app.routes.payments

# Specific test
pytest flipflop-api/tests/test_payment_flow.py::TestPaymentService::test_create_payment_intent_success -v
```

## Next Steps

1. ✓ Complete the 30-minute setup above
2. Test payment flow with curl
3. Integrate frontend with Stripe Elements
4. Configure webhook in Stripe dashboard (production)
5. Deploy to production with live keys

## API Reference Quick Links

- **Create Payment Intent**: `POST /api/payments/intent`
  - Docs: http://localhost:8000/docs#/payments/create_payment_intent_api_payments_intent_post

- **Confirm Payment**: `POST /api/payments/confirm`
  - Docs: http://localhost:8000/docs#/payments/confirm_payment_api_payments_confirm_post

- **Check Status**: `GET /api/payments/status/{intent_id}`
  - Docs: http://localhost:8000/docs#/payments/get_payment_status_api_payments_status__intent_id__get

- **Issue Refund**: `POST /api/payments/refund`
  - Docs: http://localhost:8000/docs#/payments/refund_payment_api_payments_refund_post

## Documentation

- Full docs: `PAYMENT_IMPLEMENTATION.md`
- Testing guide: `PAYMENT_VERIFICATION.md`
- Complete summary: `TASKS_9_10_SUMMARY.md`

## Support

All code includes structured logging. Check logs:

```bash
tail -f logs/flipflop.log | grep -E "payment|webhook|stripe"
```

Look for:
- `payment_intent.created` - Payment intent created
- `payment_intent.succeeded` - Payment succeeded
- `webhook.payment_intent.succeeded` - Webhook received
- `webhook.order.created` - Order created from webhook
- `webhook.email.sent` - Confirmation email sent

## Gotchas

1. **Test vs Live Keys**: Always use `sk_test_` and `pk_test_` in development
2. **Webhook Secret**: Changes when you restart `stripe listen`
3. **Email Requires SMTP**: Payment works without email, but confirmations won't send
4. **Idempotent Orders**: Same intent_id won't create duplicate orders (good!)
5. **Currency**: Always GBP (British Pounds), amounts in pence to Stripe

## Done!

Your payment system is now operational. Proceed with:
- Frontend integration
- Production Stripe key setup
- Webhook endpoint configuration in Stripe dashboard
