import type { NextRequest } from "next/server";

// Convenience passthrough so smoke tests / uptime checks can hit the backend's
// health endpoints through the web origin. Runtime-configured like /api/*.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const upstream = await fetch(`${API_URL}/health/${path.join("/")}`, {
    cache: "no-store",
    signal: request.signal,
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
