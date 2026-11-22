# Andromeda production handoff

The repository now contains the full production Compose definition, but the
first deployment needs to be run on Andromeda because Docker is not installed
on the Windows development machine and Tailscale SSH may require interactive
authentication.

## One-time server preparation

Create the dedicated admin JWT secret file on Andromeda before deploying. It
is shared only with the API and admin containers; do not commit it or copy it
to a developer workstation:

```bash
mkdir -p runtime
python3 - <<'PY'
from pathlib import Path
import secrets
path = Path("runtime/admin-auth.env")
path.write_text(f"ADMIN_JWT_SECRET={secrets.token_urlsafe(48)}\n")
path.chmod(0o600)
PY
```

Keep this file stable across deploys. Admin JWTs expire after 12 hours; existing
admin sessions must sign in again after changing this key. Customer and guest
portal token signing and licence-key encryption use the separate `SECRET_KEY`.
For a controlled rotation, set the new strong value as `SECRET_KEY` and retain
the old value as `SECRET_KEY_PREVIOUS`. New tokens and encrypted values use the
current key; verification/decryption accepts the previous key for existing
data. Remove `SECRET_KEY_PREVIOUS` only after old customer and guest tokens
have expired and stored licence/eBay credentials have been re-encrypted. The
production workflow rotates a too-short key atomically before deployment and
never prints either key.

If an older production `.env.local` has no explicit `SECRET_KEY`, the guarded
rotation step provisions a new strong key and retains the historical built-in
fallback as `SECRET_KEY_PREVIOUS`. This preserves verification/decryption for
existing values while ensuring the new production configuration uses an
explicit key. A previous key without a current key still stops the release for
manual review.

The production checkout must contain the storefront repository at either:

```text
/home/mac/CODING/FlipFlop.shop
/home/mac/CODING/FlipFlop-production/FlipFlop.shop
```

The default compose context expects the first path. If the checkout is absent,
clone `galactic-git-me/FlipFlop.shop` beside the production checkout using the
server's existing GitHub credentials.

Install the Caddy entries from:

```text
deploy/andromeda.Caddyfile.example
```

They proxy:

```text
theflipflop.shop       -> 127.0.0.1:3020
admin.theflipflop.shop -> 127.0.0.1:3021
```

After editing Caddy, validate and reload it:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Deployment

The normal route is the GitHub Actions **Deploy production** workflow. For a
direct server-side deployment of a known SHA:

```bash
cd /home/mac/CODING/FlipFlop-production
./deploy/deploy-andromeda.sh <commit-sha>
```

The script refuses to deploy if the storefront checkout is missing. It builds
API, Gem Radar, storefront, and admin, applies migrations, starts the complete
compose project, and checks ports 4311, 3020, and 3021 plus both public URLs.

Runtime secrets remain on Andromeda. Do not copy Windows `.env` files into the
production checkout without reviewing the credential matrix first.
