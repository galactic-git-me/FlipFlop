'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { useAuth } from '@/lib/auth';

export default function OAuthCallbackPage() {
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
        setError('Missing authorization code');
        return;
      }

      if (!state) {
        setError('Missing OAuth provider information');
        return;
      }

      try {
        setMessage(`Authenticating with ${state === 'google' ? 'Google' : 'GitHub'}...`);

        let result;
        if (state === 'google') {
          result = await apiClient.oauth.exchangeGoogleCode(code);
        } else if (state === 'github') {
          result = await apiClient.oauth.exchangeGitHubCode(code);
        } else {
          setError('Unknown OAuth provider');
          return;
        }

        if (result?.access_token) {
          setMessage('Login successful. Redirecting...');
          login(result.access_token);
        } else {
          setError('Failed to obtain access token');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Authentication failed');
      }
    };

    handleCallback();
  }, [searchParams, login]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md text-center">
        {error ? (
          <div className="space-y-4">
            <div className="text-red-600 font-semibold text-lg">Authentication Failed</div>
            <div className="text-red-500">{error}</div>
            <a href="/login" className="inline-block mt-4 px-4 py-2 bg-black text-white rounded font-semibold hover:bg-gray-800">
              Back to Login
            </a>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="text-gray-600 text-lg">{message}</div>
            <div className="flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-black"></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
