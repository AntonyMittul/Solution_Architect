"use client";

import { useEffect, useRef } from "react";

const RUN_EVENT_TYPES = [
  "run.status",
  "agent.started",
  "artifact.created",
  "message.created",
  "intake.awaiting_answer",
  "run.completed",
  "run.failed",
];

/**
 * Subscribe to a run's SSE event stream. `onEvent` is called with each event
 * type. Passing `runId = null` closes any open stream. The callback is held in
 * a ref so re-renders don't re-subscribe.
 */
export function useRunStream(runId: string | null, onEvent: (type: string) => void) {
  const callback = useRef(onEvent);
  callback.current = onEvent;

  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(`/api/v1/runs/${runId}/events`);
    for (const type of RUN_EVENT_TYPES) {
      source.addEventListener(type, () => callback.current(type));
    }
    return () => source.close();
  }, [runId]);
}
