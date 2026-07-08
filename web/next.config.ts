import type { NextConfig } from "next";

// 127.0.0.1, not localhost: Node 22 resolves localhost to ::1 first, while
// uvicorn binds IPv4 only.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Single origin: the browser only ever talks to the web app; the backend
  // is proxied so cookies stay httpOnly/same-site and there is no CORS surface.
  //
  // `fallback` (not a bare array): array-form rewrites are `afterFiles`, which
  // Next checks BEFORE dynamic routes — that would shadow our dynamic SSE route
  // handler. `fallback` rewrites run after all Next routes, so the streaming
  // handler at /api/v1/runs/[runId]/events wins and everything else proxies.
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback: [
        { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
        { source: "/health/:path*", destination: `${API_URL}/health/:path*` },
      ],
    };
  },
};

export default nextConfig;
