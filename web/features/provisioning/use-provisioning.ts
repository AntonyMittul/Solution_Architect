"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ProvisioningPlan } from "@/lib/types";

export const plansKey = (ws: string, pid: string) => ["plans", ws, pid] as const;
const base = (ws: string, pid: string) =>
  `/api/v1/workspaces/${ws}/projects/${pid}/provisioning`;

export function usePlans(ws: string, pid: string) {
  return useQuery({
    queryKey: plansKey(ws, pid),
    queryFn: () => api.get<ProvisioningPlan[]>(`${base(ws, pid)}/plans`),
  });
}

export function useCreatePlan(ws: string, pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (goal: string) =>
      api.post<ProvisioningPlan>(`${base(ws, pid)}/plans`, { goal }),
    onSuccess: () => qc.invalidateQueries({ queryKey: plansKey(ws, pid) }),
  });
}

export function useApprovePlan(ws: string, pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) =>
      api.post<ProvisioningPlan>(`${base(ws, pid)}/plans/${planId}/approve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: plansKey(ws, pid) }),
  });
}

export function useRejectPlan(ws: string, pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) =>
      api.post<ProvisioningPlan>(`${base(ws, pid)}/plans/${planId}/reject`),
    onSuccess: () => qc.invalidateQueries({ queryKey: plansKey(ws, pid) }),
  });
}
