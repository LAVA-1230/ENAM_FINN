"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ResearchProgress } from "@/components/research-progress";
import { TopBar } from "@/components/shell";
import { Button, Empty, ErrorLine, Sheet, Skeleton } from "@/components/ui";
import { api, send } from "@/lib/api";

type Ready = { ready: { symbol: string; name: string; sector: string | null; is_holding: boolean; scorecard: string | null }[];
               known: { symbol: string; name: string }[] };

export default function ResearchPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [running, setRunning] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["research-ready"], queryFn: () => api<Ready>("/research/ready") });
  const sym = q.trim().toUpperCase();
  const matches = sym ? (data?.known || []).filter((k) => k.symbol.startsWith(sym) || k.name.toUpperCase().includes(sym)).slice(0, 5) : [];

  async function go(symbol: string) {
    setErr(null);
    const isReady = data?.ready.some((r) => r.symbol === symbol);
    if (isReady) return router.push(`/company/${encodeURIComponent(symbol)}`);
    try {
      await send(`/research/${encodeURIComponent(symbol)}`, "POST");
      setRunning(symbol);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <main>
      <TopBar title={<h1 className="text-title font-semibold">Research</h1>}
        sub="FINN reads the last 4 concall transcripts and the latest annual report of any NSE company." />
      <form className="mt-4 px-4" onSubmit={(e) => { e.preventDefault(); if (sym) go(sym); }}>
        <label htmlFor="ticker" className="text-sec font-semibold text-ink-2">NSE symbol</label>
        <div className="mt-1 flex gap-2">
          <input id="ticker" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. ASTRAL" autoCapitalize="characters" autoComplete="off"
            className="num min-h-[48px] min-w-0 flex-1 rounded-ctl border border-rule bg-sheet px-3 text-item uppercase text-ink placeholder:normal-case placeholder:text-ink-3" />
          <Button kind="primary" type="submit" disabled={!sym}>Read filings</Button>
        </div>
        {matches.length > 0 && !running && (
          <ul className="mt-1 rounded-ctl border border-rule bg-sheet">
            {matches.map((m) => (
              <li key={m.symbol}><button type="button" onClick={() => go(m.symbol)} className="row-press flex min-h-[44px] w-full items-center gap-3 border-t border-rule px-3 text-left first:border-t-0">
                <span className="num w-28 shrink-0 font-semibold">{m.symbol}</span><span className="truncate text-sec text-ink-2">{m.name}</span></button></li>
            ))}
          </ul>
        )}
        {err && <p className="mt-2 text-sec text-down">{err}</p>}
      </form>

      {running && (
        <Sheet className="mt-4">
          <ResearchProgress symbol={running} onReady={() => router.push(`/company/${encodeURIComponent(running)}`)} />
        </Sheet>
      )}

      <h2 className="mb-2 mt-6 px-4 text-sec font-semibold text-ink-2">Ready to explore</h2>
      {isLoading && <Skeleton />}
      {error && <ErrorLine error={error} />}
      {data && (data.ready.length ? (
        <Sheet>
          {data.ready.map((r) => (
            <Link key={r.symbol} href={`/company/${encodeURIComponent(r.symbol)}`} className="row-press block border-t border-rule px-4 py-3 first:border-t-0">
              <span className="block text-body font-semibold">{r.name} <span className="num font-normal text-ink-3">{r.symbol}</span></span>
              <span className="block text-sec text-ink-2">{r.scorecard || "Promise ledger ready"}{r.is_holding ? ", in your portfolio" : ""}</span>
            </Link>
          ))}
        </Sheet>
      ) : <Empty>No company has been read yet. Type a symbol above.</Empty>)}
    </main>
  );
}
