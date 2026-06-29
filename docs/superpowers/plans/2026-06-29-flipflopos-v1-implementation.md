# FlipFlopOS v1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hybrid made-to-order and speculative PC builder platform with 3D configurator, quote engine, order management, and automated welcome guide generation.

**Architecture:** 
- **flipflop-storefront** (Next.js) handles customer 3D configuration, budget entry, OS/theme selection, payment
- **flipflop-api** (FastAPI) manages orders, quotes, sourcing, build recommendations, PDF generation
- **flipflop-admin** (React/Next.js) for operator build tracking and QA
- **PostgreSQL** stores all transactional data
- **Claude API** powers gem build recommendations

**Tech Stack:**
- Frontend: Next.js 16, React, TypeScript, Three.js (3D), Tailwind + CDS
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Database: PostgreSQL
- Payment: Stripe
- PDF: ReportLab
- LLM: Claude API (Sonnet)
- Deployment: Docker Compose (dev), Kubernetes-ready (prod)

**Timeline:** 6-8 weeks to MVP launch

---

# Phase 1: Foundation & Auth (Week 1-1.5)

## File Structure

**New directories:**
```
flipflop-storefront/
  app/
    (auth)/          # Auth routes
      login/
      signup/
      logout/
    (dashboard)/     # Customer dashboard
      page.tsx
      builds/
    configurator/
      page.tsx
  components/
    3d-viewport.tsx
    budget-slider.tsx
    component-picker.tsx
    price-sidebar.tsx
    auth-forms.tsx
  lib/
    api-client.ts
    3d-loader.ts
    types.ts

flipflop-api/
  app/
    models/
      customer.py
      order.py
      component.py
      os_component.py
      desktop_theme.py
      welcome_guide.py
    schemas/
      auth.py
      order.py
      component.py
    routes/
      auth.py
      orders.py
      components.py
    services/
      auth_service.py
      email_service.py

flipflop-admin/
  app/
    (auth)/
      login/
    (dashboard)/
      page.tsx
      orders/
      qa/
  components/
    order-card.tsx
    sourcing-approval.tsx
    qa-form.tsx
```

---

### Task 1: Set Up Database Schema & Migrations

**Files:**
- Create: `flipflop-api/app/models/__init__.py`
- Create: `flipflop-api/app/models/base.py`
- Create: `flipflop-api/app/models/customer.py`
- Create: `flipflop-api/alembic/versions/0001_initial_schema.py`
- Modify: `flipflop-api/app/database.py`

**Steps:**

- [ ] **Step 1: Create base model class**

File: `flipflop-api/app/models/base.py`

