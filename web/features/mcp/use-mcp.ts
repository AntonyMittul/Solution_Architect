"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { McpServer, McpServerStatus, McpTrust, ToolDescriptor } from "@/lib/types";

export const mcpServersKey = (ws: string) => ["mcp-servers", ws] as const;
const base = (ws: string) => `/api/v1/workspaces/${ws}/mcp-servers`;

export function useMcpServers(ws: string) {
  return useQuery({
    queryKey: mcpServersKey(ws),
    queryFn: () => api.get<McpServer[]>(base(ws)),
  });
}

export function useServerTools(ws: string, serverId: string) {
  return useQuery({
    queryKey: ["mcp-tools", ws, serverId],
    queryFn: () => api.get<ToolDescriptor[]>(`${base(ws)}/${serverId}/tools`),
  });
}

export function useRegisterServer(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; endpoint: string; trust: McpTrust }) =>
      api.post<McpServer>(base(ws), {
        ...input,
        transport: "streamable_http",
        tool_allowlist: [],
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: mcpServersKey(ws) }),
  });
}

export function useUpdateServer(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      id: string;
      tool_allowlist?: string[];
      trust?: McpTrust;
      status?: McpServerStatus;
    }) => {
      const { id, ...body } = input;
      return api.patch<McpServer>(`${base(ws)}/${id}`, body);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: mcpServersKey(ws) }),
  });
}

export function useDeleteServer(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<void>(`${base(ws)}/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: mcpServersKey(ws) }),
  });
}
