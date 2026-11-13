"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/lib/api";
import type { ProgressStep } from "@/lib/types";
import { Num } from "./ui";

type Status = { symbol: string; name?: string; status: string; progress: ProgressStep[]; error: string | null };

const MARK: Record<string, string> = { done: "Done", running: "Reading", warn: "Partial", todo: "" };

/** Live research steps (spec 8.1), polled every 2s while running. */
export function ResearchProgress({ symbol, onReady }: { symbol: string; onReady?: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["research-status", symbol],
    queryFn: () => api<Status>(`/research/${encodeURIComponent(symbol)}/status`),
    refetchInterval: (q) => (q.state.data?.status === "running" || q.state.data?.status === "queued" ? 2000 : false),
  });
  useEffect(() => {
    if (data?.status === "ready") {
      qc.invalidateQueries({ queryKey: ["company", symbol] });
      onReady?.();
    }
  }, [data?.status, symbol, qc, onReady]);
  if (!data) return null;
  if (data.status === "failed") return <p className="px-4 py-3 text-body text-down">{data.error || "Research failed."}</p>;
  const done = data.progress.filter((p) => p.state === "done" || p.state === "warn").length;
  return (
    <div className="px-4 py-3">
      <p className="text-body">{data.status === "ready" ? "Ready." : `Reading ${data.name || symbol}'s filings. Usually under two minutes.`}</p>
      <ol className="mt-2">
        {data.progress.map((p) => (
          <li key={p.key} className="flex items-start justify-between gap-3 border-t border-rule py-2 first:border-t-0">
            <span className={`text-body ${p.state === "todo" ? "text-ink-3" : ""}`}>
              {p.label}
              {p.note && <span className="block text-sec text-ink-3">{p.note}</span>}
            </span>
            <span className={`shrink-0 text-sec font-semibold ${p.state === "running" ? "pulse" : ""} ${p.state === "warn" ? "text-down" : "text-ink-2"}`}>{MARK[p.state]}</span>
          </li>
        ))}
      </ol>
      <p className="mt-1 text-small text-ink-3"><Num>{done}</Num> of <Num>{data.progress.length}</Num> steps</p>
    </div>
  );
}
