import type { NextRequest } from "next/server";

// next.config rewrites proxy /api/* to the backend, but that proxy BUFFERS the
// response body, so SSE never streams (an intake run parked at needs_input never
// closes the stream, so the browser would see nothing at all). Route handlers
// are filesystem routes and take precedence over `afterFiles` rewrites, so this
// handler owns the SSE endpoint and pipes the upstream body through unbuffered.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const fetchCache = "force-no-store";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ runId: string }> },
): Promise<Response> {
  const { runId } = await context.params;

  const url = new URL(`${API_URL}/api/v1/runs/${encodeURIComponent(runId)}/events`);
  const after = request.nextUrl.searchParams.get("after");
  if (after) url.searchParams.set("after", after);

  const headers: Record<string, string> = { accept: "text/event-stream" };
  // Same-origin session cookie and the reconnect cursor must reach the backend.
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  const lastEventId = request.headers.get("last-event-id");
  if (lastEventId) headers["last-event-id"] = lastEventId;

  const upstream = await fetch(url, {
    headers,
    cache: "no-store",
    signal: request.signal, // client disconnect tears down the upstream stream
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(null, { status: upstream.status || 502 });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
      "X-Sse-Proxy": "route-handler",
    },
  });
}
