# FlipFlop Deployment Status

## ✅ Complete Development Stack

### Container Status
```
flipflop-admin-dev     ✅ Running (port 13001)
flipflop-backend-dev   ✅ Running (port 18000)
flipflop-cache-dev     ✅ Running (port 16379)
flipflop-db-dev        ✅ Running (port 15432)
flipflop-web-dev       ✅ Running (port 13000)
```

### Services & URLs

**Storefront (PC Builder)**
- URL: `http://andromeda-ts:13000`
- Hot-reload: ✅ Enabled
- Status: HTTP 200 OK

**Admin Dashboard**
- URL: `http://andromeda-ts:13001`
- Hot-reload: ✅ Enabled
- Status: HTTP 200 OK

**API Backend**
- URL: `http://andromeda-ts:18000`
- Framework: FastAPI with auto-reload
- Status: Running

**Database**
- PostgreSQL 16 on port 15432
- Database: flipflop
- Status: Healthy

**Cache**
- Redis 7 on port 16379
- Status: Healthy

## 🎨 Design System Applied

### Claude Design System Integration
Both storefront and admin now use the premium dark-luxury theme:

**Color Palette:**
- Surface: `#0f1419` (deep charcoal)
- Surface Alt: `#1a1f2b` (cards/panels)
- Surface Raised: `#242a39` (elevation)
- Accent: `#d4af37` (premium gold)
- Hover: `#e8c547` (lighter gold)

**Typography:**
- Headings: Serif (Georgia, Garamond)
- Body: System sans-serif
- Code: Monaco/Courier New

**Components:**
- Buttons: Gold gradient with hover lift
- Cards: Alt surface with gold borders on hover
- Inputs: Focus state with gold glow
- Badges: Status-colored with subtle backgrounds

## 🔧 Development Workflow

### Hot-Reload Enabled
Changes to code files automatically trigger:
- **Next.js** (`npm run dev`) - Instant HMR
- **FastAPI** (uvicorn --reload) - Auto-restart on file changes
- **CSS** - Imported into both apps automatically

### Server Binding
All services bind to `0.0.0.0` and communicate via:
- Internal hostname: `andromeda-ts` (via Docker extra_hosts)
- External access: `localhost` or machine IP + port

### Making Changes

**Frontend (Storefront or Admin):**
```bash
# Edit files in flipflop-storefront/ or flipflop-admin/
# Changes appear instantly in browser (HMR)
```

**Backend API:**
```bash
# Edit files in flipflop-api/
# uvicorn auto-restarts the server
```

**Styles:**
```bash
# Edit app/globals.css in either frontend
# CSS variables apply immediately
# Design system reference: DESIGN_SYSTEM.md
```

## 📋 Quick Commands

```bash
# View all logs
docker compose -f docker-compose.dev.yml logs -f

# Restart specific service
docker compose -f docker-compose.dev.yml restart api

# Full stack restart
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d

# Database shell
docker exec -it flipflop-db-dev psql -U flipper -d flipflop

# Redis CLI
docker exec -it flipflop-cache-dev redis-cli
```

## 🚀 Next Steps

1. **Test the UI**: Visit `http://andromeda-ts:13000` (storefront) and `http://andromeda-ts:13001` (admin)
2. **Review design**: Check that the Claude Design System styling appears (deep charcoal background, gold accents)
3. **Make changes**: Edit any file and confirm hot-reload works
4. **Customize**: Update design tokens in `globals.css` as needed

## 📚 Documentation

- **Design System**: See `DESIGN_SYSTEM.md` for detailed component styling
- **Development Setup**: See `DEV_SETUP.md` for troubleshooting
- **Docker Compose**: See `docker-compose.dev.yml` for service configuration

---

**Last Updated**: 2026-06-29
**Status**: Production-ready development environment
