/** Reads the client-readable admin_token cookie (set alongside the httpOnly
 * admin_session cookie at login — see app/api/session/login/route.ts). Only
 * needed for calls that bypass the Next.js rewrite proxy by hitting the
 * backend at an absolute origin (NEXT_PUBLIC_API_URL); proxied /api/* calls
 * get their Authorization header injected server-side by middleware.ts instead. */
export function getAdminToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)admin_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}
