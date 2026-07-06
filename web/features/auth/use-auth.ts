"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { RegisterResponse, User } from "@/lib/types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<User>("/api/v1/auth/me"),
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { email: string; password: string }) =>
      api.post<User>("/api/v1/auth/login", input),
    onSuccess: (user) => qc.setQueryData(["me"], user),
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (input: { email: string; password: string; name: string }) =>
      api.post<RegisterResponse>("/api/v1/auth/register", input),
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (token: string) => api.post<User>("/api/v1/auth/verify", { token }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/api/v1/auth/logout"),
    onSuccess: () => qc.clear(),
  });
}
