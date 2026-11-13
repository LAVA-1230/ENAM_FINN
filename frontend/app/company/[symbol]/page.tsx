"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { DecideSheet } from "@/components/decide-sheet";
import { IconBack } from "@/components/icons";
import { useSheets } from "@/components/providers";
import { ResearchProgress } from "@/components/research-progress";
import { TopBar } from "@/components/shell";
import { Button, Empty, ErrorLine, Num, Quote, Segmented, Sheet, Skeleton, Urgency } from "@/components/ui";
import { api, send } from "@/lib/api";
import { crore, price, pts, rupees, signedPct, tone } from "@/lib/fmt";
import type { Company, EventCard, PromiseRow, Scorecard, Tripwire } from "@/lib/types";

type Tab = "promises" | "numbers" | "timeline" | "story" | "prep";

const VERDICT: Record<string, { word: string; cls: string }> = {
  kept: { word: "Kept", cls: "text-up font-semibold" }, missed: { word: "Missed", cls: "text-down font-semibold" },
  late: { word: "Late", cls: "text-ink font-semibold" }, behind: { word: "Behind", cls: "text-ink font-semibold" },
  on_track: { word: "On track", cls: "text-ink-2 font-medium" }, dropped: { word: "Dropped", cls: "text-ink-3 font-medium" },
  pending: { word: "Pending", cls: "text-ink-3 font-medium" },
};

function ScoreHead({ s }: { s: Scorecard }) {
  const segs = [["kept", 1], ["late", 0.55], ["missed", 0.3]] as const;
  return (
    <section className="mx-4 mt-3 rounded-head bg-head p-4 text-on-head">
      <p className="text-item font-semibold">{s.sentence}</p>
      {s.due > 0 && (
        <>
          <div className="mt-3 flex h-2.5 overflow-hidden rounded-tag" aria-hidden>
            {segs.map(([k, o]) => (s.counts[k] ? <span key={k} style={{ width: `${(s.counts[k] / s.due) * 100}%`, background: "var(--on-head)", opacity: o }} className="border-r border-head last:border-r-0" /> : null))}
          </div>
          <p className="mt-1.5 text-small text-on-head-2">
            {segs.filter(([k]) => s.counts[k]).map(([k]) => `${VERDICT[k].word} ${s.counts[k]}`).join(", ")}
          </p>
        </>
      )}
      <p className="mt-2 text-small text-on-head-2">
        {Object.entries(s.counts).filter(([k]) => !["kept", "late", "missed"].includes(k)).map(([k, n]) => `${VERDICT[k]?.word || k} ${n}`).join(", ")}
        {s.total ? ` of ${s.total} promises from the last four concalls` : ""}
      </p>
    </section>
  );
}

