# FlipFlop v1.0 Deployment Guide

## Overview

This guide covers deploying FlipFlop v1.0 to production, including database setup, secrets configuration, and service startup.

---

## Prerequisites

- Docker & Docker Compose installed
- PostgreSQL 14+ (or use managed service)
- Redis 6+ (for caching)
- Domain name (e.g., flipflop.example.com)
- SSL certificate (from Let's Encrypt or provider)
- Stripe account (live mode)
- Google & GitHub OAuth applications
- Email service provider (SendGrid, AWS SES, etc.)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Users                               │
└──────────────┬──────────────────┬──────────────────┬─────┘
               │                  │                  │
               ▼                  ▼                  ▼
         ┌──────────┐      ┌──────────┐      ┌──────────┐
         │ Storefront│      │  Admin   │      │  API     │
         │(Next.js)  │      │ (Next.js)│      │(FastAPI) │
         └──────────┘      └──────────┘      └──────────┘
               │                  │                  │
               └──────────────────┼──────────────────┘
                                  ▼
                        ┌──────────────────┐
                        │   PostgreSQL     │
                        │    Database      │
                        └──────────────────┘
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
                    ┌────────┐         ┌────────┐
                    │ Redis  │         │ Backups│
                    │(Cache) │         │        │
                    └────────┘         └────────┘
```

---

## Step 1: Database Setup

### Option A: Managed PostgreSQL (Recommended)

Use AWS RDS, Google Cloud SQL, or similar for production.

1. **Create Database Instance**
   ```bash
   # AWS RDS example
   aws rds create-db-instance \
     --db-instance-identifier flipflop-db \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --master-username postgres \
     --allocated-storage 20 \
     --vpc-security-group-ids sg-xxxxxxxx
   ```

2. **Get Connection String**
   ```
   postgresql://user:password@host:5432/flipflop
   ```

3. **Create Database**
   ```bash
   psql "postgresql://user:password@host:5432/postgres" \
     -c "CREATE DATABASE flipflop;"
   ```

### Option B: Docker PostgreSQL

For development/staging:

```yaml
# docker-compose.yml
postgres:
  image: postgres:15
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: ${DB_PASSWORD}
    POSTGRES_DB: flipflop
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 10s
    timeout: 5s
    retries: 5

volumes:
  postgres_data:
```

---

## Step 2: Environment Configuration

### Create `.env.production` File

```bash
# Copy template
cp .env.example .env.production

# Edit with production values
nano .env.production
```

### Required Environment Variables

```env
# Application
ENVIRONMENT=production
DEBUG=False
SECRET_KEY=your-secret-key-min-32-chars-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24

# Database
DATABASE_URL=postgresql://user:password@host:5432/flipflop
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://redis:6379/0

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=info

# Stripe
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# OAuth2 - Google
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_REDIRECT_URI=https://flipflop.example.com/oauth/google/callback

# OAuth2 - GitHub
GITHUB_CLIENT_ID=xxxxx
GITHUB_CLIENT_SECRET=xxxxx
GITHUB_REDIRECT_URI=https://flipflop.example.com/oauth/github/callback

# Email Service
EMAIL_SERVICE=sendgrid  # or ses, smtp, etc.
SENDGRID_API_KEY=SG.xxxxx
SENDER_EMAIL=noreply@flipflop.example.com
SENDER_NAME=FlipFlop

# Logging & Monitoring
SENTRY_DSN=https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
LOG_FORMAT=json

# PDF Generation
PDF_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf

# CORS
ALLOWED_ORIGINS=https://flipflop.example.com,https://admin.flipflop.example.com

# URLs
FRONTEND_URL=https://flipflop.example.com
ADMIN_URL=https://admin.flipflop.example.com
API_URL=https://api.flipflop.example.com
```

### Secure Secret Generation

```bash
# Generate strong secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Step 3: Database Migrations

### Run Migrations

```bash
# Using Alembic
cd flipflop-api
alembic upgrade head

# Or from Docker container
docker exec flipflop-api alembic upgrade head
```

### Verify Migrations

```bash
# Check migration status
alembic current
alembic history

# List all tables
psql $DATABASE_URL -c "\dt"
```

### Create Initial Data (if needed)

```bash
# Load initial OS images, themes, etc.
python scripts/load_initial_data.py
```

---

## Step 4: Docker Image Preparation

### Build Docker Images

```bash
# Build API image
cd flipflop-api
docker build -t flipflop-api:v1.0 .

# Build Storefront image
cd ../flipflop-storefront
docker build -t flipflop-storefront:v1.0 .

# Build Admin image
cd ../flipflop-admin
docker build -t flipflop-admin:v1.0 .
```

### Push to Registry

```bash
# Tag images
docker tag flipflop-api:v1.0 yourregistry/flipflop-api:v1.0
docker tag flipflop-storefront:v1.0 yourregistry/flipflop-storefront:v1.0
docker tag flipflop-admin:v1.0 yourregistry/flipflop-admin:v1.0

# Push to registry
docker push yourregistry/flipflop-api:v1.0
docker push yourregistry/flipflop-storefront:v1.0
docker push yourregistry/flipflop-admin:v1.0
```

---

## Step 5: Deploy Services

### Using Docker Compose (Simple)

```yaml
# docker-compose.production.yml
version: '3.9'

services:
  api:
    image: yourregistry/flipflop-api:v1.0
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy

  storefront:
    image: yourregistry/flipflop-storefront:v1.0
    environment:
      - NEXT_PUBLIC_API_URL=https://api.flipflop.example.com
    ports:
      - "3000:3000"
    restart: unless-stopped

  admin:
    image: yourregistry/flipflop-admin:v1.0
    environment:
      - NEXT_PUBLIC_API_URL=https://api.flipflop.example.com
    ports:
      - "3001:3001"
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: flipflop
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  postgres_data:
```

**Deploy:**

```bash
docker-compose -f docker-compose.production.yml up -d
```

### Using Kubernetes (Advanced)

See `k8s/` directory for Kubernetes manifests.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/storefront-deployment.yaml
kubectl apply -f k8s/admin-deployment.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/redis-deployment.yaml
```

---

## Step 6: Reverse Proxy Configuration

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/flipflop

upstream api {
    server localhost:8000;
}

upstream storefront {
    server localhost:3000;
}

upstream admin {
    server localhost:3001;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name flipflop.example.com api.flipflop.example.com admin.flipflop.example.com;

    return 301 https://$server_name$request_uri;
}

# API Server
server {
    listen 443 ssl http2;
    server_name api.flipflop.example.com;

    ssl_certificate /etc/letsencrypt/live/api.flipflop.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.flipflop.example.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    # CORS headers
    add_header Access-Control-Allow-Origin "https://flipflop.example.com" always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;

    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

# Storefront
server {
    listen 443 ssl http2;
    server_name flipflop.example.com;

    ssl_certificate /etc/letsencrypt/live/flipflop.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/flipflop.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    location / {
        proxy_pass http://storefront;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Admin Dashboard
server {
    listen 443 ssl http2;
    server_name admin.flipflop.example.com;

    ssl_certificate /etc/letsencrypt/live/admin.flipflop.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/admin.flipflop.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    location / {
        proxy_pass http://admin;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable Configuration:**

```bash
# Symlink to enabled sites
sudo ln -s /etc/nginx/sites-available/flipflop /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload
sudo systemctl reload nginx
```

---

## Step 7: SSL Certificate Setup

### Using Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --nginx \
  -d flipflop.example.com \
  -d api.flipflop.example.com \
  -d admin.flipflop.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

---

## Step 8: Health Checks & Monitoring

### Health Check Endpoint

```python
# In app/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": await check_database(),
        "redis": await check_redis(),
    }
