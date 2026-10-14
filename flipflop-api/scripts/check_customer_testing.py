"""Validate customer-test configuration without contacting providers."""
import sys
from pathlib import Path
from sqlalchemy.engine import make_url

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
from app.config import Settings

settings = Settings(_env_file=(API / '.env', API / '.env.local'))
errors = []
if make_url(settings.database_url).host not in ('localhost', '127.0.0.1', '::1'):
    errors.append('Customer testing requires a local development database')
if not settings.stripe_secret_key.startswith('sk_test_') or not settings.stripe_publishable_key.startswith('pk_test_'):
    errors.append('Configure matching Stripe test-mode secret and publishable keys')
if not settings.stripe_webhook_secret:
    errors.append('Configure the development Stripe webhook signing secret')
if not settings.email_sandbox_recipient:
    errors.append('Configure EMAIL_SANDBOX_RECIPIENT before customer testing')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('Customer-test configuration valid: local database, Stripe test keys, webhook and email redirect')
