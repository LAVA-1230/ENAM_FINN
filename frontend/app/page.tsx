"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { EventRow, FyiRow } from "@/components/event-row";
import { Listen } from "@/components/listen";
import { TopBar } from "@/components/shell";
import { BottomSheet, Button, Empty, ErrorLine, Num, SectionLabel, Segmented, Sheet, Skeleton } from "@/components/ui";
import { api, send } from "@/lib/api";
import { rupees, signedPct, weekday } from "@/lib/fmt";
import type { Brief } from "@/lib/types";

type Win = "since_last_visit" | "24h" | "3d" | "7d" | "custom";

function Header({ b, w, onItem }: { b: Brief; w: string; onItem: (id: number | null) => void }) {
  const h = b.header;
  if (!h) return <div className="mx-4 mt-3 rounded-head bg-head p-4 text-on-head">No prices stored yet. Run the EOD price job.</div>;
  const total = h.contributors.reduce((s, c) => s + Math.abs(c.rs), 0) || 1;
  const shades = [1, 0.62, 0.4, 0.22];
  return (
    <section aria-label="Portfolio move" className="mx-4 mt-3 rounded-head bg-head p-4 text-on-head">
      <div className="flex items-baseline justify-between gap-3">
        <Num className="text-hero font-semibold">{signedPct(h.ret, 2)}</Num>
        <Num className="text-item font-semibold">{rupees(h.rs, true)}</Num>
      </div>
      <p className="mt-1 text-body text-on-head-2">{h.sentence}</p>
      <div className="mt-3 flex h-2.5 w-full overflow-hidden rounded-tag" aria-hidden>
        {h.contributors.map((c, i) => (
          <span key={i} style={{ width: `${(Math.abs(c.rs) / total) * 100}%`, background: "var(--on-head)", opacity: shades[i] ?? 0.2 }}
                className="h-full border-r border-head last:border-r-0" />
        ))}
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-3 text-small text-on-head-2">
        {h.contributors.map((c, i) => (
          <li key={i}>{c.symbol ? c.name.split(" ")[0] : c.name} <Num>{rupees(c.rs, true)}</Num></li>
        ))}
      </ul>
      <div className="mt-3 flex items-center justify-between gap-2">
        <Listen window={w} onItem={onItem} />
        <span className="text-small text-on-head-2">{h.freshness}</span>
      </div>
    </section>
  );
}