```

### Verify Services

```bash
# API
curl https://api.flipflop.example.com/health

# Storefront
curl https://flipflop.example.com/

# Admin
curl https://admin.flipflop.example.com/
```

---

## Step 9: Backup & Recovery

### Database Backup

```bash
# Automated daily backups
crontab -e

# Add:
0 2 * * * pg_dump $DATABASE_URL | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz

# Retention (keep 30 days)
find /backups -name "db-*.sql.gz" -mtime +30 -delete
```

### Test Restore

```bash
# Create test database
createdb flipflop_restore

# Restore backup
gunzip < /backups/db-latest.sql.gz | psql flipflop_restore

# Verify
psql flipflop_restore -c "SELECT COUNT(*) FROM customers;"
```

---

## Step 10: Monitoring & Logging

### Configure Structured Logging

```python
# In app/config.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### Integrate with Sentry

```python
# In app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment=settings.environment,
)
```

---

## Step 11: Performance Optimization

### Database Query Optimization

```sql
-- Create essential indexes
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_quotes_customer_id ON quotes(customer_id);

-- Connection pooling (in FastAPI)
pool_pre_ping=True,
pool_size=20,
max_overflow=10,
```

### Caching Strategy

```python
# Cache quote results
@app.post("/quotes/generate")
async def generate_quote(request: QuoteGenerateRequest, db: AsyncSession):
    cache_key = f"quote:{request.budget}"
    
    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Generate if not cached
    quote = await quote_service.generate(request.budget)
    
    # Cache for 1 hour
    await redis.setex(cache_key, 3600, json.dumps(quote))
    
    return quote
```

