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

  oauth: {
    async getGoogleAuthUrl() {
      const res = await fetch(`${API_URL}/auth/oauth/google/url`);
      if (!res.ok) throw new Error('Failed to get Google auth URL');
      return res.json();
    },

    async getGitHubAuthUrl() {
      const res = await fetch(`${API_URL}/auth/oauth/github/url`);
      if (!res.ok) throw new Error('Failed to get GitHub auth URL');
      return res.json();
    },

    async exchangeGoogleCode(code: string) {
      const res = await fetch(`${API_URL}/auth/oauth/google/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) throw new Error('Google auth failed');
      return res.json();
    },

    async exchangeGitHubCode(code: string) {
      const res = await fetch(`${API_URL}/auth/oauth/github/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) throw new Error('GitHub auth failed');
      return res.json();
    },
  }
};
