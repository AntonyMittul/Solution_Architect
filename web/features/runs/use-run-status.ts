"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface RunStatus {
  id: string;
  kind: string;
  status: "queued" | "running" | "needs_input" | "completed" | "failed" | "cancelled";
  error: string | null;
}

const RESTING = new Set(["needs_input", "completed", "failed", "cancelled"]);

/**
 * Polls a run while it is in flight. SSE gives instant updates, but a proxy
 * that buffers (or a network that blocks) event streams must not leave the UI
 * stuck — this is the correctness net. Polling stops once the run rests.
 */
export function useRunStatus(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.get<RunStatus>(`/api/v1/runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && RESTING.has(status) ? false : 2000;
    },
  });
}