---

## Step 12: Verification Checklist

Run before declaring deployment successful:

- [ ] API responds to requests
- [ ] Database migrations completed
- [ ] Health check endpoint returns 200
- [ ] SSL certificate valid
- [ ] HTTPS enforced
- [ ] All secrets loaded (no "None" values)
- [ ] Email sending works
- [ ] Stripe webhook endpoint reachable
- [ ] OAuth2 redirects working
- [ ] PDF generation works
- [ ] No errors in logs
- [ ] Performance metrics acceptable
- [ ] Backups running
- [ ] Monitoring dashboards live

---

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check connection string
echo $DATABASE_URL

# Verify pool settings
# pool_size should be 5-20
# max_overflow should be 5-10
```

### Stripe Webhook Not Delivering

```bash
# Get webhook signing secret from Stripe dashboard
# Verify endpoint URL is reachable
curl -X GET https://api.flipflop.example.com/webhooks/stripe

# Check Stripe dashboard for failed deliveries
# Resend failed events if needed
```

### OAuth Redirect Issues

```bash
# Verify redirect URIs in OAuth app settings
# Redirect URI format: https://domain/oauth/{provider}/callback
# Protocol must match (http vs https)
```

---

## Rollback Procedure

If deployment fails:

```bash
# Rollback application (revert previous Docker image)
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d

# Rollback database (if migrations caused issues)
cd flipflop-api
alembic downgrade -1

# Verify
docker-compose logs api
```

---

## Security Hardening

### Additional Measures

1. **WAF (Web Application Firewall)**
   - Consider AWS WAF or Cloudflare
   - Block known malicious patterns

2. **DDoS Protection**
   - Rate limiting at proxy
   - Cloudflare or similar

3. **Database Security**
   - Encrypt at rest
   - Use VPC security groups
   - Disable public access

4. **API Key Rotation**
   - Stripe: rotate quarterly
   - OAuth: monitor for changes
   - Database: change passwords periodically

---

## Post-Deployment

### Monitor Key Metrics

1. Error rate (target: < 0.1%)
2. API latency (target: < 500ms)
3. Database queries (target: < 100ms)
4. Payment success rate (target: > 98%)
5. Uptime (target: > 99.9%)

### Weekly Tasks

- [ ] Review logs for errors
- [ ] Check backup integrity
- [ ] Review security alerts
- [ ] Monitor database growth
- [ ] Check certificate expiration (30+ days)

---

*Last Updated: 2026-06-29*
*Status: READY FOR PRODUCTION*