function Promises({ symbol }: { symbol: string }) {
  const { openSource } = useSheets();
  const [filter, setFilter] = useState("all");
  const { data, isLoading, error } = useQuery({ queryKey: ["promises", symbol], queryFn: () => api<{ scorecard: Scorecard; promises: PromiseRow[] }>(`/companies/${encodeURIComponent(symbol)}/promises`) });
  if (isLoading) return <Skeleton lines={6} />;
  if (error) return <ErrorLine error={error} />;
  if (!data?.promises.length) return <Empty>No explicit, numbered commitments found in the last four concalls.</Empty>;
  const statuses = Array.from(new Set(data.promises.map((p) => p.status)));
  const rows = data.promises.filter((p) => filter === "all" || p.status === filter);
  return (
    <>
      <ScoreHead s={data.scorecard} />
      {statuses.length > 1 && (
        <div className="mt-3 px-4">
          <Segmented label="Filter by verdict" value={filter} onChange={setFilter}
            options={[{ value: "all", label: "All" }, ...statuses.map((s) => ({ value: s, label: VERDICT[s]?.word || s }))]} />
        </div>
      )}
      <Sheet className="mt-3">
        {rows.map((p) => (
          <article key={p.id} className="border-t border-rule px-4 py-4 first:border-t-0">
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="text-item font-semibold">{p.metric}</h3>
              <span className={`shrink-0 text-sec ${VERDICT[p.status]?.cls}`}>{VERDICT[p.status]?.word || p.status}</span>
            </div>
            <p className="text-sec text-ink-2">Target: <Num>{p.target_text}</Num>{p.horizon ? ` for ${p.horizon}` : ""}</p>
            <p className={`mt-2 text-body ${p.status === "dropped" ? "line-through decoration-ink-3" : ""}`}><Quote>{p.quote}</Quote></p>
            {p.actual_text && <p className="mt-2 text-body">{p.actual_text}</p>}
            {p.revisions.map((r, i) => <p key={i} className="mt-1 text-sec text-ink-2">Guidance changed: {p.target_text} to {r.target_text} ({r.made_in} call)</p>)}
            {p.repeats.length > 0 && p.revisions.length === 0 && <p className="mt-1 text-sec text-ink-3">Repeated in the {p.repeats.join(", ")} call{p.repeats.length > 1 ? "s" : ""}</p>}
            <div className="mt-2 flex flex-wrap gap-x-4">
              <button className="min-h-[36px] text-sec text-link" onClick={() => openSource({ n: 0, label: `${p.source.label}${p.speaker ? `, ${p.speaker}` : ""}`, kind: "document", url: p.source.url, page: p.page, excerpt: p.quote })}>
                {p.source.label}
              </button>
              {p.evidence.map((ev, i) => (
                ev.url ? <a key={i} href={ev.url} target="_blank" rel="noreferrer" className="flex min-h-[36px] items-center text-sec text-link">{ev.label}</a>
                  : <span key={i} className="flex min-h-[36px] items-center text-sec text-ink-3">{ev.label}</span>
              ))}
            </div>
          </article>
        ))}
      </Sheet>
      <p className="mt-3 px-4 text-small text-ink-3">Quotes are copied from concall transcripts. Verdicts on numbers are computed from reported results, never by a language model.</p>
    </>
  );
}

type Fin = { title: string; basis: string | null; quarters: { label: string; revenue: number | null; opm: number | null; pat: number | null }[];
  revenue_cagr_3y: number | null; pat_cagr_3y: number | null; source: { label: string; url: string } };

function RevenueChart({ f }: { f: Fin }) {
  const q = f.quarters.slice(-8);
  const max = Math.max(...q.map((x) => x.revenue || 0)) || 1;
  const m = q.map((x) => x.opm).filter((x): x is number => x != null);
  const [sel, setSel] = useState(q.length - 1);
  const mMin = Math.min(...m), mMax = Math.max(...m);
  const y = (v: number) => 34 - ((v - mMin) / ((mMax - mMin) || 1)) * 28;
  const W = 100 / q.length;
  return (
    <div className="px-4">
      <h3 className="text-body font-semibold">{f.title}</h3>
      <svg viewBox="0 0 100 34" className="mt-2 h-10 w-full overflow-visible" preserveAspectRatio="none" aria-hidden>
        <polyline fill="none" stroke="var(--link)" strokeWidth="0.8" vectorEffect="non-scaling-stroke"
          points={q.map((x, i) => (x.opm != null ? `${i * W + W / 2},${y(x.opm)}` : "")).filter(Boolean).join(" ")} />
      </svg>
      <div className="flex h-28 items-end gap-1" role="list" aria-label="Quarterly revenue">
        {q.map((x, i) => (
          <button key={x.label} role="listitem" onClick={() => setSel(i)} aria-label={`${x.label}: revenue ${crore(x.revenue)}, margin ${x.opm?.toFixed(1)}%`}
            className="flex h-full flex-1 flex-col justify-end">
            <span className="block w-full rounded-t-[2px] bg-ink" style={{ height: `${((x.revenue || 0) / max) * 100}%`, opacity: i === sel ? 1 : 0.25 }} />
          </button>
        ))}
      </div>
      <div className="flex gap-1 border-t border-ink pt-1">
        {q.map((x, i) => <span key={x.label} className={`num flex-1 text-center text-small ${i === sel ? "text-ink" : "text-ink-3"}`}>{x.label.split(" ")[0]}</span>)}
      </div>
      <p className="mt-2 text-sec"><Num>{q[sel]?.label}: revenue {crore(q[sel]?.revenue)}, EBITDA margin {q[sel]?.opm?.toFixed(1)}%, PAT {crore(q[sel]?.pat)}</Num></p>
      <p className="text-small text-ink-3">Bars: revenue. Line: EBITDA margin. {f.basis ? `${f.basis[0].toUpperCase()}${f.basis.slice(1)} figures. ` : ""}<a href={f.source.url} target="_blank" rel="noreferrer" className="text-link">{f.source.label}</a></p>
    </div>
  );
}

