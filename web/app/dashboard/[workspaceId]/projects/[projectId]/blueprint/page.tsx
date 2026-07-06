"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { DiagramCanvas } from "@/components/diagram-canvas";
import { MarkdownView } from "@/components/markdown";
import { Banner, Button, ErrorText, Spinner } from "@/components/ui";
import { downloadFile } from "@/lib/api";
import { artifactsKey, useArtifacts, useStartBlueprint } from "@/features/blueprint/use-blueprint";
import { useRequirements } from "@/features/intake/use-intake";
import { useRunStream } from "@/features/runs/use-run-stream";
import { useWorkspaces } from "@/features/workspaces/use-workspaces";
import type {
  ApiSpecContent,
  ArchitectureContent,
  ArtifactSummary,
  ArtifactType,
  CostContent,
  DbSchemaContent,
  DesignDocContent,
  DiagramContent,
  Provenance,
  TechStackContent,
} from "@/lib/types";
import { canWriteProjects } from "@/lib/types";

const TABS: { type: ArtifactType; label: string }[] = [
  { type: "design_doc", label: "Design doc" },
  { type: "architecture_doc", label: "Architecture" },
  { type: "diagram", label: "Diagram" },
  { type: "tech_stack", label: "Tech stack" },
  { type: "api_spec", label: "API" },
  { type: "db_schema", label: "Database" },
  { type: "cost_estimate", label: "Cost" },
];

const AGENTS: { key: string; label: string }[] = [
  { key: "solution_designer", label: "Solution designer" },
  { key: "api_designer", label: "API designer" },
  { key: "data_modeler", label: "Data modeler" },
  { key: "tech_stack_recommender", label: "Tech stack" },
  { key: "cost_estimator", label: "Cost estimator" },
  { key: "diagram_generator", label: "Diagram" },
  { key: "design_reviewer", label: "Design reviewer" },
  { key: "docs_writer", label: "Docs writer" },
];

export default function BlueprintPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const qc = useQueryClient();
  const { data: workspaces } = useWorkspaces();
  const artifacts = useArtifacts(workspaceId, projectId);
  const requirements = useRequirements(workspaceId, projectId);
  const start = useStartBlueprint(workspaceId, projectId);

  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<ArtifactType>("design_doc");

  const role = workspaces?.find((w) => w.id === workspaceId)?.role;
  const canWrite = role ? canWriteProjects(role) : false;
  const confirmed = requirements.data?.status === "confirmed";
  const generating = activeRunId !== null;

  const onEvent = useCallback(
    (type: string, payload: Record<string, unknown> | undefined) => {
      const agent = payload?.agent as string | undefined;
      if (type === "agent.started" && agent) setRunningAgent(agent);
      if (type === "agent.completed" && agent) {
        setCompleted((prev) => new Set(prev).add(agent));
        setRunningAgent(null);
      }
      if (type === "artifact.created") {
        qc.invalidateQueries({ queryKey: artifactsKey(workspaceId, projectId) });
      }
      if (type === "run.completed" || type === "run.failed") {
        qc.invalidateQueries({ queryKey: artifactsKey(workspaceId, projectId) });
        setActiveRunId(null);
        setRunningAgent(null);
      }
    },
    [qc, workspaceId, projectId],
  );
  useRunStream(activeRunId, onEvent);

  async function generate() {
    setCompleted(new Set());
    setRunningAgent(null);
    const result = await start.mutateAsync();
    setActiveRunId(result.run_id);
  }

  const byType = useMemo(() => {
    const map = new Map<ArtifactType, ArtifactSummary>();
    for (const a of artifacts.data ?? []) map.set(a.type, a);
    return map;
  }, [artifacts.data]);

  const hasArtifacts = (artifacts.data ?? []).some((a) => a.latest);
  const current = byType.get(selected);

  return (
    <div className="space-y-5">
      <Link
        href={`/dashboard/${workspaceId}/projects/${projectId}`}
        className="text-sm text-slate-400 hover:text-slate-200"
      >
        ← Requirements
      </Link>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">Blueprint</h2>
        <div className="flex items-center gap-2">
          {hasArtifacts && !generating && (
            <Button
              variant="ghost"
              onClick={() =>
                void downloadFile(
                  `/api/v1/workspaces/${workspaceId}/projects/${projectId}/export`,
                  "blueprint.zip",
                )
              }
            >
              Download .zip
            </Button>
          )}
          {canWrite && confirmed && (
            <Button onClick={() => void generate()} disabled={generating}>
              {generating ? "Generating…" : hasArtifacts ? "Regenerate" : "Generate blueprint"}
            </Button>
          )}
        </div>
      </div>

      {!confirmed && (
        <Banner tone="amber">
          Confirm the requirements before generating a blueprint.{" "}
          <Link
            href={`/dashboard/${workspaceId}/projects/${projectId}`}
            className="font-medium text-amber-100 underline"
          >
            Go to requirements
          </Link>
        </Banner>
      )}

      {generating && <GenerationProgress running={runningAgent} completed={completed} />}
      {start.isError && <ErrorText>{(start.error as Error).message}</ErrorText>}

      {artifacts.isLoading && <Spinner />}

      {hasArtifacts && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
            {TABS.filter((tab) => byType.get(tab.type)?.latest).map((tab) => (
              <button
                key={tab.type}
                onClick={() => setSelected(tab.type)}
                className={`rounded-lg px-3 py-1 text-sm ${
                  selected === tab.type
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:bg-slate-800"
                }`}
              >
                {tab.label}
                {byType.get(tab.type)?.is_stale && <span className="ml-1 text-amber-400">•</span>}
              </button>
            ))}
          </div>

          {current?.latest ? (
            <div className="space-y-3">
              <ArtifactViewer type={selected} content={current.latest.content} />
              <ProvenanceFooter
                provenance={current.latest.provenance}
                version={current.latest.version}
                createdAt={current.latest.created_at}
                stale={current.is_stale}
              />
            </div>
          ) : (
            <p className="text-sm text-slate-500">Select an artifact.</p>
          )}
        </div>
      )}

      {!hasArtifacts && !artifacts.isLoading && confirmed && !generating && (
        <Banner tone="slate">
          No blueprint yet. Click “Generate blueprint” to run the multi-agent design.
        </Banner>
      )}
    </div>
  );
}