```python
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 2: Create Customer model**

File: `flipflop-api/app/models/customer.py`

```python
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Customer(BaseModel):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
```

- [ ] **Step 3: Create alembic migration**

File: `flipflop-api/alembic/versions/001_initial_schema.py`

```python
"""Initial schema: Customer table"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500)),
        sa.Column('phone', sa.String(20)),
        sa.Column('last_login', sa.DateTime),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

def downgrade():
    op.drop_table('customers')
```

- [ ] **Step 4: Run migration**

```bash
cd flipflop-api
alembic upgrade head
```

Expected: Migration applies successfully, customers table created in DB.

- [ ] **Step 5: Commit**

```bash
git add flipflop-api/app/models/ flipflop-api/alembic/versions/001_initial_schema.py
git commit -m "feat: add customer model and initial migration"
```

---

### Task 2: Implement Authentication API (Signup/Login)

**Files:**
- Create: `flipflop-api/app/schemas/auth.py`
- Create: `flipflop-api/app/routes/auth.py`
- Create: `flipflop-api/app/services/auth_service.py`
- Modify: `flipflop-api/app/main.py` (add auth routes)
- Create: `flipflop-api/requirements.txt` (add passlib, python-jose, bcrypt)

**Steps:**

- [ ] **Step 1: Add auth dependencies**

File: `flipflop-api/requirements.txt` (add these lines)

```
passlib[bcrypt]>=1.7.4
python-jose[cryptography]>=3.3.0
pydantic>=2.0.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Create auth schemas**

File: `flipflop-api/app/schemas/auth.py`

```python
from pydantic import BaseModel, EmailStr

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class CustomerResponse(BaseModel):
    id: int
    email: str
    name: str
    
    class Config:
        from_attributes = True
```

- [ ] **Step 3: Create auth service**

File: `flipflop-api/app/services/auth_service.py`

```python
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.schemas.auth import SignupRequest, LoginRequest

SECRET_KEY = "your-secret-key-change-in-prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 168

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)
    
    @staticmethod
    def create_access_token(email: str) -> str:
        expires = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        data = {"sub": email, "exp": expires}
        return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> str:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub")
        except JWTError:
            return None
    
    @staticmethod
    def signup(db: Session, request: SignupRequest) -> Customer:
        # Check if email exists
        existing = db.query(Customer).filter(Customer.email == request.email).first()
        if existing:
            raise ValueError("Email already registered")
        
        customer = Customer(
            email=request.email,
            password_hash=AuthService.hash_password(request.password),
            name=request.name
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    
    @staticmethod
    def login(db: Session, request: LoginRequest) -> Customer:
        customer = db.query(Customer).filter(Customer.email == request.email).first()
        if not customer or not AuthService.verify_password(request.password, customer.password_hash):
            raise ValueError("Invalid email or password")
        
        customer.last_login = datetime.utcnow()
        db.commit()
        return customer
```

- [ ] **Step 4: Create auth routes**

File: `flipflop-api/app/routes/auth.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, CustomerResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    try:
        customer = AuthService.signup(db, request)
        token = AuthService.create_access_token(customer.email)
        return {"access_token": token}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        customer = AuthService.login(db, request)
        token = AuthService.create_access_token(customer.email)
        return {"access_token": token}
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/me", response_model=CustomerResponse)
async def get_current_user(token: str, db: Session = Depends(get_db)):
    email = AuthService.verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    customer = db.query(Customer).filter(Customer.email == email).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer
```

- [ ] **Step 5: Add routes to main app**

File: `flipflop-api/app/main.py` (add at startup)

```python
from app.routes.auth import router as auth_router

app.include_router(auth_router)
```

- [ ] **Step 6: Test signup endpoint**

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","name":"Test User"}'
```

Expected: Returns `{"access_token": "eyJ...", "token_type": "bearer"}`

- [ ] **Step 7: Commit**

```bash
git add flipflop-api/app/schemas/auth.py flipflop-api/app/services/auth_service.py flipflop-api/app/routes/auth.py flipflop-api/requirements.txt
git commit -m "feat: implement authentication (signup/login)"
```

---

### Task 3: Build Customer Frontend Auth Pages

**Files:**
- Create: `flipflop-storefront/app/(auth)/signup/page.tsx`
- Create: `flipflop-storefront/app/(auth)/login/page.tsx`
- Create: `flipflop-storefront/lib/api-client.ts`
- Create: `flipflop-storefront/lib/auth.ts`

**Steps:**

- [ ] **Step 1: Create API client**

File: `flipflop-storefront/lib/api-client.ts`

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = {
  async signup(email: string, password: string, name: string) {
    const res = await fetch(`${API_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name }),
    });
    if (!res.ok) throw new Error('Signup failed');
    return res.json();
  },

  async login(email: string, password: string) {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error('Login failed');
    return res.json();
  },

  async getMe(token: string) {
    const res = await fetch(`${API_URL}/auth/me?token=${token}`);
    if (!res.ok) throw new Error('Failed to get user');
    return res.json();
  },
};
```

- [ ] **Step 2: Create auth hook**

File: `flipflop-storefront/lib/auth.ts`

```typescript
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export function useAuth() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('auth_token');
    if (stored) setToken(stored);
    setLoading(false);
  }, []);

  const login = useCallback((newToken: string) => {
    localStorage.setItem('auth_token', newToken);
    setToken(newToken);
    router.push('/');
  }, [router]);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setToken(null);
    router.push('/login');
  }, [router]);

  return { token, loading, login, logout, isAuthenticated: !!token };
}
```

- [ ] **Step 3: Create signup page**

File: `flipflop-storefront/app/(auth)/signup/page.tsx`

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { useAuth } from '@/lib/auth';

export default function SignupPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({ email: '', password: '', name: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await apiClient.signup(formData.email, formData.password, formData.name);
      login(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold mb-8 text-center">Build Your Perfect PC</h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-700 rounded">{error}</div>}
          
          <input
            type="text"
            placeholder="Name"
            value={formData.name}
            onChange={(e) => setFormData({...formData, name: e.target.value})}
            className="w-full px-4 py-3 border rounded"
            required
          />
          
          <input
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={(e) => setFormData({...formData, email: e.target.value})}
            className="w-full px-4 py-3 border rounded"
            required
          />
          
          <input
            type="password"
            placeholder="Password"
            value={formData.password}
            onChange={(e) => setFormData({...formData, password: e.target.value})}
            className="w-full px-4 py-3 border rounded"
            required
          />
          
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white py-3 rounded font-semibold hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? 'Creating account...' : 'Sign up'}
          </button>
        </form>
        
        <p className="mt-4 text-center text-gray-600">
          Already have an account? <a href="/login" className="text-black font-semibold">Log in</a>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create login page**

File: `flipflop-storefront/app/(auth)/login/page.tsx`

```typescript
'use client';

import { useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({ email: '', password: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await apiClient.login(formData.email, formData.password);
      login(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold mb-8 text-center">Welcome back</h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-700 rounded">{error}</div>}
          
          <input
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={(e) => setFormData({...formData, email: e.target.value})}
            className="w-full px-4 py-3 border rounded"
            required
          />
          
          <input
            type="password"
            placeholder="Password"
            value={formData.password}
            onChange={(e) => setFormData({...formData, password: e.target.value})}
            className="w-full px-4 py-3 border rounded"
            required
          />
          
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white py-3 rounded font-semibold hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? 'Logging in...' : 'Log in'}
          </button>
        </form>
        
        <p className="mt-4 text-center text-gray-600">
          New here? <a href="/signup" className="text-black font-semibold">Create account</a>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Test auth flow**

1. Start storefront: `npm run dev`
2. Navigate to `http://localhost:3000/signup`
3. Sign up with test credentials
4. Should redirect to home page

- [ ] **Step 6: Commit**

```bash
git add flipflop-storefront/lib/api-client.ts flipflop-storefront/lib/auth.ts flipflop-storefront/app/\(auth\)/
git commit -m "feat: implement customer auth (signup/login pages)"
```

---

## Phase 2: Core Models & Quote Engine (Week 2-2.5)

Due to length constraints, I'll summarize the remaining phases with key tasks. The full plan would include similar detailed steps for:

### Task 4-6: Create remaining models (Component, OSComponent, DesktopTheme, Order, WelcomeGuide, Playbook)
- Create SQLAlchemy models for each entity
- Create corresponding Alembic migrations
- Create Pydantic schemas for request/response

### Task 7-8: Implement Quote Engine
- Create quote calculation service (budget → recommended specs)
- Implement component selection endpoints
- Real-time price calculation

### Task 9-10: Add Payment Integration
- Stripe integration
- Payment processing endpoint
- Order creation after successful payment

---

## Phase 3: 3D Configurator Frontend (Week 3-4)

### Task 11-12: Build 3D viewport
- Integrate Three.js
- Load 3D models (Meshy AI models)
- Real-time rotation/zoom

### Task 13-14: Component picker UI
- Budget slider
- Component selection interface
- Stock status indicators
- Smart alternatives suggestions

### Task 15: Real-time pricing sidebar
- Display component prices
- Calculate total
- Show labor + overhead

---

## Phase 4: OS & Theme Selection (Week 4-5)

### Task 16-17: OS selection & license key management
- Windows/Linux toggle
- License key inventory
- Assignment logic

### Task 18-19: Desktop theme selection
- 10 theme options with previews
- Theme data storage
- Rainmeter configuration management

---

## Phase 5: Welcome Guide Generator (Week 5-6)

### Task 20-21: PDF generation service
- Create dynamic PDF per order
- BIOS settings section
- Component overview
- Troubleshooting guide
- License key inclusion
- Save to DB and filesystem

---

## Phase 6: Admin Dashboard (Week 6-7)

### Task 22-25: Build operator interface
- Order queue dashboard
- Sourcing approval interface
- QA checklist and photo uploads
- Build status management
- Email notifications on status change

---

## Phase 7: LLM Build Generator (Week 7-8)

### Task 26-28: Implement gem build recommendations
- Integrate Claude API
- Catalogue analysis
- Market price comparison
- Suggest high-profit builds
- Admin UI for recommendations

---

## Phase 8: Testing & Launch (Week 8)

### Task 29-32: End-to-end testing
- Full customer flow (signup → configure → pay → receive)
- Admin workflow (order receipt → sourcing → build → QA → ship)
- Payment handling
- Email notifications

---

# Execution Strategy

**Total estimated tasks:** 32 major tasks + micro-steps = ~150-200 individual steps

**Phased delivery:**
1. **Week 1-2:** Foundation (auth, database, basic APIs)
2. **Week 2-4:** Quote & payment engine
3. **Week 4-6:** 3D configurator, OS/theme selection
4. **Week 6-7:** Welcome guide & admin tools
5. **Week 7-8:** LLM gem builder, final testing & refinement

**Deployment:**
- Dev: Docker Compose (local testing)
- Staging: Single server (final QA)
- Prod: Kubernetes (scalable)

---

# Success Criteria for MVP Launch

- ✅ Customers can signup/login
- ✅ Budget → quote calculation works
- ✅ 3D configurator displays and allows component selection
- ✅ Real-time pricing accurate
- ✅ OS selection (Windows/Linux) functional
- ✅ Windows license key assignment working
- ✅ 10 themes available, selectable
- ✅ Payment processing (Stripe) working
- ✅ Orders created and stored
- ✅ Operator can view order queue
- ✅ Sourcing approval interface functional
- ✅ QA checklist works, status updates trigger emails
- ✅ Welcome guide auto-generates on QA pass
- ✅ Customer receives welcome guide PDF
- ✅ Customer dashboard shows order history + status tracking
- ✅ LLM suggests gem builds (admin tool)
- ✅ No critical bugs in e2e flow

