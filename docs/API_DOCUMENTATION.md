@'@'@'@@@@# FlipFlop API Documentation

## Base URL

```
https://api.flipflop.example.com
```

## Public customer support assistant

### POST /api/public/support/chat

Answer general customer questions from the approved support knowledge base and the labelled customer-safe Software Playbook section. This endpoint does not access customer accounts, orders, tracking, payments or warranty cases. Order-specific information belongs in the authenticated customer portal.

**Request:**

```json
{
  "message": "Are the recommended software apps required?",
  "history": [
    { "role": "user", "content": "I am choosing a new PC." },
    { "role": "assistant", "content": "What will you use it for?" }
  ]
}
```

The message is limited to 1,600 characters; history is limited to eight user/assistant messages of at most 1,200 characters each.

**Response (200):**

```json
{
  "answer": "The recommended apps are optional. You can add or remove approved apps before your software choices lock.",
  "sources": [
    { "name": "FlipFlop first-line support knowledge base", "version": "1.4", "reviewed_at": "2026-09-29", "section": "Approved customer support guidance" },
    { "name": "FlipFlop Software Playbook", "version": "1.1", "reviewed_at": "2026-09-29", "section": "Customer-safe software recommendations" }
  ]
}
```

**Errors:** `422` for invalid input; `503` if the approved sources or configured LLM are unavailable.

## Authentication

All protected endpoints require a JWT token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

## Response Format

All responses follow this format:

```json
{
  "data": { /* response data */ },
  "error": null,
  "message": "Success"
}
```

Error responses:

```json
{
  "detail": "Error description"
}
```

---

## Curated Playbook inventory (admin)

### POST /api/curated-builds/auto-link-bestseller-components

Resolve each saved Playbook slot's Amazon bestseller identity to an active supplier listing in the same Playbook slot. Matching uses the product ASIN associated with its CPK first, then an exact listing CPK. If a matching listing is not yet marked for the Curated Catalogue, it is linked for stock and price visibility but still requires Curated approval before publishing. Among equivalent active offers, an already-curated listing is preferred, followed by the lowest price.

**Response (200):**

```json
{
  "linked": 11,
  "unmatched": 176,
  "linked_needs_curation": 11,
  "segments_updated": 6
}
```

This endpoint requires admin authentication. It does not curate new listings or publish Playbook segments.

### GET /api/public/playbooks/{playbook_id}/curated-slots?build_id={curated_build_id}

Returns the Playbook recommendation and customer-selectable options for each component slot. RAM and storage capacity choices come from the curated catalogue; additional substitutions are returned only when the curated cell is live and the offer was reviewed by an administrator.

Reviewed alternatives include `approved_upgrade` evidence (candidate, price delta, approved bestseller match, and CPU/GPU benchmark comparison where available). Customers submit the selected `variant_id` in `slot_selections`; checkout revalidates the variant against the active curated catalogue and prices it from the current listing. The legacy `upgrade_candidate_indexes` field remains accepted for existing clients.

Publishing a curated cell requires at least one reviewed offer for every component category that has a drafted upgrade. Each offer must match an active curated target and approved exact-model popularity evidence; CPU/GPU offers also need equal-or-better use-case benchmark evidence.

## Auth Endpoints

### POST /auth/signup

