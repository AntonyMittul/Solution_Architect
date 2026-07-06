"use client";

import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { DiagramContent } from "@/lib/types";

// Column per component type gives a left-to-right architecture layout. Auto
// layout (dagre/elk) is a future refinement.
const COLUMN: Record<string, number> = {
  client: 0,
  external: 0,
  service: 1,
  queue: 1,
  api: 1,
  datastore: 2,
  database: 2,
  cache: 2,
};

const NODE_STYLE = {
  background: "#1e293b",
  color: "#e2e8f0",
  border: "1px solid #334155",
  borderRadius: 8,
  fontSize: 12,
  width: 170,
  padding: 6,
};

export function DiagramCanvas({ content }: { content: DiagramContent }) {
  const perColumn: Record<number, number> = {};
  const nodes: Node[] = (content.nodes ?? []).map((node) => {
    const col = COLUMN[node.type] ?? 1;
    const row = (perColumn[col] = (perColumn[col] ?? 0) + 1) - 1;
    return {
      id: node.id,
      position: { x: col * 240, y: row * 96 },
      data: { label: node.label },
      style: NODE_STYLE,
    };
  });

  const ids = new Set(nodes.map((n) => n.id));
  const edges: Edge[] = (content.edges ?? [])
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .map((edge, i) => ({
      id: `e${i}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      labelStyle: { fill: "#94a3b8", fontSize: 10 },
      style: { stroke: "#475569" },
    }));

  if (nodes.length === 0) {
    return <p className="text-sm text-slate-500">The diagram is empty.</p>;
  }

  return (
    <div className="h-[480px] overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
        <Background color="#1e293b" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
