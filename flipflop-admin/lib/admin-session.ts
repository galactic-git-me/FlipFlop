import { jwtVerify, SignJWT } from "jose";

export const ADMIN_SESSION_COOKIE = "admin_session";
export const ADMIN_TOKEN_AUDIENCE = "flipflop-admin";

function getSecret(): Uint8Array {
  const secret = process.env.ADMIN_JWT_SECRET;
  if (!secret) {
    throw new Error("ADMIN_JWT_SECRET is not set (see .env.local)");
  }
  return new TextEncoder().encode(secret);
}

export interface AdminSession {
  adminId: number;
  email?: string;
  name?: string;
}

/** Verifies the backend-issued JWT (see flipflop-api app/services/admin_auth_service.py).
 * Same HS256 secret + "flipflop-admin" audience on both sides — if this throws, the
 * cookie is missing, expired, or was signed for a different audience (e.g. a customer token). */
export async function verifyAdminToken(token: string): Promise<AdminSession | null> {
  try {
    const { payload } = await jwtVerify(token, getSecret(), {
      audience: ADMIN_TOKEN_AUDIENCE,
    });
    const sub = payload.sub;
    if (!sub) return null;
    return { adminId: Number(sub) };
  } catch {
    return null;
  }
}
