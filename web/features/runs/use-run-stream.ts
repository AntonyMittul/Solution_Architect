"use client";

import { useEffect, useRef } from "react";

const RUN_EVENT_TYPES = [
  "run.status",
  "agent.started",
  "agent.completed",
  "artifact.created",
  "message.created",
  "intake.awaiting_answer",
  "blueprint.revising",
  "run.completed",
  "run.failed",
];

type EventPayload = Record<string, unknown> | undefined;

/**
 * Subscribe to a run's SSE event stream. `onEvent` is called with each event
 * type and its parsed payload. Passing `runId = null` closes any open stream.
 * The callback is held in a ref so re-renders don't re-subscribe.
 */
export function useRunStream(
  runId: string | null,
  onEvent: (type: string, payload: EventPayload) => void,
) {
  const callback = useRef(onEvent);
  callback.current = onEvent;

  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(`/api/v1/runs/${runId}/events`);
    for (const type of RUN_EVENT_TYPES) {
      source.addEventListener(type, (event) => {
        let payload: EventPayload;
        try {
          payload = JSON.parse((event as MessageEvent<string>).data).payload;
        } catch {
          payload = undefined;
        }
        callback.current(type, payload);
      });
    }
    return () => source.close();
  }, [runId]);
}
