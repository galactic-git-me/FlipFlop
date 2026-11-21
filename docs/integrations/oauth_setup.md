# OAuth2 Authentication Setup Guide

This document describes how to set up and test OAuth2 authentication with Google and GitHub for the FlipFlop application.

## Implementation Summary

OAuth2 authentication has been added to both the backend (FastAPI) and frontend (Next.js) with the following features:

1. **Google OAuth** - Users can sign up/login with their Google account
2. **GitHub OAuth** - Users can sign up/login with their GitHub account
3. **Account Linking** - OAuth accounts can be linked to existing email-based accounts
4. **Fallback Support** - Full email/password authentication still works alongside OAuth

## Backend Implementation

### Database Schema Changes

The `customers` table has been extended with OAuth fields:

```sql
- google_id (String, unique) - Google user ID
- google_email (String) - Email from Google profile
- github_id (Integer, unique) - GitHub user ID
- github_username (String) - GitHub username
- oauth_provider (String) - Provider type: 'google', 'github', or NULL for email-only
```

**Migration File**: `flipflop-api/alembic/versions/20260629_0013_customer_oauth_fields.py`

### New Backend Files

1. **`flipflop-api/app/services/oauth_service.py`**
   - `OAuthService` class handles OAuth provider integration
   - Methods for Google/GitHub authentication flow
   - User creation/linking logic

2. **`flipflop-api/app/routes/oauth.py`**
   - OAuth endpoints:
     - `GET /auth/oauth/google/url` - Get Google auth URL
     - `GET /auth/oauth/github/url` - Get GitHub auth URL
     - `POST /auth/oauth/google/callback` - Handle Google callback
     - `POST /auth/oauth/github/callback` - Handle GitHub callback

### Modified Backend Files

1. **`flipflop-api/app/models/customer.py`** - Added OAuth columns
2. **`flipflop-api/app/config.py`** - Added OAuth configuration variables
3. **`flipflop-api/app/main.py`** - Registered OAuth router

## Frontend Implementation

### New Frontend Files

1. **`flipflop-storefront/app/(auth)/callback/page.tsx`**
   - Handles OAuth provider callbacks
   - Exchanges authorization code for JWT token
   - Handles loading states and errors
   - Automatically redirects to home on success

### Modified Frontend Files

1. **`flipflop-storefront/lib/api-client.ts`** - Added OAuth methods:
   - `oauth.getGoogleAuthUrl()` - Get Google auth URL
   - `oauth.getGitHubAuthUrl()` - Get GitHub auth URL
   - `oauth.exchangeGoogleCode(code)` - Exchange Google code
   - `oauth.exchangeGitHubCode(code)` - Exchange GitHub code

2. **`flipflop-storefront/app/(auth)/signup/page.tsx`** - Added:
   - Google sign-up button with SVG logo
   - GitHub sign-up button with SVG logo
   - Visual divider between OAuth and email signup
   - Loading states for OAuth flows

3. **`flipflop-storefront/app/(auth)/login/page.tsx`** - Added:
   - Google login button
   - GitHub login button
   - Visual divider between OAuth and email login
   - Loading states for OAuth flows

## Setup Instructions

### Step 1: Register OAuth Applications

#### Google OAuth Setup

1. Go to https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Web application" as the application type
4. Add authorized redirect URIs:
   - Development: `http://localhost:3000/auth/callback`
   - Production: `https://yourdomain.com/auth/callback`
5. Copy the Client ID and Client Secret

#### GitHub OAuth Setup

1. Go to https://github.com/settings/developers → "New OAuth App"
2. Fill in application details:
   - Application name: FlipFlop
   - Homepage URL: `http://localhost:3000` (or your domain)
   - Authorization callback URL: `http://localhost:3000/auth/callback`
3. Copy the Client ID and Client Secret

### Step 2: Configure Environment Variables

#### Backend (.env)

Add the following to `flipflop-api/.env`:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback
```

**Important**: Never commit these credentials to version control. Use `.env.local` for local development.

#### Frontend Configuration

The frontend uses:
- `NEXT_PUBLIC_API_URL` environment variable (already configured)
- Redirect URI is hardcoded as `http://localhost:3000/auth/callback`

Update the frontend redirect URI in OAuth apps if using a different domain.

### Step 3: Run Database Migration

The OAuth fields will be automatically added when the application starts:

```bash
cd flipflop-api
alembic upgrade head
```

Or the migration runs automatically on FastAPI startup.

### Step 4: Start the Application

#### Backend
```bash
cd flipflop-api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd flipflop-storefront
npm install
npm run dev
```

## Testing OAuth Flows

### Manual Testing

1. **Google Sign-Up**
   - Navigate to http://localhost:3000/signup
   - Click "Sign up with Google"
   - Authorize the application
   - Should redirect to home page and be logged in

