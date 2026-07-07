"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui";
import { useLogout, useMe } from "@/features/auth/use-auth";
import { useCreateWorkspace, useWorkspaces } from "@/features/workspaces/use-workspaces";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: user, isLoading, isError } = useMe();

  useEffect(() => {
    if (!isLoading && (isError || !user)) router.replace("/login");
  }, [isError, isLoading, user, router]);

  if (isLoading) return <Spinner label="Loading your account…" />;
  if (!user) return null;

  return (
    <div className="min-h-screen">
      <TopBar userEmail={user.email} />
      <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
    </div>
  );
}

function TopBar({ userEmail }: { userEmail: string }) {
  const router = useRouter();
  const params = useParams<{ workspaceId?: string }>();
  const logout = useLogout();
  const { data: workspaces } = useWorkspaces();
  const createWorkspace = useCreateWorkspace();

  function onSwitch(value: string) {
    if (value === "__new__") {
      const name = window.prompt("New workspace name");
      if (name?.trim()) {
        createWorkspace.mutate(name.trim(), {
          onSuccess: (ws) => router.push(`/dashboard/${ws.id}`),
        });
      }
      return;
    }
    router.push(`/dashboard/${value}`);
  }

  function onLogout() {
    logout.mutate(undefined, { onSuccess: () => router.replace("/login") });
  }

  return (
    <header className="border-b border-slate-800">
      <div className="mx-auto flex max-w-4xl items-center gap-4 px-6 py-3">
        <Link href="/dashboard" className="text-sm font-semibold tracking-tight">
          AI Solution Architect
        </Link>

        {workspaces && workspaces.length > 0 && (
          <select
            value={params.workspaceId ?? ""}
            onChange={(e) => onSwitch(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-200 outline-none focus:border-indigo-500"
          >
            {!params.workspaceId && <option value="">Select workspace…</option>}
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>
                {ws.name} ({ws.role})
              </option>
            ))}
            <option value="__new__">+ New workspace…</option>
          </select>
        )}

        <div className="ml-auto flex items-center gap-4 text-sm text-slate-400">
          {params.workspaceId && (
            <Link href={`/dashboard/${params.workspaceId}/usage`} className="hover:text-slate-200">
              Usage
            </Link>
          )}
          <Link href="/playground" className="hover:text-slate-200">
            Playground
          </Link>
          <span className="hidden sm:inline">{userEmail}</span>
          <button
            onClick={onLogout}
            disabled={logout.isPending}
            className="rounded-lg border border-slate-700 px-3 py-1 text-slate-200 hover:bg-slate-800"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
