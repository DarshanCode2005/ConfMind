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

const AGENT_NODES: Array<{ id: string; label: string; x: number; y: number; tool: string }> = [
  // Layer 1: Input & Probe
  { id: "phq_probe", label: "🔍 PHQ Probe", x: 380, y: 0, tool: "predicthq" },

  // Layer 2: Web Agents
  { id: "web_search_1", label: "🌐 Web Agent 1", x: 180, y: 100, tool: "tavily" },
  { id: "web_search_2", label: "🌐 Web Agent 2", x: 380, y: 100, tool: "tavily" },
  { id: "web_search_3", label: "🌐 Web Agent 3", x: 580, y: 100, tool: "tavily" },

  // Shared Memory (Center)
  { id: "shared_memory", label: "💾 Shared Memory", x: 380, y: 200, tool: "memory" },

  // Layer 3: Discovery
  { id: "sponsor", label: "💰 Sponsor Agent", x: 60, y: 300, tool: "discovery" },
  { id: "speaker", label: "🎤 Speaker Agent", x: 270, y: 300, tool: "discovery" },
  { id: "venue", label: "📍 Venue Agent", x: 490, y: 300, tool: "discovery" },
  { id: "exhibitor", label: "🏢 Exhibitor Agent", x: 700, y: 300, tool: "discovery" },

  // Layer 4: Analytics
  { id: "pricing", label: "🎟️ Pricing Agent", x: 180, y: 420, tool: "analytics" },
  { id: "gtm", label: "📢 GTM Agent", x: 380, y: 420, tool: "analytics" },
  { id: "eventops", label: "📅 Event Ops", x: 580, y: 420, tool: "analytics" },

  // Final Aggregation
  { id: "revenue", label: "📈 Revenue Agent", x: 380, y: 540, tool: "revenue" },
];

const EDGES: Edge[] = [
  // PHQ to Web Agents
  { id: "p-w1", source: "phq_probe", target: "web_search_1", animated: true },
  { id: "p-w2", source: "phq_probe", target: "web_search_2", animated: true },
  { id: "p-w3", source: "phq_probe", target: "web_search_3", animated: true },

  // Web Agents to Memory
  { id: "w1-m", source: "web_search_1", target: "shared_memory", animated: true },
  { id: "w2-m", source: "web_search_2", target: "shared_memory", animated: true },
  { id: "w3-m", source: "web_search_3", target: "shared_memory", animated: true },

  // Memory to Discovery
  { id: "m-sp", source: "shared_memory", target: "sponsor", animated: true },
  { id: "m-sk", source: "shared_memory", target: "speaker", animated: true },
  { id: "m-ve", source: "shared_memory", target: "venue", animated: true },
  { id: "m-ex", source: "shared_memory", target: "exhibitor", animated: true },

  // Discovery to Analytics
  { id: "ve-pr", source: "venue", target: "pricing", animated: true },
  { id: "sp-pr", source: "sponsor", target: "pricing", animated: true },
  { id: "sk-pr", source: "speaker", target: "pricing", animated: true },
  { id: "pr-gt", source: "pricing", target: "gtm", animated: true },
  { id: "ex-gt", source: "exhibitor", target: "gtm", animated: true },

  // Analytics pipeline
  { id: "gt-eo", source: "gtm", target: "eventops", animated: true },
  { id: "eo-rv", source: "eventops", target: "revenue", animated: true },
].map(edge => ({
  ...edge,
  markerEnd: { type: MarkerType.ArrowClosed },
  style: { stroke: "#475569", strokeWidth: 1.5 },
}));

function statusStyle(status: AgentStatus, toolType?: string): {
  background: string;
  border: string;
  color: string;
  boxShadow: string;
} {
  const toolColors: Record<string, string> = {
    predicthq: "#14b8a6",
    tavily: "#a855f7",
    memory: "#fb923c",
    discovery: "#3b82f6",
    analytics: "#22c55e",
    revenue: "#64748b",
  };

  const primaryColor = toolType ? toolColors[toolType] : "#3b82f6";

  switch (status) {
    case "running":
      return {
        background: "rgba(30, 58, 95, 0.8)",
        border: `2px solid ${primaryColor}`,
        color: primaryColor,
        boxShadow: `0 0 15px ${primaryColor}66`,
      };
    case "completed":
      return {
        background: "rgba(20, 83, 45, 0.8)",
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
  if (lower.includes("phq_probe")) return "phq_probe";
  if (lower.includes("web_search_agent_1") || lower.includes("web_search_1")) return "web_search_1";
  if (lower.includes("web_search_agent_2") || lower.includes("web_search_2")) return "web_search_2";
  if (lower.includes("web_search_agent_3") || lower.includes("web_search_3")) return "web_search_3";
  if (lower.includes("sponsor")) return "sponsor";
  if (lower.includes("speaker") || lower.includes("artist")) return "speaker";
  if (lower.includes("venue")) return "venue";
  if (lower.includes("pricing") || lower.includes("footfall") || lower.includes("ticket"))
    return "pricing";
  if (lower.includes("exhibitor")) return "exhibitor";
  if (lower.includes("gtm") || lower.includes("community")) return "gtm";
  if (lower.includes("event ops") || lower.includes("eventops") || lower.includes("schedule"))
    return "eventops";
  if (lower.includes("revenue")) return "revenue";
  return "";
}

export default function AgentGraph({ agentStatuses }: AgentGraphProps) {
  // Build initial nodes
  const buildNodes = useCallback((statuses: Record<string, AgentStatus>): Node[] => {
    return AGENT_NODES.map(({ id, label, x, y, tool }) => {
      const normalizedStatuses: Record<string, AgentStatus> = {};
      Object.keys(statuses).forEach((k) => {
        const normalized = normalizeAgentName(k);
        if (normalized) normalizedStatuses[normalized] = statuses[k];
      });

      const status: AgentStatus = normalizedStatuses[id] ?? "pending";
      const style = statusStyle(status, tool);

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
            <span className="w-2.5 h-2.5 rounded-full bg-teal-500 border border-teal-400 inline-block" />
            PHQ Probe
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500 border border-purple-400 inline-block" />
            Web Search
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-orange-500 border border-orange-400 inline-block" />
            Memory
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 border border-blue-400 inline-block" />
            Discovery
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-emerald-400 inline-block" />
            Analytics
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
