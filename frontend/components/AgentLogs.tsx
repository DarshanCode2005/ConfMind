"use client";

import { useEffect, useRef, useState } from "react";
import { subscribeToAgentStatus } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Terminal, Circle } from "lucide-react";

interface LogLine {
  id: number;
  text: string;
  ts: string;
}

// Derive a tag and agent name from a log line like "[Sponsor Agent] Running..."
function parseLogLine(raw: string): {
  agent: string | null;
  body: string;
  type: "start" | "running" | "done" | "info";
} {
  const match = raw.match(/^\[([^\]]+)\]\s*(.*)$/);
  if (!match) return { agent: null, body: raw, type: "info" };

  const agent = match[1];
  const body = match[2].trim().toLowerCase();

  let type: "start" | "running" | "done" | "info" = "info";
  if (body.includes("start")) type = "start";
  else if (body.includes("running")) type = "running";
  else if (body.includes("complet") || body.includes("done") || body.includes("finish"))
    type = "done";

  return { agent, body: match[2], type };
}

function typeColor(t: "start" | "running" | "done" | "info"): string {
  switch (t) {
    case "start":
      return "text-blue-400";
    case "running":
      return "text-yellow-400";
    case "done":
      return "text-emerald-400";
    default:
      return "text-slate-400";
  }
}

function agentColor(t: "start" | "running" | "done" | "info"): string {
  switch (t) {
    case "start":
      return "bg-blue-400/10 text-blue-300 border-blue-400/20";
    case "running":
      return "bg-yellow-400/10 text-yellow-300 border-yellow-400/20";
    case "done":
      return "bg-emerald-400/10 text-emerald-300 border-emerald-400/20";
    default:
      return "bg-slate-400/10 text-slate-300 border-slate-400/20";
  }
}

interface AgentLogsProps {
  onAgentStatusChange?: (agent: string, status: "running" | "completed" | "pending") => void;
}

export default function AgentLogs({ onAgentStatusChange }: AgentLogsProps) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef(0);

  useEffect(() => {
    const cleanup = subscribeToAgentStatus(
      (line) => {
        setConnected(true);

        const id = ++counterRef.current;
        const ts = new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        setLogs((prev) => [...prev, { id, text: line, ts }]);

        // Notify parent about agent status
        const { agent, type } = parseLogLine(line);
        if (agent && onAgentStatusChange) {
          if (type === "running" || type === "start") {
            onAgentStatusChange(agent, "running");
          } else if (type === "done") {
            onAgentStatusChange(agent, "completed");
          }
        }

        // Detect completion
        if (
          line.toLowerCase().includes("orchestrat") &&
          (line.toLowerCase().includes("complet") || line.toLowerCase().includes("done"))
        ) {
          setDone(true);
        }
      },
      (_e) => {
        // SSE closed or errored
        setDone(true);
      }
    );

    return cleanup;
  }, [onAgentStatusChange]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <Card className="border-border/50 bg-card/80 backdrop-blur-sm shadow-sm">
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-primary" />
          <CardTitle className="text-base">Live Agent Execution</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          {done ? (
            <Badge
              variant="outline"
              className="bg-emerald-400/10 text-emerald-300 border-emerald-400/20 gap-1 text-xs"
            >
              <Circle className="w-2 h-2 fill-emerald-400" />
              Completed
            </Badge>
          ) : connected ? (
            <Badge
              variant="outline"
              className="bg-blue-400/10 text-blue-300 border-blue-400/20 gap-1 text-xs"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-400" />
              </span>
              Running
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="bg-slate-400/10 text-slate-300 border-slate-400/20 gap-1 text-xs"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-slate-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-400" />
              </span>
              Connecting...
            </Badge>
          )}
          <span className="text-xs text-muted-foreground tabular-nums">
            {logs.length} events
          </span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={scrollRef}
          className="h-64 overflow-y-auto font-mono text-xs bg-linear-to-b from-muted/20 to-background/70 rounded-b-lg border-t border-border/40 p-4 space-y-0.5"
        >
          {logs.length === 0 ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="animate-pulse">▋</span>
              <span>Waiting for agents to start...</span>
            </div>
          ) : (
            logs.map((log) => {
              const { agent, body, type } = parseLogLine(log.text);
              return (
                <div key={log.id} className="flex items-start gap-2 leading-5">
                  <span className="text-muted-foreground shrink-0 w-18">
                    {log.ts}
                  </span>
                  {agent && (
                    <span
                      className={`shrink-0 px-1.5 py-0 rounded text-[10px] border font-semibold leading-5 ${agentColor(type)}`}
                    >
                      {agent}
                    </span>
                  )}
                  <span className={typeColor(type)}>{agent ? body : log.text}</span>
                </div>
              );
            })
          )}
          {connected && !done && (
            <div className="flex items-center gap-1 text-muted-foreground pt-1">
              <span className="animate-pulse text-primary">▋</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
