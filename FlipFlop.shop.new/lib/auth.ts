/**
 * Authentication utilities for FlipFlop.shop
 * Reuses existing auth system from flipflop-api
 */

export interface Customer {
  id: number
  email: string
  name: string
  last_login: string | null
  created_at: string
  year_of_birth: number | null
  marketing_opt_in: boolean
  acquisition_source: string | null
}

export interface SignupData {
  email: string
  password?: string | null  // Optional for magic link
  name: string
  year_of_birth?: number | null
  marketing_opt_in?: boolean
  acquisition_source?: string | null
  acquisition_detail?: string | null
}

export interface LoginData {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api'

/**
 * Sign up a new customer
 */
export async function signup(data: SignupData): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Signup failed')
  }

  return response.json()
}

/**
 * Log in an existing customer
 */
export async function login(data: LoginData): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Login failed')
  }

  return response.json()
}

/**
 * Get current customer profile
 */
export async function getMe(token: string): Promise<Customer> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw new Error('Failed to fetch profile')
  }

  return response.json()
}

/**
 * Update customer profile (progressive disclosure)
 */
export async function updateProfile(
  token: string,
  updates: Partial<{
    name: string
    year_of_birth: number
    marketing_opt_in: boolean
    acquisition_source: string
    acquisition_detail: string
  }>
): Promise<Customer> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(updates),
  })

  if (!response.ok) {
    throw new Error('Failed to update profile')
  }

  return response.json()
}

// Keep returned access tokens in memory. Do not persist them in browser storage.