const FLAG: Record<string, string> = { healthy: "Healthy", watch: "Watch", red: "Red flag" };

function Numbers({ symbol }: { symbol: string }) {
  const fin = useQuery({ queryKey: ["fin", symbol], queryFn: () => api<Fin>(`/companies/${encodeURIComponent(symbol)}/financials`) });
  const cash = useQuery({ queryKey: ["cash", symbol], queryFn: () => api<any>(`/companies/${encodeURIComponent(symbol)}/cash`) });
  return (
    <div className="pt-4">
      {fin.isLoading ? <Skeleton /> : fin.data?.quarters.length ? <RevenueChart f={fin.data} /> : <Empty>No quarterly table yet.</Empty>}
      {fin.data && (fin.data.revenue_cagr_3y != null || fin.data.pat_cagr_3y != null) && (
        <p className="mt-3 px-4 text-sec text-ink-2">3-year growth: revenue <Num className={tone(fin.data.revenue_cagr_3y)}>{signedPct(fin.data.revenue_cagr_3y)}</Num> a year, PAT <Num className={tone(fin.data.pat_cagr_3y)}>{signedPct(fin.data.pat_cagr_3y)}</Num> a year</p>
      )}
      <h2 className="mb-2 mt-6 px-4 text-sec font-semibold text-ink-2">Cash quality</h2>
      {cash.data?.available ? (
        <Sheet>
          {cash.data.rows.map((r: any) => (
            <div key={r.key} className="flex items-start justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0">
              <div><p className="text-body">{r.label}</p><p className="num text-sec text-ink-3">{r.detail}</p></div>
              <div className="text-right"><Num className="block text-item font-semibold">{r.value}</Num>
                <span className={`text-sec ${r.flag === "red" ? "font-semibold text-down" : r.flag === "watch" ? "font-semibold text-ink" : "text-ink-3"}`}>{FLAG[r.flag]}</span></div>
            </div>
          ))}
          <p className="border-t border-rule px-4 py-2 text-small text-ink-3">{cash.data.source}</p>
        </Sheet>
      ) : <Empty>Cash-flow history isn't loaded for this company.</Empty>}
      <Tripwires symbol={symbol} />
    </div>
  );
}

function Tripwires({ symbol }: { symbol: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["tripwires", symbol], queryFn: () => api<{ tripwires: Tripwire[]; metrics: Record<string, string> }>(`/companies/${encodeURIComponent(symbol)}/tripwires`) });
  const [edit, setEdit] = useState<Record<number, string>>({});
  if (!data?.tripwires.length) return null;
  async function save() {
    const items = data!.tripwires.map((t) => ({ id: t.id, metric_key: t.metric_key, op: t.op, enabled: t.enabled,
      threshold: edit[t.id] !== undefined && edit[t.id] !== "" ? Number(edit[t.id]) : t.threshold }));
    await send(`/companies/${encodeURIComponent(symbol)}/tripwires`, "PUT", items);
    setEdit({});
    qc.invalidateQueries({ queryKey: ["tripwires", symbol] });
  }
  return (
    <>
      <h2 className="mb-2 mt-6 px-4 text-sec font-semibold text-ink-2">Tripwires: your sell-review triggers</h2>
      <Sheet>
        {data.tripwires.map((t) => (
          <div key={t.id} className="flex items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0">
            <div className="min-w-0">
              <p className="text-body">{t.label}</p>
              <p className="text-sec text-ink-3">Now <Num>{t.value_label}</Num>, limit {t.op} <Num>{t.threshold_label}</Num>{t.source === "auto" ? ", set by FINN" : ""}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span className={`text-sec font-semibold ${t.status === "hit" ? "text-down" : t.status === "near" ? "text-ink" : "text-ink-3"}`}>{t.status === "hit" ? "Hit" : t.status === "near" ? "Near" : "OK"}</span>
              <label className="sr-only" htmlFor={`tw-${t.id}`}>Limit for {t.label}</label>
              <input id={`tw-${t.id}`} inputMode="decimal" className="num h-11 w-16 rounded-ctl border border-rule bg-paper px-2 text-right text-body text-ink"
                value={edit[t.id] ?? String(t.threshold)} onChange={(e) => setEdit({ ...edit, [t.id]: e.target.value })} />
            </div>
          </div>
        ))}
      </Sheet>
      {Object.keys(edit).length > 0 && <div className="px-4 pt-3"><Button onClick={save} className="w-full">Save limits</Button></div>}
    </>
  );
}

