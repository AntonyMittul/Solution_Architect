import type { NextConfig } from "next";

// Single origin: the browser only ever talks to the web app; the backend is
// reached through runtime route handlers under app/api and app/health.
//
// We deliberately do NOT use next.config `rewrites` here: their destinations are
// resolved at BUILD time and baked into the routes manifest, so a container image
// built without API_URL would forever proxy to localhost. Route handlers read
// process.env.API_URL at request time, so one image works in every environment.
// (Array-form rewrites are also `afterFiles`, which Next matches before dynamic
// routes — that silently shadowed our streaming SSE handler.)
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
