"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ErrorText, Spinner } from "@/components/ui";
import { useUsage } from "@/features/metering/use-usage";

export default function UsagePage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const usage = useUsage(workspaceId);

  if (usage.isLoading) return <Spinner />;
  if (usage.isError) return <ErrorText>{(usage.error as Error).message}</ErrorText>;
  if (!usage.data) return null;

  const u = usage.data;
  const runsPct = u.monthly_run_quota
    ? Math.min(100, Math.round((u.runs_this_month / u.monthly_run_quota) * 100))
    : 0;
  const period = new Date(u.period_start).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/dashboard/${workspaceId}`}
          className="text-sm text-slate-400 hover:text-slate-200"
        >
          ← Projects
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Usage</h2>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs uppercase text-slate-300">
            {u.plan} plan
          </span>
          <span className="text-sm text-slate-500">{period}</span>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-sm font-medium">Runs this month</span>
          <span className="text-sm text-slate-400">
            {u.runs_this_month} / {u.monthly_run_quota}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full ${runsPct >= 100 ? "bg-rose-500" : "bg-indigo-500"}`}
            style={{ width: `${runsPct}%` }}
          />
        </div>
        {runsPct >= 100 && (
          <p className="mt-2 text-xs text-rose-400">
            Monthly run limit reached — new intake and blueprint runs are paused until next month.
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Tokens this month" value={u.total_tokens.toLocaleString()} />
        <Stat
          label="Estimated cost"
          value={`$${u.estimated_cost_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
        />
        <Stat label="Per-run token budget" value={u.per_run_token_budget.toLocaleString()} />
      </div>

      <p className="text-xs text-slate-600">
        Costs are estimates based on total tokens and a blended per-million-token rate.
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}
