import type { ReactNode } from "react";

// The login page is client-rendered, so route config on the client page does
// not affect prerendering. Keep this auth entry point out of shared caches.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function LoginLayout({ children }: { children: ReactNode }) {
  return children;
}
