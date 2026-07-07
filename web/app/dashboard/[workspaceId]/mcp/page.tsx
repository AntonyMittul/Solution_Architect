"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Banner, Button, ErrorText, Field, Spinner, TextInput } from "@/components/ui";
import {
  useDeleteServer,
  useMcpServers,
  useRegisterServer,
  useServerTools,
  useUpdateServer,
} from "@/features/mcp/use-mcp";
import { useWorkspaces } from "@/features/workspaces/use-workspaces";
import { canManageWorkspace } from "@/lib/types";
import type { McpServer, McpTrust } from "@/lib/types";

export default function McpSettingsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { data: workspaces } = useWorkspaces();
  const servers = useMcpServers(workspaceId);
  const register = useRegisterServer(workspaceId);

  const [name, setName] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [trust, setTrust] = useState<McpTrust>("untrusted");

  const role = workspaces?.find((w) => w.id === workspaceId)?.role;
  const canManage = role ? canManageWorkspace(role) : false;

  function onRegister(event: React.FormEvent) {
    event.preventDefault();
    register.mutate(
      { name, endpoint, trust },
      {
        onSuccess: () => {
          setName("");
          setEndpoint("");
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/dashboard/${workspaceId}`}
          className="text-sm text-slate-400 hover:text-slate-200"
        >
          ← Projects
        </Link>
        <h2 className="mt-2 text-lg font-semibold tracking-tight">MCP servers</h2>
        <p className="text-sm text-slate-500">
          Connect Model Context Protocol servers and allowlist the tools agents may propose. Only
          allowlisted tools can ever run, and only after you approve a plan.
        </p>
      </div>

      {!canManage && (
        <Banner tone="slate">Workspace admins can register and configure MCP servers.</Banner>
      )}

      {canManage && (
        <form
          onSubmit={onRegister}
          className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5"
        >
          <p className="text-sm font-medium">Register a server</p>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Name">
              <TextInput
                required
                placeholder="github"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Field label="Endpoint (streamable HTTP)">
              <TextInput
                placeholder="https://mcp.example/github"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
              />
            </Field>
            <Field label="Trust">
              <select
                value={trust}
                onChange={(e) => setTrust(e.target.value as McpTrust)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-500"
              >
                <option value="untrusted">untrusted</option>
                <option value="trusted_read">trusted_read</option>
              </select>
            </Field>
          </div>
          {register.isError && <ErrorText>{(register.error as Error).message}</ErrorText>}
          <Button type="submit" disabled={register.isPending}>
            {register.isPending ? "Registering…" : "Register server"}
          </Button>
        </form>
      )}

      {servers.isLoading && <Spinner />}
      {servers.isError && <ErrorText>{(servers.error as Error).message}</ErrorText>}
      {servers.data && servers.data.length === 0 && !servers.isLoading && (
        <Banner tone="slate">No MCP servers yet.</Banner>
      )}

      <div className="space-y-4">
        {servers.data?.map((server) => (
          <ServerCard
            key={server.id}
            workspaceId={workspaceId}
            server={server}
            canManage={canManage}
          />
        ))}
      </div>
    </div>
  );
}

function ServerCard({
  workspaceId,
  server,
  canManage,
}: {
  workspaceId: string;
  server: McpServer;
  canManage: boolean;
}) {
  const tools = useServerTools(workspaceId, server.id);
  const update = useUpdateServer(workspaceId);
  const remove = useDeleteServer(workspaceId);
  const allowed = new Set(server.tool_allowlist);

  function toggleTool(toolName: string, checked: boolean) {
    const next = new Set(allowed);
    if (checked) next.add(toolName);
    else next.delete(toolName);
    update.mutate({ id: server.id, tool_allowlist: [...next] });
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <div className="flex items-center gap-3">
        <p className="font-medium">{server.name}</p>
        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
          {server.trust}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            server.status === "active"
              ? "bg-emerald-950 text-emerald-300"
              : "bg-slate-800 text-slate-500"
          }`}
        >
          {server.status}
        </span>
        {server.endpoint && (
          <span className="truncate text-xs text-slate-600">{server.endpoint}</span>
        )}
        {canManage && (
          <div className="ml-auto flex gap-2">
            <button
              onClick={() =>
                update.mutate({
                  id: server.id,
                  status: server.status === "active" ? "disabled" : "active",
                })
              }
              className="rounded-lg border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
            >
              {server.status === "active" ? "Disable" : "Enable"}
            </button>
            <button
              onClick={() => remove.mutate(server.id)}
              className="rounded-lg px-2 py-1 text-xs text-rose-400 hover:bg-rose-950/40"
            >
              Delete
            </button>
          </div>
        )}
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Tools ({server.tool_allowlist.length} allowlisted)
        </p>
        {tools.isLoading && <Spinner />}
        {tools.isError && (
          <p className="text-xs text-slate-600">Could not discover tools from this server.</p>
        )}
        <ul className="grid gap-1 sm:grid-cols-2">
          {tools.data?.map((tool) => (
            <li key={tool.name} className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                disabled={!canManage || update.isPending}
                checked={allowed.has(tool.name)}
                onChange={(e) => toggleTool(tool.name, e.target.checked)}
                className="mt-1"
              />
              <span>
                <span className="font-mono text-xs text-slate-200">{tool.name}</span>
                <span className="block text-xs text-slate-500">{tool.description}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