function Timeline({ symbol }: { symbol: string }) {
  const [tier, setTier] = useState("all");
  const { data, isLoading } = useQuery({ queryKey: ["timeline", symbol, tier], queryFn: () => api<{ events: EventCard[] }>(`/companies/${encodeURIComponent(symbol)}/timeline?limit=80${tier === "all" ? "" : `&tier=${tier}`}`) });
  return (
    <div className="pt-3">
      <div className="px-4"><Segmented label="Filter" value={tier} onChange={setTier}
        options={[{ value: "all", label: "All" }, { value: "P0,P1", label: "Urgent and today" }, { value: "P2", label: "FYI" }, { value: "P3", label: "Routine" }]} /></div>
      {isLoading ? <Skeleton /> : !data?.events.length ? <Empty>No filings or alerts stored for this company yet.</Empty> : (
        <Sheet className="mt-3">
          {data.events.map((e) => (
            <Link key={e.id} href={`/event/${e.id}`} className="row-press flex gap-3 border-t border-rule px-4 py-3 first:border-t-0">
              <Num className="w-14 shrink-0 text-small text-ink-3">{e.date_ist}</Num>
              <span className="min-w-0 flex-1 text-body"><Urgency tier={e.tier} /> {e.title}</span>
            </Link>
          ))}
        </Sheet>
      )}
    </div>
  );
}

function Story({ symbol, company }: { symbol: string; company: Company }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["story", symbol], queryFn: () => api<any>(`/companies/${encodeURIComponent(symbol)}/story`) });
  const [thesis, setThesis] = useState<string | null>(null);
  const b = data?.business;
  async function saveThesis() {
    await send(`/portfolio/${encodeURIComponent(symbol)}`, "PATCH", { thesis });
    setThesis(null);
    qc.invalidateQueries({ queryKey: ["company", symbol] });
  }
  return (
    <div className="pt-4">
      {company.is_holding && (
        <section className="px-4">
          <h2 className="text-sec font-semibold text-ink-2">Your thesis</h2>
          {thesis === null ? (
            <>
              <p className="mt-1 text-body">{company.thesis || "No thesis written yet."}</p>
              <p className="text-small text-ink-3">{company.thesis_source === "concall" ? "Pre-filled from management's own words; edit it to make it yours." : ""}</p>
              <Button kind="tertiary" className="-ml-4" onClick={() => setThesis(company.thesis || "")}>Edit thesis</Button>
            </>
          ) : (
            <div className="mt-1">
              <textarea value={thesis} onChange={(e) => setThesis(e.target.value)} rows={3} maxLength={600} aria-label="Thesis"
                className="w-full rounded-ctl border border-rule bg-sheet p-3 text-body text-ink" />
              <div className="flex gap-3"><Button onClick={saveThesis}>Save</Button><Button kind="tertiary" onClick={() => setThesis(null)}>Cancel</Button></div>
            </div>
          )}
        </section>
      )}
      {isLoading ? <Skeleton /> : (
        <>
          <h2 className="mb-2 mt-6 px-4 text-sec font-semibold text-ink-2">The business</h2>
          {b?.available && b.segments?.length > 0 ? (
            <Sheet>
              {b.segments.map((s: any) => (
                <div key={s.name} className="border-t border-rule px-4 py-3 first:border-t-0">
                  <div className="flex justify-between"><span className="text-body font-medium">{s.name}</span><Num>{s.share_pct != null ? `${s.share_pct.toFixed(0)}%` : ""}</Num></div>
                  {s.share_pct != null && <div className="mt-1 h-1.5 rounded-tag bg-rule"><div className="h-full rounded-tag bg-ink" style={{ width: `${s.share_pct}%` }} /></div>}
                  {s.line && <p className="mt-1 text-sec text-ink-2">{s.line}</p>}
                </div>
              ))}
              <p className="border-t border-rule px-4 py-2 text-small text-ink-3">{b.document?.label}{b.period ? `, ${b.period}` : ""}</p>
            </Sheet>
          ) : b?.available && b.quotes?.length ? (
            <Sheet>{b.quotes.map((q: any, i: number) => <p key={i} className="border-t border-rule px-4 py-3 text-body first:border-t-0"><Quote>{q.text}</Quote> <span className="text-small text-ink-3">{b.document?.label}, p.{q.page}</span></p>)}</Sheet>
          ) : <Empty>Business mix appears once FINN has read the annual report.</Empty>}
          {(["bull", "bear"] as const).map((side) => (
            <section key={side}>
              <h2 className="mb-2 mt-6 px-4 text-sec font-semibold text-ink-2">{side === "bull" ? "The case for" : "The case against"}</h2>
              {data?.bullbear?.[side]?.length ? (
                <Sheet>
                  {data.bullbear[side].map((p: any, i: number) => (
                    <div key={i} className={`border-t border-rule border-l-2 px-4 py-3 first:border-t-0 ${side === "bull" ? "border-l-up" : "border-l-down"}`}>
                      <p className="text-body"><span className={side === "bull" ? "text-up" : "text-down"}>{side === "bull" ? "+" : "−"}</span> {p.text}</p>
                      <p className="text-small text-ink-3">From the {p.card} card: {p.fact}</p>
                    </div>
                  ))}
                </Sheet>
              ) : <Empty>Not enough evidence for this side yet.</Empty>}
            </section>
          ))}
          <p className="mt-3 px-4 text-small text-ink-3">{data?.footnote}</p>
        </>
      )}
      {company.decisions.length > 0 && (
        <>
          <h2 className="mb-2 mt-6 px-4 text-sec font-semibold text-ink-2">Your decisions</h2>
          <Sheet>{company.decisions.map((d) => <p key={d.id} className="border-t border-rule px-4 py-2.5 text-body first:border-t-0"><Num className="text-sec text-ink-3">{d.date}</Num> <b className="capitalize">{d.action}</b>{d.note ? `: ${d.note}` : ""}</p>)}</Sheet>
        </>
      )}
    </div>
  );
}

