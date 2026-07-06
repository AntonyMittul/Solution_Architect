"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { ChatMessage, PostMessageResult, Requirements } from "@/lib/types";

export const messagesKey = (ws: string, pid: string) => ["messages", ws, pid] as const;
export const requirementsKey = (ws: string, pid: string) => ["requirements", ws, pid] as const;

const base = (ws: string, pid: string) => `/api/v1/workspaces/${ws}/projects/${pid}`;

export function useMessages(ws: string, pid: string) {
  return useQuery({
    queryKey: messagesKey(ws, pid),
    queryFn: () => api.get<ChatMessage[]>(`${base(ws, pid)}/messages`),
  });
}

export function useRequirements(ws: string, pid: string) {
  return useQuery({
    queryKey: requirementsKey(ws, pid),
    queryFn: async () => {
      try {
        return await api.get<Requirements>(`${base(ws, pid)}/requirements`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null; // none yet
        throw error;
      }
    },
  });
}

export function usePostMessage(ws: string, pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) =>
      api.post<PostMessageResult>(`${base(ws, pid)}/messages`, { text }),
    onSuccess: () => qc.invalidateQueries({ queryKey: messagesKey(ws, pid) }),
  });
}

export function useConfirmRequirements(ws: string, pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Requirements>(`${base(ws, pid)}/requirements/confirm`),
    onSuccess: () => qc.invalidateQueries({ queryKey: requirementsKey(ws, pid) }),
  });
}
