"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Banner, Button, ErrorText, Spinner } from "@/components/ui";
import {
  messagesKey,
  requirementsKey,
  useConfirmRequirements,
  useMessages,
  usePostMessage,
  useRequirements,
} from "@/features/intake/use-intake";
import { useRunStream } from "@/features/runs/use-run-stream";
import { useWorkspaces } from "@/features/workspaces/use-workspaces";
import { TEMPLATE_BRIEFS } from "@/lib/briefs";
import type { ChatMessage, Requirements, RequirementsContent } from "@/lib/types";
import { canWriteProjects } from "@/lib/types";

const DONE = new Set(["run.completed", "run.failed"]);
const REFETCH = new Set(["message.created", "artifact.created", "intake.awaiting_answer"]);

export default function ProjectIntakePage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const qc = useQueryClient();
  const { data: workspaces } = useWorkspaces();
  const messages = useMessages(workspaceId, projectId);
  const requirements = useRequirements(workspaceId, projectId);
  const postMessage = usePostMessage(workspaceId, projectId);
  const confirm = useConfirmRequirements(workspaceId, projectId);

  const [text, setText] = useState("");
  // One stream stays open for the whole (possibly multi-round) run: it survives
  // the needs_input pause via heartbeats, and the resume publishes to the same
  // channel — so we never reopen and replay stale events.
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [awaitingAnswer, setAwaitingAnswer] = useState(false);

  const role = workspaces?.find((w) => w.id === workspaceId)?.role;
  const canWrite = role ? canWriteProjects(role) : false;
  const thinking = activeRunId !== null && !awaitingAnswer;

  const onEvent = useCallback(
    (type: string) => {
      if (REFETCH.has(type)) {
        qc.invalidateQueries({ queryKey: messagesKey(workspaceId, projectId) });
        qc.invalidateQueries({ queryKey: requirementsKey(workspaceId, projectId) });
      }
      if (type === "intake.awaiting_answer") setAwaitingAnswer(true); // user's turn
      if (DONE.has(type)) {
        qc.invalidateQueries({ queryKey: messagesKey(workspaceId, projectId) });
        qc.invalidateQueries({ queryKey: requirementsKey(workspaceId, projectId) });
        setActiveRunId(null); // close the stream
        setAwaitingAnswer(false);
      }
    },
    [qc, workspaceId, projectId],
  );
  useRunStream(activeRunId, onEvent);

  async function send() {
    const value = text.trim();
    if (!value) return;
    setText("");
    setAwaitingAnswer(false); // back to thinking
    const result = await postMessage.mutateAsync(value);
    setActiveRunId(result.run_id); // same id on resume -> stream stays open
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <div className="space-y-4">
      <Link href={`/dashboard/${workspaceId}`} className="text-sm text-slate-400 hover:text-slate-200">
        ← Projects
      </Link>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <section className="space-y-4">
          <h2 className="text-lg font-semibold tracking-tight">Requirements intake</h2>

          {messages.isLoading && <Spinner />}
          {messages.isError && <ErrorText>{(messages.error as Error).message}</ErrorText>}

          {messages.data && messages.data.length === 0 && !thinking && (
            <div className="space-y-3">
              <Banner tone="slate">
                Describe your software idea to begin — e.g. “Build a food delivery app for one
                million users.”
              </Banner>
              {canWrite && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-500">Start from a template:</span>
                  {TEMPLATE_BRIEFS.map((brief) => (
                    <button
                      key={brief.id}
                      onClick={() => setText(brief.prompt)}
                      className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-indigo-500 hover:text-indigo-300"
                    >
                      {brief.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <ul className="space-y-3">
            {messages.data?.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {thinking && (
              <li className="flex items-center gap-2 text-sm text-slate-500">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-indigo-400" />
                Requirements analyst is thinking…
              </li>
            )}
          </ul>

          {canWrite ? (
            <div className="space-y-2">
              {awaitingAnswer && (
                <p className="text-xs text-amber-400">
                  Your turn — answer the analyst's questions to refine the requirements.
                </p>
              )}
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                rows={3}
                disabled={thinking}
                placeholder="Describe your idea, or answer the analyst's questions…"
                className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-indigo-500 disabled:opacity-60"
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-600">Enter to send · Shift+Enter for newline</span>
                <Button onClick={() => void send()} disabled={thinking || !text.trim()}>
                  Send
                </Button>
              </div>
              {postMessage.isError && (
                <ErrorText>{(postMessage.error as Error).message}</ErrorText>
              )}
            </div>
          ) : (
            <Banner tone="slate">You have read-only access to this workspace.</Banner>
          )}
        </section>

        <RequirementsPanel
          requirements={requirements.data ?? null}
          loading={requirements.isLoading}
          canWrite={canWrite}
          confirming={confirm.isPending}
          onConfirm={() => confirm.mutate()}
          blueprintHref={`/dashboard/${workspaceId}/projects/${projectId}/blueprint`}
        />
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <li className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
          isUser ? "bg-indigo-600 text-white" : "border border-slate-800 bg-slate-900 text-slate-100"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content.text}</p>
        {message.content.questions && message.content.questions.length > 0 && (
          <ul className="mt-2 space-y-1 border-t border-slate-700/50 pt-2">
            {message.content.questions.map((q) => (
              <li key={q.id} className="text-slate-300">
                • {q.question}
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

const SECTIONS: { key: keyof RequirementsContent; label: string }[] = [
  { key: "goals", label: "Goals" },
  { key: "actors", label: "Actors" },
  { key: "functional_requirements", label: "Functional requirements" },
  { key: "non_functional_requirements", label: "Non-functional requirements" },
  { key: "constraints", label: "Constraints" },
  { key: "assumptions", label: "Assumptions" },
  { key: "open_questions", label: "Open questions" },
];

function RequirementsPanel({
  requirements,
  loading,
  canWrite,
  confirming,
  onConfirm,
  blueprintHref,
}: {
  requirements: Requirements | null;
  loading: boolean;
  canWrite: boolean;
  confirming: boolean;
  onConfirm: () => void;
  blueprintHref: string;
}) {
  return (
    <aside className="h-fit rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Requirements</h3>
        {requirements && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs ${
              requirements.status === "confirmed"
                ? "bg-emerald-950 text-emerald-300"
                : "bg-slate-800 text-slate-400"
            }`}
          >
            v{requirements.version} · {requirements.status}
          </span>
        )}
      </div>

      {loading && <Spinner />}
      {!loading && !requirements && (
        <p className="text-sm text-slate-500">
          The structured requirements document will appear here as you chat.
        </p>
      )}

      {requirements && (
        <div className="space-y-3">
          <p className="text-sm text-slate-300">{requirements.content.summary}</p>
          {SECTIONS.map(({ key, label }) => {
            const items = requirements.content[key] as string[];
            if (!items || items.length === 0) return null;
            return (
              <div key={key}>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {label}
                </p>
                <ul className="mt-1 space-y-0.5 text-sm text-slate-300">
                  {items.map((item, i) => (
                    <li key={i}>• {item}</li>
                  ))}
                </ul>
              </div>
            );
          })}

          {canWrite && requirements.status === "draft" && (
            <Button onClick={onConfirm} disabled={confirming} className="w-full">
              {confirming ? "Confirming…" : "Confirm requirements"}
            </Button>
          )}
          {requirements.status === "confirmed" && (
            <Link
              href={blueprintHref}
              className="block rounded-lg bg-emerald-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-emerald-500"
            >
              Generate blueprint →
            </Link>
          )}
        </div>
      )}
    </aside>
  );
}