function GenerationProgress({
  running,
  completed,
}: {
  running: string | null;
  completed: Set<string>;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <p className="mb-3 text-sm text-slate-300">Running the multi-agent design graph…</p>
      <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
        {AGENTS.map((agent) => {
          const done = completed.has(agent.key);
          const active = running === agent.key;
          return (
            <li key={agent.key} className="flex items-center gap-2">
              <span
                className={
                  done
                    ? "text-emerald-400"
                    : active
                      ? "text-indigo-400"
                      : "text-slate-600"
                }
              >
                {done ? "✓" : active ? "▸" : "○"}
              </span>
              <span className={done ? "text-slate-300" : "text-slate-500"}>{agent.label}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ProvenanceFooter({
  provenance,
  version,
  createdAt,
  stale,
}: {
  provenance: Provenance;
  version: number;
  createdAt: string;
  stale: boolean;
}) {
  return (
    <p className="border-t border-slate-800 pt-2 text-xs text-slate-600">
      v{version} · generated by {provenance.agent} ({provenance.model}) · from requirements v
      {provenance.requirements_version} · {new Date(createdAt).toLocaleString()}
      {stale && <span className="ml-2 text-amber-400">stale — upstream changed</span>}
    </p>
  );
}

function ArtifactViewer({
  type,
  content,
}: {
  type: ArtifactType;
  content: Record<string, unknown>;
}) {
  switch (type) {
    case "design_doc":
      return <MarkdownView text={(content as unknown as DesignDocContent).markdown ?? ""} />;
    case "diagram":
      return <DiagramCanvas content={content as unknown as DiagramContent} />;
    case "architecture_doc":
      return <ArchitectureView content={content as unknown as ArchitectureContent} />;
    case "tech_stack":
      return <TechStackView content={content as unknown as TechStackContent} />;
    case "api_spec":
      return <ApiSpecView content={content as unknown as ApiSpecContent} />;
    case "db_schema":
      return <DbSchemaView content={content as unknown as DbSchemaContent} />;
    case "cost_estimate":
      return <CostView content={content as unknown as CostContent} />;
  }
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
      {children}
    </div>
  );
}

function ArchitectureView({ content }: { content: ArchitectureContent }) {
  return (
    <div className="space-y-4">
      {content.overview && <p className="text-sm text-slate-300">{content.overview}</p>}
      {content.components?.length > 0 && (
        <Section title="Components">
          <ul className="space-y-1 text-sm text-slate-300">
            {content.components.map((c, i) => (
              <li key={i}>
                <span className="font-medium text-slate-100">{c.name}</span>{" "}
                <span className="text-xs text-slate-500">({c.type})</span> — {c.responsibility}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {content.data_flows?.length > 0 && (
        <Section title="Data flows">
          <ul className="ml-5 list-disc text-sm text-slate-300">
            {content.data_flows.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </Section>
      )}
      {content.key_decisions?.length > 0 && (
        <Section title="Key decisions">
          <ul className="space-y-1 text-sm text-slate-300">
            {content.key_decisions.map((d, i) => (
              <li key={i}>
                <span className="font-medium text-slate-100">{d.decision}</span> — {d.rationale}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function TechStackView({ content }: { content: TechStackContent }) {
  return (
    <ul className="space-y-2 text-sm text-slate-300">
      {content.choices?.map((c, i) => (
        <li key={i} className="rounded-lg border border-slate-800 px-3 py-2">
          <span className="text-xs uppercase text-slate-500">{c.layer}</span>
          <p className="font-medium text-slate-100">{c.choice}</p>
          <p className="text-xs text-slate-400">{c.rationale}</p>
          {c.alternatives?.length > 0 && (
            <p className="mt-1 text-xs text-slate-600">alternatives: {c.alternatives.join(", ")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function ApiSpecView({ content }: { content: ApiSpecContent }) {
  return (
    <table className="w-full text-left text-sm">
      <tbody>
        {content.endpoints?.map((e, i) => (
          <tr key={i} className="border-b border-slate-800">
            <td className="py-1 pr-3 font-mono text-xs text-indigo-400">{e.method}</td>
            <td className="py-1 pr-3 font-mono text-xs text-slate-200">{e.path}</td>
            <td className="py-1 text-slate-400">{e.summary}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DbSchemaView({ content }: { content: DbSchemaContent }) {
  return (
    <div className="space-y-4">
      {content.tables?.map((table, i) => (
        <div key={i} className="rounded-lg border border-slate-800">
          <p className="border-b border-slate-800 bg-slate-900 px-3 py-1.5 font-mono text-sm text-slate-100">
            {table.name}
          </p>
          <ul className="divide-y divide-slate-800/60">
            {table.columns?.map((col, j) => (
              <li key={j} className="flex items-baseline gap-3 px-3 py-1 text-sm">
                <span className="font-mono text-slate-200">{col.name}</span>
                <span className="font-mono text-xs text-slate-500">{col.type}</span>
                {!col.nullable && <span className="text-xs text-amber-400">NOT NULL</span>}
                {table.primary_key?.includes(col.name) && (
                  <span className="text-xs text-indigo-400">PK</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function CostView({ content }: { content: CostContent }) {
  const total = (content.line_items ?? []).reduce((s, li) => s + (li.monthly_expected || 0), 0);
  return (
    <div className="space-y-2">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase text-slate-500">
            <th className="py-1">Service</th>
            <th className="py-1 text-right">Low</th>
            <th className="py-1 text-right">Expected</th>
            <th className="py-1 text-right">High</th>
          </tr>
        </thead>
        <tbody>
          {content.line_items?.map((li, i) => (
            <tr key={i} className="border-b border-slate-800">
              <td className="py-1 text-slate-200">{li.service}</td>
              <td className="py-1 text-right text-slate-400">{li.monthly_low}</td>
              <td className="py-1 text-right text-slate-200">{li.monthly_expected}</td>
              <td className="py-1 text-right text-slate-400">{li.monthly_high}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-right text-sm text-slate-300">
        ≈ {total.toLocaleString()} {content.currency}/mo (expected)
      </p>
      {content.pricing_note && <p className="text-xs text-slate-600">{content.pricing_note}</p>}
    </div>
  );
}
