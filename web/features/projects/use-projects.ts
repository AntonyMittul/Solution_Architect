"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Project } from "@/lib/types";

const projectsKey = (workspaceId: string) => ["projects", workspaceId] as const;

export function useProjects(workspaceId: string) {
  return useQuery({
    queryKey: projectsKey(workspaceId),
    queryFn: () => api.get<Project[]>(`/api/v1/workspaces/${workspaceId}/projects`),
    enabled: Boolean(workspaceId),
  });
}

export function useCreateProject(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description?: string }) =>
      api.post<Project>(`/api/v1/workspaces/${workspaceId}/projects`, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectsKey(workspaceId) }),
  });
}

export function useDeleteProject(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) =>
      api.del<void>(`/api/v1/workspaces/${workspaceId}/projects/${projectId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectsKey(workspaceId) }),
  });
}

export function useRestoreProject(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) =>
      api.post<Project>(`/api/v1/workspaces/${workspaceId}/projects/${projectId}/restore`),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectsKey(workspaceId) }),
  });
}