export default function BriefPage() {
  const [win, setWin] = useState<Win>("24h");
  const [custom, setCustom] = useState<{ from: string; to: string } | null>(null);
  const [pick, setPick] = useState(false);
  const [showRoutine, setShowRoutine] = useState(false);
  const [speaking, setSpeaking] = useState<number | null>(null);

  useEffect(() => {
    try { if (localStorage.getItem("finn-visited")) setWin("since_last_visit"); localStorage.setItem("finn-visited", "1"); } catch {}
    const t = setTimeout(() => send("/brief/seen", "POST").catch(() => {}), 8000);
    return () => clearTimeout(t);
  }, []);

  const qs = win === "custom" && custom ? `window=custom&from=${custom.from}&to=${custom.to}` : `window=${win}`;
  const { data: b, error, isLoading } = useQuery({ queryKey: ["brief", qs], queryFn: () => api<Brief>(`/brief?${qs}`) });
  const now = new Date();
  const part = now.getHours() < 12 ? "morning" : now.getHours() < 17 ? "afternoon" : "evening";

  return (
    <main>
      <TopBar sub={`${now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}, ${part} brief`} />
      <div className="mt-3 px-4">
        <Segmented<Win> label="Brief window" value={win} onChange={(v) => (v === "custom" ? setPick(true) : setWin(v))}
          options={[{ value: "since_last_visit", label: "Since last visit" }, { value: "24h", label: "24h" },
                    { value: "3d", label: "3 days" }, { value: "7d", label: "7 days" },
                    { value: "custom", label: custom && win === "custom" ? `${custom.from.slice(5)} to ${custom.to.slice(5)}` : "Custom" }]} />
      </div>

      {isLoading && <Skeleton lines={8} />}
      {error && <ErrorLine error={error} cached={!!b} />}
      {b && (
        <>
          <Header b={b} w={win === "custom" ? "7d" : win} onItem={setSpeaking} />

          {b.coming_up.length > 0 && (
            <div className="mt-3 flex items-baseline gap-3 overflow-x-auto px-4 no-scrollbar">
              <span className="shrink-0 text-sec font-semibold text-ink-2">Coming up</span>
              {b.coming_up.map((c) => (
                <Link key={c.symbol + c.date} href={`/company/${encodeURIComponent(c.symbol)}`} className="min-h-[44px] shrink-0 py-2 text-sec text-link">
                  {c.label} <Num>{weekday(c.date)}</Num>
                </Link>
              ))}
            </div>
          )}

          <SectionLabel>Needs you today ({b.counts.attention})</SectionLabel>
          {b.attention.length ? (
            <Sheet>{b.attention.map((e, i) => <EventRow key={e.id} e={e} active={speaking === e.id} draw={i === 0} />)}</Sheet>
          ) : (
            <Sheet><Empty>Nothing needs you {win === "24h" ? "today" : "in this window"}. {b.counts.routine} routine filings hidden.</Empty></Sheet>
          )}

          {b.tripwires.length > 0 && (
            <>
              <SectionLabel>Tripwires near your limit ({b.tripwires.length})</SectionLabel>
              <Sheet>
                {b.tripwires.map((t) => (
                  <Link key={t.id} href={`/company/${encodeURIComponent(t.symbol)}?tab=numbers`} className="row-press flex justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0">
                    <span className="text-body"><span className="font-medium">{t.company}:</span> {t.label}</span>
                    <span className={`shrink-0 text-sec font-semibold ${t.status === "hit" ? "text-down" : "text-ink"}`}>{t.status === "hit" ? "Hit" : "Near"}</span>
                  </Link>
                ))}
              </Sheet>
            </>
          )}

          {b.good_to_know.length > 0 && (
            <>
              <SectionLabel>For your information ({b.counts.good_to_know})</SectionLabel>
              <Sheet>{b.good_to_know.map((e) => <FyiRow key={e.id} e={e} />)}</Sheet>
            </>
          )}

          {b.routine.count > 0 && (
            <div className="mt-5 px-4">
              <div className="flex items-center justify-between">
                <span className="text-body text-ink-2">{b.routine.count} routine filings hidden</span>
                <Button kind="tertiary" onClick={() => setShowRoutine(!showRoutine)}>{showRoutine ? "Hide" : "Show"}</Button>
              </div>
              {showRoutine && (
                <Sheet className="-mx-4 mt-1">
                  {b.routine.groups.map((g) => (
                    <details key={g.label} className="border-t border-rule first:border-t-0">
                      <summary className="flex min-h-[48px] cursor-pointer items-center justify-between px-4 text-body">
                        <span>{g.label} <span className="text-ink-3">({g.companies} {g.companies === 1 ? "company" : "companies"})</span></span>
                        <Num className="text-ink-3">{g.count}</Num>
                      </summary>
                      <ul className="pb-2">
                        {g.items.map((it) => (
                          <li key={it.id}><Link href={`/event/${it.id}`} className="block px-4 py-1.5 text-sec text-ink-2">{it.company}: {it.title} <span className="text-ink-3">{it.date_ist}</span></Link></li>
                        ))}
                      </ul>
                    </details>
                  ))}
                </Sheet>
              )}
            </div>
          )}

          <p className="mt-6 px-4 text-small text-ink-3">
            {b.freshness.filings_checked ? `Checked filings ${b.freshness.filings_checked}. ` : "Filings not checked yet. "}
            {b.freshness.eod_label ? `Prices are end of day, last close ${b.freshness.eod_label.replace(/^EOD /, "")}.` : "Prices are end of day."}
          </p>
        </>
      )}
      <CustomRange open={pick} onClose={() => setPick(false)} onPick={(r) => { setCustom(r); setWin("custom"); setPick(false); }} />
    </main>
  );
}

function CustomRange({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (r: { from: string; to: string }) => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10);
  const [from, setFrom] = useState(weekAgo);
  const [to, setTo] = useState(today);
  return (
    <BottomSheet open={open} onClose={onClose} label="Custom window">
      <form className="px-4 pb-6 pt-3" onSubmit={(e) => { e.preventDefault(); if (from <= to) onPick({ from, to }); }}>
        <h2 className="text-item font-semibold">Custom window</h2>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="text-sec text-ink-2">From
            <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)}
              className="num mt-1 block min-h-[48px] w-full rounded-ctl border border-rule bg-paper px-2 text-body text-ink" />
          </label>
          <label className="text-sec text-ink-2">To
            <input type="date" value={to} min={from} max={today} onChange={(e) => setTo(e.target.value)}
              className="num mt-1 block min-h-[48px] w-full rounded-ctl border border-rule bg-paper px-2 text-body text-ink" />
          </label>
        </div>
        <Button kind="primary" type="submit" className="mt-5 w-full">Show this window</Button>
      </form>
    </BottomSheet>
  );
}
