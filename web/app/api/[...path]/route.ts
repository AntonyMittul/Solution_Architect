import type { NextRequest } from "next/server";

// Runtime proxy to the backend. This replaces next.config `rewrites`, whose
// destinations are baked into the build — so a container image built without
// API_URL would proxy to localhost forever. Reading API_URL here keeps config at
// runtime (12-factor), so one image promotes across environments.
//
// The more specific /api/v1/runs/[runId]/events route wins over this catch-all
// and handles the SSE stream.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

// Hop-by-hop headers must not be forwarded; fetch recomputes length/encoding.
const SKIP = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "accept-encoding",
  "keep-alive",
]);

async function proxy(request: NextRequest, segments: string[]): Promise<Response> {
  const target = new URL(`${API_URL}/api/${segments.map(encodeURIComponent).join("/")}`);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!SKIP.has(key.toLowerCase())) headers.set(key, value);
  });

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "manual",
    cache: "no-store",
    signal: request.signal,
  });

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (lower !== "set-cookie" && !SKIP.has(lower)) out.set(key, value);
  });
  // Auth relies on httpOnly cookies: forward each Set-Cookie separately.
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);

  return new Response(upstream.body, { status: upstream.status, headers: out });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function POST(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function PUT(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function PATCH(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function DELETE(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
