import type { NextConfig } from "next";

// 127.0.0.1, not localhost: Node 22 resolves localhost to ::1 first, while
// uvicorn binds IPv4 only.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Single origin: the browser only ever talks to the web app; the backend
  // is proxied so cookies stay httpOnly/same-site and there is no CORS surface.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/health/:path*", destination: `${API_URL}/health/:path*` },
    ];
  },
};

export default nextConfig;
