"use client";

import { useCallback, useEffect, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  MarkerType,
  useNodesState,
  useEdgesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GitBranch } from "lucide-react";

export type AgentStatus = "pending" | "running" | "completed";

interface AgentGraphProps {
  agentStatuses: Record<string, AgentStatus>;
}

const AGENT_NODES: Array<{ id: string; label: string; x: number; y: number }> = [
  { id: "orchestrator", label: "🧠 Orchestrator", x: 380, y: 20 },
  { id: "sponsor", label: "💰 Sponsor Agent", x: 60, y: 160 },
  { id: "speaker", label: "🎤 Speaker Agent", x: 220, y: 160 },
  { id: "venue", label: "📍 Venue Agent", x: 380, y: 160 },
  { id: "pricing", label: "🎟️ Pricing Agent", x: 540, y: 160 },
  { id: "exhibitor", label: "🏢 Exhibitor Agent", x: 700, y: 160 },
  { id: "gtm", label: "📢 GTM Agent", x: 220, y: 300 },
  { id: "eventops", label: "📅 Event Ops", x: 540, y: 300 },
];

const EDGES: Edge[] = [
  "sponsor",
  "speaker",
  "venue",
  "pricing",
  "exhibitor",
  "gtm",
  "eventops",
].map((target) => ({
  id: `orchestrator-${target}`,
  source: "orchestrator",
  target,
  animated: true,
  markerEnd: { type: MarkerType.ArrowClosed },
  style: { stroke: "#475569", strokeWidth: 1.5 },
}));

function statusStyle(status: AgentStatus): {
  background: string;
  border: string;
  color: string;
  boxShadow: string;
} {
  switch (status) {
    case "running":
      return {
        background: "#1e3a5f",
        border: "2px solid #3b82f6",
        color: "#93c5fd",
        boxShadow: "0 0 12px rgba(59,130,246,0.4)",
      };
    case "completed":
      return {
        background: "#14532d",
        border: "2px solid #22c55e",
        color: "#86efac",
        boxShadow: "0 0 12px rgba(34,197,94,0.3)",
      };
    default:
      return {
        background: "#1e293b",
        border: "2px solid #334155",
        color: "#94a3b8",
        boxShadow: "none",
      };
  }
}

// Normalize agent name from SSE message to node id
function normalizeAgentName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes("sponsor")) return "sponsor";
  if (lower.includes("speaker") || lower.includes("artist")) return "speaker";
  if (lower.includes("venue")) return "venue";
  if (lower.includes("pricing") || lower.includes("footfall") || lower.includes("ticket"))
    return "pricing";
  if (lower.includes("exhibitor")) return "exhibitor";
  if (lower.includes("gtm") || lower.includes("community")) return "gtm";
  if (lower.includes("event ops") || lower.includes("eventops") || lower.includes("schedule"))
    return "eventops";
  if (lower.includes("orchestrat")) return "orchestrator";
  return "";
}

export default function AgentGraph({ agentStatuses }: AgentGraphProps) {
  // Build initial nodes
  const buildNodes = useCallback((statuses: Record<string, AgentStatus>): Node[] => {
    return AGENT_NODES.map(({ id, label, x, y }) => {
      const normalizedStatuses: Record<string, AgentStatus> = {};
      Object.keys(statuses).forEach((k) => {
        const normalized = normalizeAgentName(k);
        if (normalized) normalizedStatuses[normalized] = statuses[k];
      });

      const status: AgentStatus = normalizedStatuses[id] ?? "pending";
      const style = statusStyle(status);

      return {
        id,
        position: { x, y },
        data: { label },
        style: {
          ...style,
          borderRadius: "10px",
          padding: "10px 16px",
          fontSize: "12px",
          fontWeight: 600,
          cursor: "default",
          whiteSpace: "nowrap",
          transition: "all 0.4s ease",
        },
      };
    });
  }, []);

  const [nodes, setNodes, onNodesChange] = useNodesState(buildNodes({}));
  const [edges, , onEdgesChange] = useEdgesState(EDGES);

  useEffect(() => {
    setNodes(buildNodes(agentStatuses));
  }, [agentStatuses, buildNodes, setNodes]);

  const nodeTypes = useMemo(() => ({}), []);

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-primary" />
          <CardTitle className="text-base">Agent Execution Graph</CardTitle>
        </div>
        <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600 border border-slate-500 inline-block" />
            Pending
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-600 border border-blue-400 inline-block" />
            Running
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 border border-emerald-400 inline-block" />
            Completed
          </span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="h-[380px] w-full rounded-b-lg overflow-hidden border-t border-border/30">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            className="bg-black/30"
          >
            <Background color="#1e293b" gap={24} size={1} />
            <Controls
              showInteractive={false}
              className="!bg-card !border-border"
            />
          </ReactFlow>
        </div>
      </CardContent>
    </Card>
  );
}