Create a new customer account.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "name": "John Doe"
}
```

**Response (201):**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Errors:**

- `409`: Email already registered
- `422`: Invalid input (email format, password strength)

---

### POST /auth/login

Authenticate customer and get access token.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200):**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Errors:**

- `401`: Invalid email or password

---

## OAuth2 Endpoints

### POST /oauth/google/callback

Complete Google OAuth2 login.

**Request:**

```json
{
  "code": "4/0AX4XfWg..."
}
```

**Response (200):**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Errors:**

- `400`: Invalid code
- `401`: Token verification failed

---

### POST /oauth/github/callback

Complete GitHub OAuth2 login.

**Request:**

```json
{
  "code": "ghu_16C7e42F292c6912E7..."
}
```

**Response (200):**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

---

## Quotes Endpoints

### POST /quotes/generate

Generate a PC configuration quote within budget.

**Request:**

```json
{
  "budget": 1500.0
}
```

**Response (200):**

```json
{
  "id": 1,
  "customer_id": 1,
  "budget": 1500.0,
  "total_price": 1450.50,
  "components": [
    {
      "id": 10,
      "type": "CPU",
      "name": "Intel Core i7-13700K",
      "price": 420.00,
      "specs": {
        "cores": 16,
        "threads": 24,
        "tdp": 125
      }
    },
    {
      "id": 20,
      "type": "GPU",
      "name": "RTX 4070",
      "price": 599.00,
      "specs": {
        "vram": 12,
        "cuda_cores": 5888
      }
    },
    {
      "id": 30,
      "type": "RAM",
      "name": "Corsair Vengeance DDR5 32GB",
      "price": 150.00,
      "specs": {
        "capacity": 32,
        "speed": 6000,
        "type": "DDR5"
      }
    },
    {
      "id": 40,
      "type": "SSD",
      "name": "Samsung 990 Pro 2TB",
      "price": 180.00,
      "specs": {
        "capacity": 2000,
        "interface": "NVMe",
        "speed": 7100
      }
    },
    {
      "id": 50,
      "type": "PSU",
      "name": "Corsair RM1000x Gold",
      "price": 180.00,
      "specs": {
        "wattage": 1000,
        "efficiency": "80+ Gold"
      }
    },
    {
      "id": 60,
      "type": "Case",
      "name": "NZXT H7 Flow",
      "price": 150.00,
      "specs": {
        "form_factor": "ATX",
        "drive_bays": 4
      }
    },
    {
      "id": 70,
      "type": "Cooler",
      "name": "Noctua NH-D15",
      "price": 110.00,
      "specs": {
        "type": "Air",
        "socket_support": ["LGA1700"]
      }
    }
  ],
  "created_at": "2026-06-29T10:30:00Z"
}
```

**Errors:**

- `401`: Unauthorized
- `422`: Invalid budget (must be > 0)

---

## Orders Endpoints

### POST /orders/create

Create a new order with custom configuration.

**Request:**

```json
{
  "budget": 1500.0,
  "components": {
    "cpu_id": 10,
    "gpu_id": 20,
    "ram_id": 30,
    "ssd_id": 40,
    "psu_id": 50,
    "case_id": 60,
    "cooler_id": 70
  },
  "os_id": 1,
  "theme_id": 2
}
```

**Response (201):**

```json
{
  "id": 1,
  "customer_id": 1,
  "status": "pending_payment",
  "budget": 1500.0,
  "total_price": 1450.50,
  "os_id": 1,
  "theme_id": 2,
  "components": [
    {
      "id": 10,
      "type": "CPU",
      "name": "Intel Core i7-13700K"
    }
  ],
  "created_at": "2026-06-29T10:30:00Z",
  "updated_at": "2026-06-29T10:30:00Z"
}
```

**Errors:**

- `401`: Unauthorized
- `422`: Invalid component IDs

---

### GET /orders

List all customer orders.

**Query Parameters:**

- `status`: Filter by status (pending_payment, sourcing, building, shipping, delivered)
- `limit`: Results per page (default: 20, max: 100)
- `offset`: Pagination offset (default: 0)

**Response (200):**

```json
{
  "orders": [
    {
      "id": 1,
      "status": "sourcing",
      "budget": 1500.0,
      "total_price": 1450.50,
      "created_at": "2026-06-29T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Errors:**

- `401`: Unauthorized

---

### GET /orders/{order_id}

Get order details.

**Response (200):**

```json
{
  "id": 1,
  "customer_id": 1,
  "status": "sourcing",
  "budget": 1500.0,
  "total_price": 1450.50,
  "os_id": 1,
  "theme_id": 2,
  "components": [
    {
      "id": 10,
      "type": "CPU",
      "name": "Intel Core i7-13700K",
      "price": 420.00
    }
  ],
  "created_at": "2026-06-29T10:30:00Z",
  "updated_at": "2026-06-29T11:00:00Z"
}
```

**Errors:**

- `401`: Unauthorized
- `404`: Order not found

---

### Welcome Guide — `/api/guides/orders/{order_id}`

Guide generation (`POST .../generate`), download (`GET .../download`) and status (`GET .../status`) require a Bearer token. Account tokens must belong to the order's customer; guest portal tokens are limited to their granted order. Guest tokens can read/download an existing guide but cannot regenerate it. Downloads are private/no-store. Legacy guide PDFs are regenerated before serving so an older PDF cannot disclose a Windows product key.

Example download:

```http
GET /api/guides/orders/{order_id}/download
Authorization: Bearer <customer-or-order-scoped-guest-token>
```

**Response (200):**

- Content-Type: `application/pdf`
- Binary PDF content

**Errors:**

- `401`: Missing or invalid access token
- `403`: Guest token attempted document regeneration
- `404`: Order does not belong to the account, guide not found, or guide unavailable
- `500`: PDF generation failed

---

## Payments Endpoints

### POST /payments/intent

Create Stripe payment intent.

**Request:**

```json
{
  "amount": 1500.0,
  "order_id": 1
}
```

**Response (200):**

```json
{
  "intent_id": "pi_1234567890",
  "client_secret": "pi_1234567890_secret_xyz",
  "amount": 1500.0,
  "currency": "gbp",
  "status": "requires_payment_method"
}
```

**Errors:**

- `401`: Unauthorized
- `404`: Order not found
- `500`: Stripe API error

---

### POST /payments/confirm

Confirm payment (deprecated - use Stripe client library instead).

**Request:**

```json
{
  "payment_intent_id": "pi_1234567890"
}
```

**Response (200):**

```json
{
  "status": "succeeded",
  "order_id": 1
}
```

---

## Webhooks Endpoints

### POST /webhooks/stripe

Handle Stripe webhook events.

**Headers:**

```
Stripe-Signature: t=timestamp,v1=signature
```

**Request:**

```json
{
  "id": "evt_1234567890",
  "type": "payment_intent.succeeded",
  "data": {
    "object": {
      "id": "pi_1234567890",
      "amount": 150000,
      "currency": "gbp",
      "status": "succeeded",
      "metadata": {
        "order_id": "1"
      }
    }
  }
}
```

**Response (200):**

```json
{
  "status": "success",
  "event_id": "evt_1234567890"
}
```

**Errors:**

- `400`: Invalid signature
- `409`: Event already processed

---

## Admin Endpoints

### POST /api/cases/{case_id}/3d-reference-selection

Approve 1–4 distinct product photos for a case, in the order Meshy should use them. The first photo is the primary colour and texture reference. At least one photo is required; Meshy's multi-image endpoint supports at most four.

### POST /api/assets-3d/cases/{case_id}/generate

Create a review-only Meshy draft from the exact currently approved photo selection. The request body includes `image_urls` (1–4 URLs in approved order), a `request_id`, and optional `notes`. One photo is submitted to Meshy's Image-to-3D endpoint; two to four are submitted to Multi-Image-to-3D. Texture generation and PBR are enabled in both modes. The result remains a draft requiring separate model approval.

### GET /admin/orders

List all orders (admin only).

**Query Parameters:**

- `status`: Filter by status
- `customer_id`: Filter by customer
- `limit`: Results per page
- `offset`: Pagination offset

**Response (200):**

```json
{
  "orders": [
    {
      "id": 1,
      "customer_id": 1,
      "customer_email": "user@example.com",
      "status": "sourcing",
      "budget": 1500.0,
      "total_price": 1450.50,
      "created_at": "2026-06-29T10:30:00Z"
    }
  ],
  "total": 100
}
```

**Errors:**

- `401`: Unauthorized
- `403`: Insufficient permissions

---

### POST /admin/orders/{order_id}/approve-sourcing

Approve order for sourcing.

**Response (200):**

```json
{
  "id": 1,
  "status": "building"
}
```

---

### POST /admin/orders/{order_id}/approve-build

Approve order for shipping.

**Response (200):**

```json
{
  "id": 1,
  "status": "shipping"
}
```

---

### POST /admin/orders/{order_id}/mark-delivered

Mark order as delivered.

**Response (200):**

```json
{
  "id": 1,
  "status": "delivered"
}
```

---

## Gems Endpoints

### POST /gems/recommendations

Get LLM-powered gem recommendations.

**Request:**

```json
{
  "order_id": 1,
  "budget": 100.0
}
```

**Response (200):**

```json
{
  "gems": [
    {
      "name": "Premium Thermal Paste",
      "description": "High-performance thermal paste for CPU cooling",
      "price": 45.00,
      "benefit": "Improves CPU temperatures by 5-10°C",
      "priority": "high"
    },
    {
      "name": "Cable Management Kit",
      "description": "Professional cable management solution",
      "price": 35.00,
      "benefit": "Better airflow and cable organization",
      "priority": "medium"
    }
  ]
}
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Unprocessable Entity |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `/auth/login` | 5 per minute |
| `/auth/signup` | 5 per minute |
| `/quotes/generate` | 100 per hour |
| `/orders` | 100 per hour |
| `/webhooks/stripe` | Unlimited (Stripe verified) |

---

## Pagination

List endpoints support pagination:

```
GET /orders?limit=20&offset=0
```

**Response:**

```json
{
  "data": [/* items */],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

---

## Filtering

```
GET /admin/orders?status=sourcing&customer_id=1
```

---

## Status Values

### Order Status

- `pending_payment` - Awaiting payment
- `sourcing` - Components being sourced
- `building` - PC being assembled
- `shipping` - In transit
- `delivered` - Delivered to customer

---

## Examples

### Complete Order Flow

```bash
# 1. Signup
curl -X POST https://api.flipflop.example.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "name": "John Doe"
  }'

# Response:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "token_type": "bearer"
# }

# 2. Generate Quote
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
curl -X POST https://api.flipflop.example.com/quotes/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"budget": 1500.0}'

# 3. Create Order
curl -X POST https://api.flipflop.example.com/orders/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": 1500.0,
    "components": {
      "cpu_id": 10,
      "gpu_id": 20,
      ...
    },
    "os_id": 1,
    "theme_id": 2
  }'

# 4. Get Welcome Guide
curl -X GET https://api.flipflop.example.com/api/guides/orders/1/download \
  -H "Authorization: Bearer $TOKEN" \
  --output welcome-guide.pdf
```

---

## SDKs & Libraries

- **JavaScript/TypeScript**: Fetch API or Axios
- **Python**: `requests` or `httpx`
- **Go**: `net/http`
- **Ruby**: `Net::HTTP` or `HTTPClient`

---

## Support

- Email: api-support@flipflop.example.com
- Slack: #api-support
- Status: https://status.flipflop.example.com

---

*Last Updated: 2026-06-29*
*API Version: v1.0*

## Catalogue product guides

- `POST /api/public/product-copy` accepts one of `variant_id` or `case_id`. For an upgrade-specific guide, pass `baseline_variant_id`, or pass `curated_build_id` with `candidate_index` for an approved offer. It returns structured `copy`, its context key, and whether the content is upgrade-specific.
- Copy is generated from the supplier title, scraped description and available specifications, then cached against a source hash. Supplier text is treated as untrusted input; the generated text is plain text and does not invent absent technical claims.
- Missing or changed content is generated on demand through configured local/free model tiers only. A generation failure returns HTTP 503; there is no paid-tier fallback.
- Admin-only `GET /api/catalogue/marketing-copy/status` reports sweep coverage. `POST /api/catalogue/marketing-copy/generate-batch` accepts `{"limit":1..4}` and generates a resumable batch. The admin page is `/catalogue/copy`.
