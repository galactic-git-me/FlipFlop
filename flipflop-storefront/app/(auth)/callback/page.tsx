'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { useAuth } from '@/lib/auth';

export const dynamic = 'force-dynamic';

function OAuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [error, setError] = useState('');
  const [message, setMessage] = useState('Authenticating...');

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state'); // 'google' or 'github'

      if (!code) {
        setError('No authorization code received');
        return;
      }

      try {
        let result;

        if (state === 'google') {
          result = await apiClient.oauth.exchangeGoogleCode(code);
        } else if (state === 'github') {
          result = await apiClient.oauth.exchangeGitHubCode(code);
        } else {
          setError('Invalid OAuth provider');
          return;
        }

        if (result && result.token) {
          login(result.token);
          router.push('/');
        } else {
          setError('Authentication failed: no token returned');
        }
      } catch (err) {
        setError(`Authentication failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
    };

    handleCallback();
  }, [searchParams, router, login]);

  if (error) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h1>Authentication Error</h1>
        <p>{error}</p>
        <a href="/login">Back to login</a>
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>{message}</h1>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={<div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>}>
      <OAuthCallbackContent />
    </Suspense>
  );
}
