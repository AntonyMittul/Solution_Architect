"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ArtifactSummary, StartBlueprintResponse } from "@/lib/types";

export const artifactsKey = (ws: string, pid: string) => ["artifacts", ws, pid] as const;

const base = (ws: string, pid: string) => `/api/v1/workspaces/${ws}/projects/${pid}`;

export function useArtifacts(ws: string, pid: string) {
  return useQuery({
    queryKey: artifactsKey(ws, pid),
    queryFn: () => api.get<ArtifactSummary[]>(`${base(ws, pid)}/artifacts`),
  });
}

export function useStartBlueprint(ws: string, pid: string) {
  return useMutation({
    mutationFn: () => api.post<StartBlueprintResponse>(`${base(ws, pid)}/blueprint`),
  });
}
