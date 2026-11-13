import { NextResponse } from "next/server";

const headers = {
  "Access-Control-Allow-Origin": "*",
  "Cache-Control": "no-store, max-age=0",
};

export function GET() {
  return NextResponse.json(
    { ok: true, service: "flipflop-shop", checked_at: new Date().toISOString() },
    { headers },
  );
}

export function HEAD() {
  return new Response(null, { status: 200, headers });
}