2. **GitHub Sign-Up**
   - Navigate to http://localhost:3000/signup
   - Click "Sign up with GitHub"
   - Authorize the application
   - Should redirect to home page and be logged in

3. **Account Linking**
   - Sign up with email/password with email: `test@example.com`
   - Log out
   - Click "Login with Google" and authorize with a Google account using `test@example.com`
   - Account should be linked (same customer record)
   - OAuth fields updated in database

4. **Regular Email Login**
   - All existing email/password flows continue to work
   - Both OAuth and email auth can coexist

### Testing Checklist

- [ ] Google OAuth sign-up creates new account
- [ ] GitHub OAuth sign-up creates new account
- [ ] Google OAuth login works with existing account
- [ ] GitHub OAuth login works with existing account
- [ ] Account linking: email → Google OAuth
- [ ] Account linking: email → GitHub OAuth
- [ ] Callback page handles errors gracefully
- [ ] JWT token is created and stored correctly
- [ ] User can access protected endpoints with OAuth token

## API Endpoints Reference

### Get OAuth URLs (Frontend calls these)

**Get Google Auth URL**
```
GET /api/auth/oauth/google/url

Response:
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

**Get GitHub Auth URL**
```
GET /api/auth/oauth/github/url

Response:
{
  "url": "https://github.com/login/oauth/authorize?..."
}
```

### Handle OAuth Callbacks

**Google Callback**
```
POST /api/auth/oauth/google/callback
Content-Type: application/json

{
  "code": "authorization_code_from_google"
}

Response:
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

**GitHub Callback**
```
POST /api/auth/oauth/github/callback
Content-Type: application/json

{
  "code": "authorization_code_from_github"
}

Response:
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

## User Flow Diagrams

### Sign-Up Flow

```
User clicks "Sign up with Google"
    ↓
Frontend fetches Google auth URL from backend
    ↓
Redirects user to Google consent screen
    ↓
User authorizes FlipFlop
    ↓
Google redirects to /auth/callback with authorization code
    ↓
Callback page exchanges code for user info
    ↓
Calls backend OAuth endpoint
    ↓
Backend creates/links customer account
    ↓
Returns JWT token
    ↓
Callback page stores token in localStorage
    ↓
User is logged in and redirected home
```

### Login Flow (Existing Account)

```
User clicks "Login with Google"
    ↓
Same as sign-up flow above
    ↓
Backend finds existing account by google_id
    ↓
Returns JWT token for existing account
    ↓
User is logged in
```

### Account Linking Flow

```
User has email account: test@example.com
    ↓
Clicks "Login with Google"
    ↓
Authorizes with Google account using test@example.com
    ↓
Backend finds customer by email
    ↓
Links Google account to existing customer
    ↓
Updates google_id, google_email, oauth_provider fields
    ↓
Returns JWT token
    ↓
Same customer now has both email/password and Google auth
```

## Security Considerations

1. **CSRF Protection**: OAuth state parameter not used in current implementation (implicit trust in callback page). For production, implement CSRF token exchange.

2. **Redirect URI Validation**: Ensure OAuth apps are configured with exact redirect URIs matching deployment environment.

3. **Secret Management**: Never commit `.env` files containing OAuth secrets. Use environment variables or secure secret management systems in production.

4. **Token Validation**: JWT tokens are validated on protected endpoints using the existing auth middleware.

5. **Password for OAuth Users**: OAuth users get a placeholder password ("oauth-provider") in the database to maintain schema compatibility.

## Troubleshooting

### Google OAuth Issues

- **Invalid redirect_uri**: Ensure the redirect URI in Google Console matches exactly (including protocol and port)
- **"Unauthorized_client"**: Check that Client ID and Client Secret are correct
- **"access_denied"**: User clicked "Cancel" on consent screen

### GitHub OAuth Issues

- **"Bad verification code"**: Authorization code expired or invalid (valid for 10 minutes)
- **"Redirect_uri_mismatch"**: Ensure GitHub OAuth app redirect URI matches exactly
- **Empty email**: GitHub may not provide email; application generates fallback email

### Database Issues

- **Migration not running**: Check Alembic configuration and database connection
- **Unique constraint violations**: Check for duplicate google_id or github_id values
- **Column not found**: Ensure migration 20260629_0013 has run

## Environment-Specific Configuration

### Development

- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Redirect URI: `http://localhost:3000/auth/callback`

### Production

Replace with your actual domain:
- API: `https://api.yourdomain.com`
- Frontend: `https://yourdomain.com`
- Redirect URI: `https://yourdomain.com/auth/callback`

Update OAuth apps in Google Console and GitHub to use production redirect URI.

## References

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
