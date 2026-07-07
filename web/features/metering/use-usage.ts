"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Usage } from "@/lib/types";

export function useUsage(workspaceId: string) {
  return useQuery({
    queryKey: ["usage", workspaceId],
    queryFn: () => api.get<Usage>(`/api/v1/workspaces/${workspaceId}/usage`),
    enabled: Boolean(workspaceId),
  });
}
