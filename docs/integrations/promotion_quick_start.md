# Curated Set Promotion: Quick Start

**For**: Michael & team  
**Purpose**: Promote approved curated playbooks from dev to production without re-clicking

---

## TL;DR

Michael's Approve clicks in dev = **dev sign-off only**. Run these commands to promote to production:

```bash
# 1. Export from dev
cd flipflop-api
python scripts/promote_curated_to_production.py export --output ./manifest.json

# 2. Copy to andromeda-ts
scp manifest.json andromeda:/home/mac/FlipFlop/

# 3. Dry-run on andromeda-ts (ALWAYS FIRST!)
ssh andromeda
cd /home/mac/FlipFlop/flipflop-api
python scripts/promote_curated_to_production.py import --manifest ../manifest.json --dry-run

# 4. Apply to production (after verification)
python scripts/promote_curated_to_production.py import --manifest ../manifest.json --no-dry-run
```

After promotion:
- ✅ Curated builds live on FlipFlop.shop
- ✅ Only new/changed SKUs require re-approval
- ✅ BuildBot/PricingBot/MeshyBot write directly to prod

---

## What Gets Promoted

1. **Curated playbooks** (24 builds: FF-GVG-01 through FF-FAM-03)
2. **Ship names** (BuildBot stamped, ids 122-145: Reliant, Defiant, Voyager, etc.)
3. **Pricing** (approved sells + upsell deltas, ids 66-89)
4. **Photo packs** (pending - scaffolded for future)
5. **3D assets** (pending - scaffolded for future)

---

## Safety Features

- ✅ **Dry-run by default** - Must explicitly use `--no-dry-run` to apply
- ✅ **Environment check** - Verifies production before applying
- ✅ **Manifest hash** - SHA256 verification prevents corruption
- ✅ **Interactive confirm** - Requires typing "yes" for live import
- ✅ **Audit trail** - All promotions logged in database

---

## Admin API (Alternative to CLI)

```http
# Export
POST /api/admin/curated-promotion/export
Authorization: Bearer <admin-token>
{
  "include_playbooks": true,
  "include_pricing": true
}

# Import (dry-run)
POST /api/admin/curated-promotion/import
Authorization: Bearer <admin-token>
{
  "manifest": {...},
  "dry_run": true
}

# View history
GET /api/admin/curated-promotion/history
Authorization: Bearer <admin-token>
```

---

## Troubleshooting

### "Not production environment"
- Check you're on andromeda-ts: `hostname`
- Verify env vars: `echo $APP_ENV` (should be "production")

### "Manifest hash mismatch"
- File corrupted during transfer
- Re-export and transfer again

### Playbooks not showing
- Check API: `curl https://www.theflipflop.shop/api/public/curated-builds | jq`
- Restart API: `docker compose -f deploy/andromeda-api.compose.yml restart api`

---

## Files & Locations

**Dev** (local):
```
flipflop-api/
├── data/curated_build_definitions.json  ← 24 playbooks
├── tmp/ship-name-map.json               ← BuildBot stamped (ids 122-145)
└── data/ship_names.json                 ← Ship metadata
```

**Production** (andromeda-ts):
```
/home/mac/FlipFlop/flipflop-api/
├── data/curated_build_definitions.json  ← Promoted here
├── tmp/ship-name-map.json               ← Promoted here
└── data/ship_names.json                 ← Promoted here
```

---

## Full Documentation

See `CURATED_PROMOTION_GUIDE.md` for complete guide including:
- Detailed workflow
- API endpoint documentation
- Database schema
- Bot workflow after promotion
- Troubleshooting guide
- Future enhancements

---

## Questions?

Contact: Michael or check `CURATED_PROMOTION_GUIDE.md`
