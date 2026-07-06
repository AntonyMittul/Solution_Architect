"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";

type RunEventItem = { seq: number; type: string; detail: string };

const STREAMED_EVENT_TYPES = ["run.status", "agent.token", "run.completed", "run.failed"];

export default function Playground() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [events, setEvents] = useState<RunEventItem[]>([]);
  const sourceRef = useRef<EventSource | null>(null);

  const startRun = useCallback(async () => {
    sourceRef.current?.close();
    setEvents([]);
    setStatus("creating…");

    const response = await fetch("/api/v1/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "ping" }),
    });
    if (!response.ok) {
      setStatus(`error (HTTP ${response.status})`);
      return;
    }
    const run: { id: string; status: string } = await response.json();
    setRunId(run.id);
    setStatus(run.status);

    const source = new EventSource(`/api/v1/runs/${run.id}/events`);
    sourceRef.current = source;
    for (const type of STREAMED_EVENT_TYPES) {
      source.addEventListener(type, (event) => {
        const message = event as MessageEvent<string>;
        const data: { payload: Record<string, unknown> } = JSON.parse(message.data);
        setEvents((prev) => [
          ...prev,
          { seq: Number(message.lastEventId), type, detail: JSON.stringify(data.payload) },
        ]);
        if (type === "run.completed" || type === "run.failed") {
          setStatus(type === "run.completed" ? "completed" : "failed");
          source.close();
        } else if (type === "run.status") {
          setStatus(String(data.payload.status));
        }
      });
    }
    source.onerror = () => {
      // EventSource auto-reconnects with Last-Event-ID; nothing to do here.
    };
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Run streaming playground</h1>
        <Link href="/dashboard" className="text-sm text-slate-400 hover:text-slate-200">
          ← Back to dashboard
        </Link>
      </div>
      <p className="text-sm text-slate-400">
        End-to-end proof: web → api → queue → worker → event log → SSE → web.
      </p>

      <div className="flex items-center gap-4">
        <button
          onClick={startRun}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 active:bg-indigo-700"
        >
          Run walking skeleton
        </button>
        <span className="text-sm text-slate-300">
          status: <span className="font-mono">{status}</span>
        </span>
      </div>

      {runId && <p className="text-xs text-slate-500">run {runId}</p>}

      <ul className="space-y-1">
        {events.map((event) => (
          <li
            key={event.seq}
            className="flex items-baseline gap-3 rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm"
          >
            <span className="w-6 text-right font-mono text-xs text-slate-500">{event.seq}</span>
            <span className="w-32 font-mono text-xs text-emerald-400">{event.type}</span>
            <span className="truncate font-mono text-xs text-slate-300">{event.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