function Prep({ symbol }: { symbol: string }) {
  const { data, isLoading } = useQuery({ queryKey: ["prep", symbol], queryFn: () => api<{ questions: { text: string; why: string }[]; coming_up: { date: string; purpose: string }[] }>(`/companies/${encodeURIComponent(symbol)}/prep`) });
  if (isLoading) return <Skeleton />;
  return (
    <div className="pt-4">
      {data?.coming_up[0] && <p className="px-4 text-body">Next: {data.coming_up[0].purpose} on <Num>{data.coming_up[0].date}</Num></p>}
      <h2 className="mb-2 mt-4 px-4 text-sec font-semibold text-ink-2">Questions to ask on the call</h2>
      {data?.questions.length ? (
        <Sheet>{data.questions.map((q, i) => <div key={i} className="border-t border-rule px-4 py-3 first:border-t-0"><p className="text-body"><Num>{i + 1}.</Num> {q.text}</p><p className="text-small text-ink-3">Why: {q.why}</p></div>)}</Sheet>
      ) : <Empty>No missed promises, near tripwires or management changes to raise.</Empty>}
    </div>
  );
}

function CompanyInner() {
  const { symbol: raw } = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(raw).toUpperCase();
  const router = useRouter();
  const sp = useSearchParams();
  const qc = useQueryClient();
  const { openAsk } = useSheets();
  const [tab, setTab] = useState<Tab>((sp.get("tab") as Tab) || "promises");
  const [decide, setDecide] = useState(false);
  const [started, setStarted] = useState(false);
  const { data: c, error, isLoading } = useQuery({ queryKey: ["company", symbol], queryFn: () => api<Company>(`/companies/${encodeURIComponent(symbol)}`), retry: false });

  async function startResearch() {
    await send(`/research/${encodeURIComponent(symbol)}`, "POST");
    setStarted(true);
    qc.invalidateQueries({ queryKey: ["research-status", symbol] });
  }

  const back = (
    <button onClick={() => (history.length > 1 ? router.back() : router.push("/portfolio"))} className="-ml-2 flex min-h-[44px] items-center gap-1 pr-2 text-body text-link">
      <IconBack size={20} /> Back
    </button>
  );
  const ex = c?.exposure;
  const mv = ex?.move;
  const ready = c?.research.status === "ready";
  const running = started || c?.research.status === "running";

  return (
    <main>
      <TopBar back={back} ask={{ symbol, label: c?.name || symbol }} />
      {isLoading && <Skeleton lines={8} />}
      {error && !c && (
        <div className="px-4 py-4">
          <p className="text-body">{(error as Error).message}</p>
          {!started ? <Button kind="primary" className="mt-3 w-full" onClick={startResearch}>Read {symbol}'s filings</Button> : <ResearchProgress symbol={symbol} onReady={() => qc.invalidateQueries({ queryKey: ["company", symbol] })} />}
        </div>
      )}
      {c && (
        <>
          <header className="px-4 pt-2">
            <p className="text-sec text-ink-3">{c.symbol}, {c.exchange}{c.sector ? `, ${c.sector}` : ""}</p>
            <h1 className="text-title font-semibold">{c.name}</h1>
            {c.price && (
              <p className="mt-1"><Num className="text-item font-semibold">{price(c.price.close)}</Num>{" "}
                {mv && <Num className={`text-body ${tone(mv.ret)}`}>{signedPct(mv.ret)}</Num>}{" "}
                <span className="text-small text-ink-3">{c.price.label}</span></p>
            )}
            {mv && mv.specific != null && (
              <p className="text-sec text-ink-2">{mv.index} <Num className={tone(mv.index_ret)}>{signedPct(mv.index_ret)}</Num>, stock-specific <Num className={tone(mv.specific)}>{pts(mv.specific)}</Num></p>
            )}
            {ex?.held && (
              <p className="text-sec text-ink-2"><Num>{ex.weight?.toFixed(1)}%</Num> of your book, {ex.pnl_rs != null && <>P&amp;L <Num className={tone(ex.pnl_rs)}>{rupees(ex.pnl_rs, true)}</Num> ({signedPct(ex.pnl_pct)})</>}</p>
            )}
          </header>

          {!ready && (
            <Sheet className="mt-4">
              {running ? <ResearchProgress symbol={symbol} /> : (
                <div className="px-4 py-4">
                  <p className="text-body">FINN hasn't read this company's concall transcripts and annual report yet.</p>
                  {c.research.error && <p className="mt-1 text-sec text-down">Last attempt: {c.research.error}</p>}
                  <Button kind="primary" className="mt-3 w-full" onClick={startResearch}>Read filings</Button>
                </div>
              )}
            </Sheet>
          )}

          <div className="mt-4 px-4">
            <Segmented<Tab> label="Company sections" value={tab} onChange={setTab}
              options={[{ value: "promises", label: "Promises" }, { value: "numbers", label: "Numbers" }, { value: "timeline", label: "Timeline" },
                        { value: "story", label: "Story" }, ...(c.prep_due || tab === "prep" ? [{ value: "prep" as Tab, label: "Prep" }] : [])]} />
          </div>
          {tab === "promises" && (ready ? <Promises symbol={symbol} /> : <Empty>The promise ledger appears once FINN has read the last four concalls.</Empty>)}
          {tab === "numbers" && <Numbers symbol={symbol} />}
          {tab === "timeline" && <Timeline symbol={symbol} />}
          {tab === "story" && <Story symbol={symbol} company={c} />}
          {tab === "prep" && <Prep symbol={symbol} />}

          <div className="mt-6 grid grid-cols-2 gap-3 px-4">
            <Button onClick={() => openAsk({ symbol, label: c.name })}>Ask about {c.name.split(" ")[0]}</Button>
            <Button kind="tertiary" onClick={() => setDecide(true)}>Record a decision</Button>
          </div>
          {!c.prep_due && tab !== "prep" && <div className="px-4"><Button kind="tertiary" className="-ml-4" onClick={() => setTab("prep")}>Concall prep questions</Button></div>}
          <DecideSheet open={decide} onClose={() => setDecide(false)} symbol={symbol} />
        </>
      )}
    </main>
  );
}

export default function CompanyPage() {
  return <Suspense fallback={<Skeleton lines={8} />}><CompanyInner /></Suspense>;
}
