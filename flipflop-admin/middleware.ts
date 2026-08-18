import { NextRequest, NextResponse } from "next/server";

// Auth disabled for development — all routes are public
export async function middleware(request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: [
    // Run on every route except static assets (anything under public/, by
    // extension) and Next internals. Without the extension exclusion, image
    // requests like /pics/logo.png get caught by the "no session" branch
    // below and redirected to an HTML /login page instead of the image.
    "/((?!_next/static|_next/image|favicon.ico|api/session|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|mp4|webm|woff2?|ttf|glb)$).*)",
  ],
};
