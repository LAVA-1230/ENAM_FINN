"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { TopBar } from "@/components/shell";
import { BottomSheet, Button, ErrorLine, Num, Segmented, Sheet, Skeleton, Toggle } from "@/components/ui";
import { api, send } from "@/lib/api";
import { rupees, signedPct, tone } from "@/lib/fmt";
import type { Holding } from "@/lib/types";

type Sort = "weight" | "move" | "health";
const HEALTH = {
  green: { word: "Intact", cls: "text-up", dot: "var(--up)" },
  amber: { word: "Watch", cls: "text-ink", dot: "var(--ink-3)" },
  red: { word: "At risk", cls: "text-down", dot: "var(--down)" },
};

export default function PortfolioPage() {
  const qc = useQueryClient();
  const [sort, setSort] = useState<Sort>("weight");
  const [menu, setMenu] = useState<Holding | null>(null);
  const { data, error, isLoading } = useQuery({ queryKey: ["portfolio"], queryFn: () => api<{ total: number; count: number; holdings: Holding[]; eod_label: string | null }>("/portfolio") });

  const rows = [...(data?.holdings || [])].sort((a, b) =>
    sort === "weight" ? (b.weight || 0) - (a.weight || 0)
      : sort === "move" ? Math.abs(b.move?.ret || 0) - Math.abs(a.move?.ret || 0)
        : ["red", "amber", "green"].indexOf(a.health) - ["red", "amber", "green"].indexOf(b.health));

  async function patch(sym: string, body: object) {
    await send(`/portfolio/${encodeURIComponent(sym)}`, "PATCH", body);
    qc.invalidateQueries({ queryKey: ["portfolio"] });
    setMenu(null);
  }

  return (
    <main>
      <TopBar title={<h1 className="text-title font-semibold">Portfolio</h1>}
        sub={data ? <><Num>{data.count}</Num> holdings, <Num>{rupees(data.total)}</Num>{data.eod_label ? `, ${data.eod_label}` : ""}</> : null} />
      <div className="mt-3 px-4">
        <Segmented<Sort> label="Sort holdings" value={sort} onChange={setSort}
          options={[{ value: "weight", label: "By weight" }, { value: "move", label: "By move" }, { value: "health", label: "By thesis health" }]} />
        <p className="mt-2 text-small text-ink-3">Thesis health: intact (no warnings in 90 days), watch (one warning or a tripwire near), at risk (a tripwire hit or two weakening events).</p>
      </div>
      {isLoading && <Skeleton lines={10} />}
      {error && <ErrorLine error={error} />}
      {data && (
        <Sheet className="mt-3">
          {rows.map((h) => {
            const hl = HEALTH[h.health];
            return (
              <div key={h.symbol} className="flex border-t border-rule first:border-t-0">
                <Link href={`/company/${encodeURIComponent(h.symbol)}`} className="row-press flex min-w-0 flex-1 gap-3 py-3 pl-4">
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full" style={{ background: hl.dot }} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-body font-semibold">{h.name}</span>
                    <span className="block truncate text-sec text-ink-3">
                      <span className={hl.cls}>{hl.word}</span>
                      {h.muted_until ? ", muted" : h.only_p0 ? ", urgent only" : ""}: {h.note ? h.note.text : "No events this week"}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <Num className={`block text-body font-medium ${tone(h.move?.ret)}`}>{signedPct(h.move?.ret)}</Num>
                    <Num className="block text-sec text-ink-3">{h.weight?.toFixed(1)}%</Num>
                  </span>
                </Link>
                <button aria-label={`Options for ${h.name}`} onClick={() => setMenu(h)} className="flex w-11 shrink-0 items-center justify-center text-ink-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden><circle cx="12" cy="5" r="1.6" fill="currentColor" /><circle cx="12" cy="12" r="1.6" fill="currentColor" /><circle cx="12" cy="19" r="1.6" fill="currentColor" /></svg>
                </button>
              </div>
            );
          })}
        </Sheet>
      )}
      <BottomSheet open={!!menu} onClose={() => setMenu(null)} label="Holding options">
        {menu && (
          <div className="px-4 pb-6 pt-3">
            <h2 className="text-item font-semibold">{menu.name}</h2>
            <p className="text-sec text-ink-3"><Num>{menu.qty}</Num> shares{menu.avg_cost ? <>, average cost <Num>{rupees(menu.avg_cost)}</Num></> : ""}</p>
            <div className="mt-3">
              <Toggle label="Mute for 7 days" hint="Only urgent items get through" checked={!!menu.muted_until}
                onChange={(v) => patch(menu.symbol, { mute_days: v ? 7 : 0 })} />
              <Toggle label="Urgent only" hint="Everything else for this holding counts as routine" checked={menu.only_p0}
                onChange={(v) => patch(menu.symbol, { only_p0: v })} />
            </div>
            <Link href={`/company/${encodeURIComponent(menu.symbol)}?tab=story`} className="mt-4 block"><Button className="w-full">Edit thesis</Button></Link>
          </div>
        )}
      </BottomSheet>
    </main>
  );
}
