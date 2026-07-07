"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Banner, Button, ErrorText, Spinner } from "@/components/ui";
import { useMcpServers } from "@/features/mcp/use-mcp";
import {
  useApprovePlan,
  useCreatePlan,
  usePlans,
  useRejectPlan,
} from "@/features/provisioning/use-provisioning";
import { useWorkspaces } from "@/features/workspaces/use-workspaces";
import { canManageWorkspace, canWriteProjects } from "@/lib/types";
import type { ProvisioningPlan, ToolInvocation } from "@/lib/types";

const PLAN_BADGE: Record<string, string> = {
  proposed: "bg-amber-950 text-amber-300",
  executed: "bg-emerald-950 text-emerald-300",
  failed: "bg-rose-950 text-rose-300",
  rejected: "bg-slate-800 text-slate-500",
};

const INVOCATION_BADGE: Record<string, string> = {
  proposed: "text-slate-400",
  succeeded: "text-emerald-400",
  failed: "text-rose-400",
  skipped: "text-slate-600",
};

export default function ProvisionPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const { data: workspaces } = useWorkspaces();
  const servers = useMcpServers(workspaceId);
  const plans = usePlans(workspaceId, projectId);
  const createPlan = useCreatePlan(workspaceId, projectId);

  const [goal, setGoal] = useState("");

  const role = workspaces?.find((w) => w.id === workspaceId)?.role;
  const canWrite = role ? canWriteProjects(role) : false;
  const canApprove = role ? canManageWorkspace(role) : false;
  const hasAllowlistedServer = (servers.data ?? []).some(
    (s) => s.status === "active" && s.tool_allowlist.length > 0,
  );

  function onCreate(event: React.FormEvent) {
    event.preventDefault();
    if (goal.trim()) createPlan.mutate(goal.trim(), { onSuccess: () => setGoal("") });
  }

  return (
    <div className="space-y-5">
      <div>
        <Link
          href={`/dashboard/${workspaceId}/projects/${projectId}`}
          className="text-sm text-slate-400 hover:text-slate-200"
        >
          ← Project
        </Link>
        <h2 className="mt-2 text-lg font-semibold tracking-tight">Provisioning</h2>
        <p className="text-sm text-slate-500">
          Describe a provisioning goal. The provisioner proposes a plan of MCP tool calls; nothing
          runs until you approve it.
        </p>
      </div>

      {!servers.isLoading && !hasAllowlistedServer && (
        <Banner tone="amber">
          Register an MCP server and allowlist at least one tool first.{" "}
          <Link
            href={`/dashboard/${workspaceId}/mcp`}
            className="font-medium text-amber-100 underline"
          >
            Open MCP settings
          </Link>
        </Banner>
      )}

      {canWrite && (
        <form
          onSubmit={onCreate}
          className="space-y-2 rounded-xl border border-slate-800 bg-slate-900/50 p-4"
        >
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            rows={2}
            placeholder="e.g. Create a private GitHub repo for this blueprint and open a setup issue"
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={createPlan.isPending || !goal.trim()}>
              {createPlan.isPending ? "Planning…" : "Propose a plan"}
            </Button>
          </div>
          {createPlan.isError && <ErrorText>{(createPlan.error as Error).message}</ErrorText>}
        </form>
      )}

      {plans.isLoading && <Spinner />}
      {plans.data && plans.data.length === 0 && !plans.isLoading && (
        <Banner tone="slate">No provisioning plans yet.</Banner>
      )}

      <div className="space-y-4">
        {plans.data?.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            workspaceId={workspaceId}
            projectId={projectId}
            canApprove={canApprove}
          />
        ))}
      </div>
    </div>
  );
}

function PlanCard({
  plan,
  workspaceId,
  projectId,
  canApprove,
}: {
  plan: ProvisioningPlan;
  workspaceId: string;
  projectId: string;
  canApprove: boolean;
}) {
  const approve = useApprovePlan(workspaceId, projectId);
  const reject = useRejectPlan(workspaceId, projectId);
  const busy = approve.isPending || reject.isPending;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <p className="font-medium">{plan.goal}</p>
          <p className="text-sm text-slate-500">{plan.summary}</p>
        </div>
        <span
          className={`ml-auto rounded-full px-2 py-0.5 text-xs ${
            PLAN_BADGE[plan.status] ?? "bg-slate-800 text-slate-400"
          }`}
        >
          {plan.status}
        </span>
      </div>

      {plan.invocations.length === 0 ? (
        <p className="mt-3 text-sm text-slate-600">
          No runnable tool calls were proposed for this goal.
        </p>
      ) : (
        <ol className="mt-3 space-y-2">
          {plan.invocations.map((invocation, i) => (
            <InvocationRow key={invocation.id} index={i + 1} invocation={invocation} />
          ))}
        </ol>
      )}

      {plan.status === "proposed" && canApprove && plan.invocations.length > 0 && (
        <div className="mt-4 flex gap-2">
          <Button onClick={() => approve.mutate(plan.id)} disabled={busy}>
            {approve.isPending ? "Running…" : "Approve & run"}
          </Button>
          <Button variant="ghost" onClick={() => reject.mutate(plan.id)} disabled={busy}>
            Reject
          </Button>
        </div>
      )}
      {plan.status === "proposed" && !canApprove && (
        <p className="mt-3 text-xs text-slate-600">A workspace admin must approve this plan.</p>
      )}
    </div>
  );
}

function InvocationRow({ index, invocation }: { index: number; invocation: ToolInvocation }) {
  const args = Object.entries(invocation.arguments);
  return (
    <li className="rounded-lg border border-slate-800 px-3 py-2 text-sm">
      <div className="flex items-baseline gap-2">
        <span className="text-xs text-slate-600">{index}.</span>
        <span className="font-mono text-xs text-indigo-300">{invocation.tool_name}</span>
        <span className={`ml-auto text-xs ${INVOCATION_BADGE[invocation.status]}`}>
          {invocation.status}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">{invocation.rationale}</p>
      {args.length > 0 && (
        <p className="mt-1 font-mono text-xs text-slate-400">
          {args.map(([k, v]) => `${k}=${v}`).join("  ")}
        </p>
      )}
      {invocation.result && (
        <pre className="mt-1 overflow-x-auto rounded bg-slate-950 px-2 py-1 text-xs text-slate-400">
          {JSON.stringify(invocation.result)}
        </pre>
      )}
    </li>
  );
}
