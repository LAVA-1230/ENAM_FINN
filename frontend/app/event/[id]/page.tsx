"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { DecideSheet } from "@/components/decide-sheet";
import { IconBack } from "@/components/icons";
import { useSheets } from "@/components/providers";
import { TopBar } from "@/components/shell";
import { Button, ErrorLine, Num, Quote, Row, Segmented, Skeleton, Urgency } from "@/components/ui";
import { api, send } from "@/lib/api";
import { crore, pts, rupees, signedPct, tone } from "@/lib/fmt";
import type { EventDetail, Move } from "@/lib/types";

function Section({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border-t border-rule py-4">
      <div className="mb-2 flex items-baseline justify-between px-4">
        <h2 className="text-sec font-semibold text-ink-2">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

function pctCell(v: number | null | undefined, isPts?: boolean) {
  return <Num className={tone(v)}>{isPts ? pts(v) : signedPct(v)}</Num>;
}

function ResultsBlock({ en }: { en: Record<string, any> }) {
  if (!en.table) return null;
  return (
    <Section title={`${en.period} results`} right={<span className="text-small text-ink-3">{en.basis ? `${en.basis}, ` : ""}{en.unit}</span>}>
      <div className="overflow-x-auto px-4">
        <table className="w-full text-body">
          <thead>
            <tr className="text-sec text-ink-3">
              <th className="py-1 text-left font-normal">Metric</th>
              <th className="py-1 text-right font-normal">This quarter</th>
              <th className="py-1 text-right font-normal">QoQ</th>
              <th className="py-1 text-right font-normal">YoY</th>
            </tr>
          </thead>
          <tbody>
            {en.table.map((r: any) => (
              <tr key={r.metric} className="border-t border-rule">
                <td className="py-2 pr-2">{r.metric}</td>
                <td className="py-2 text-right"><Num>{r.is_pct ? `${r.value?.toFixed(1)}%` : crore(r.value)}</Num></td>
                <td className="py-2 text-right">{pctCell(r.qoq, r.is_pct)}</td>
                <td className="py-2 text-right">{pctCell(r.yoy, r.is_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 px-4 text-small text-ink-3">{en.bank_format ? "Lender: EBITDA is not meaningful, so FINN shows income, operating profit and provisions." : en.ebitda_definition}</p>
      <p className={`mt-1 px-4 text-sec font-medium ${en.method === "screener" ? "text-ink-2" : "text-up"}`}>
        {en.method === "screener" ? "From screener.in's table; not checked against this PDF" : `Verified against the filing${en.page ? `, page ${en.page}` : ""}`}
      </p>
      {en.guidance && (
        <div className="mt-3 px-4">
          <p className="text-sec font-semibold text-ink-2">Against what management promised</p>
          <p className="mt-1 text-body"><Quote>{en.guidance.quote}</Quote></p>
          <p className="text-small text-ink-3">{en.guidance.made_in} call{en.guidance.page ? `, page ${en.guidance.page}` : ""}</p>
        </div>
      )}
    </Section>
  );
}

function initials(name: string) {
  return name.split(/\s+/).filter((w) => /^[A-Z]/.test(w)).slice(0, 2).map((w) => w[0]).join("");
}

function KmpBlock({ en }: { en: Record<string, any> }) {
  const bio = en.bio;
  return (
    <>
      {bio && (
        <Section title={bio.name === en.person ? "Who is coming in" : "Background"}>
          <div className="flex gap-3 px-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-rule text-sec font-semibold" aria-hidden>{initials(bio.name || "?")}</span>
            <div className="min-w-0">
              <p className="text-body font-semibold">{bio.name}</p>
              {bio.role && <p className="text-sec text-ink-2">{bio.role}</p>}
              <ul className="mt-1 space-y-1">
                {bio.lines?.map((l: any, i: number) => (
                  <li key={i} className="text-body">{l.verbatim ? <Quote>{l.text}</Quote> : l.text}</li>
                ))}
              </ul>
              {bio.note && <p className="text-sec text-ink-3">{bio.note}</p>}
              {bio.sources?.length > 0 && (
                <p className="mt-1 text-small text-ink-3">Sources: {bio.sources.map((s: any, i: number) => (
                  <a key={i} href={s.url} target="_blank" rel="noreferrer" className="text-link underline">{s.label || s.id}{i < bio.sources.length - 1 ? ", " : ""}</a>
                ))}</p>
              )}
            </div>
          </div>
        </Section>
      )}
      {en.cluster?.items?.length > 0 && (
        <Section title="Earlier key exits in the last 12 months">
          <ol className="px-4">
            {en.cluster.items.map((it: any) => (
              <li key={it.id} className="flex gap-3 border-t border-rule py-2 first:border-t-0">
                <Num className="w-20 shrink-0 text-sec text-ink-3">{it.date}</Num>
                <Link href={`/event/${it.id}`} className="text-body text-link">{it.title}</Link>
              </li>
            ))}
          </ol>
        </Section>
      )}
    </>
  );
}

function MoveBlock({ m, related, noFiling }: { m: Move; related?: EventDetail["related_filing"]; noFiling: boolean }) {
  return (
    <Section title={`Move on ${m.date}`}>
      <div className="px-4">
        <Row label="Stock"><Num className={tone(m.ret)}>{signedPct(m.ret)}</Num></Row>
        <Row label={m.index}><Num className={tone(m.index_ret)}>{signedPct(m.index_ret)}</Num></Row>
        {m.index !== "Nifty 50" && <Row label="Nifty 50"><Num className={tone(m.nifty_ret)}>{signedPct(m.nifty_ret)}</Num></Row>}
        <Row label="Stock-specific"><Num className={`font-semibold ${tone(m.specific)}`}>{pts(m.specific)}</Num></Row>
        {m.vol_ratio && <Row label="Volume"><Num>{m.vol_ratio.toFixed(1)}x the 20-day average</Num></Row>}
        <Row label="Related filing">
          {related ? <a href={related.url || "#"} target="_blank" rel="noreferrer" className="text-link">{related.subject}</a>
            : noFiling ? "No filing found in the 48 hours before" : "n/a"}
        </Row>
      </div>
      <p className="mt-2 px-4 text-small text-ink-3">Volume is an observation, not a prediction. EOD close, never real-time.</p>
    </Section>
  );
}

function OtherBlock({ en }: { en: Record<string, any> }) {
  return (
    <>
      {en.rating && (
        <Section title="Credit rating">
          <div className="px-4">
            <p className="num text-item font-semibold">{en.rating.rating_old || "?"} to {en.rating.rating_new || "?"}</p>
            <p className="text-sec text-ink-2">{[en.rating.agency, en.rating.instrument, en.rating.outlook && `outlook ${en.rating.outlook}`].filter(Boolean).join(", ")}</p>
          </div>
        </Section>
      )}
      {en.pledge && (
        <Section title="Promoter pledge">
          <div className="px-4">
            {["before", "after"].map((k) => (
              <div key={k} className="mt-1 flex items-center gap-3">
                <span className="w-14 text-sec text-ink-3">{k === "before" ? "Before" : "After"}</span>
                <div className="h-2 flex-1 rounded-tag bg-rule"><div className="h-full rounded-tag bg-ink" style={{ width: `${Math.min(100, en.pledge[k] || 0)}%` }} /></div>
                <Num className="w-14 text-right">{en.pledge[k] != null ? `${en.pledge[k].toFixed(1)}%` : "n/a"}</Num>
              </div>
            ))}
          </div>
        </Section>
      )}
      {(en.amount_crore || en.size_vs_company) && (
        <Section title="Size versus the company">
          <p className="px-4 text-item font-semibold">
            <Num>{en.amount_crore ? crore(en.amount_crore) : ""}</Num>
            {en.size_vs_company && <span> ≈ <Num>{en.size_vs_company.pct.toFixed(1)}%</Num> of {en.size_vs_company.base}</span>}
          </p>
        </Section>
      )}
      {en.members && (
        <Section title="Holdings that moved together">
          <ul className="px-4">
            {en.members.map((m: any) => (
              <li key={m.symbol} className="flex justify-between border-t border-rule py-2 first:border-t-0">
                <Link href={`/company/${encodeURIComponent(m.symbol)}`} className="text-link">{m.name}</Link>
                <Num className={tone(m.ret)}>{signedPct(m.ret)}</Num>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

export default function EventPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { openAsk } = useSheets();
  const [decide, setDecide] = useState(false);
  const { data: e, error, isLoading } = useQuery({ queryKey: ["event", id], queryFn: () => api<EventDetail>(`/events/${id}`) });

  async function tag(v: string) {
    await send(`/events/${id}`, "PATCH", { thesis_tag: v, status: "seen" });
    qc.invalidateQueries({ queryKey: ["event", id] });
    qc.invalidateQueries({ queryKey: ["portfolio"] });
  }
  async function dismiss() {
    await send(`/events/${id}`, "PATCH", { status: "dismissed" });
    qc.invalidateQueries({ queryKey: ["brief"] });
    router.back();
  }
  function share() {
    if (!e) return;
    const text = [`${e.company}: ${e.title}`, e.metric_line, e.impact_line, e.source?.url].filter(Boolean).join("\n");
    if (navigator.share) navigator.share({ title: e.title, text }).catch(() => {});
    else navigator.clipboard?.writeText(text);
  }

  const back = (
    <button onClick={() => (history.length > 1 ? router.back() : router.push("/"))} className="-ml-2 flex min-h-[44px] items-center gap-1 pr-2 text-body text-link">
      <IconBack size={20} /> Brief
    </button>
  );
  const en = e?.enrichment || {};
  const ex = e?.exposure;

  return (
    <main className="bg-sheet pb-6">
      <TopBar back={back} ask={e ? { symbol: e.symbol, eventId: e.id, label: `${e.company || "Portfolio"}, ${e.title}` } : undefined} />
      {isLoading && <Skeleton lines={10} />}
      {error && <ErrorLine error={error} />}
      {e && (
        <>
          <div className="px-4 pb-4 pt-2">
            <div className="flex flex-wrap items-center gap-2">
              <Urgency tier={e.tier} />
              {e.symbol ? <Link href={`/company/${encodeURIComponent(e.symbol)}`} className="text-sec font-medium text-link">{e.company}</Link>
                : <span className="text-sec font-medium text-ink-2">Your portfolio</span>}
              <span className="ml-auto text-small text-ink-3">{e.date_ist}, <Num>{e.time_ist}</Num></span>
            </div>
            <h1 className="mt-2 text-title font-semibold">{e.title}</h1>
            {e.metric_line && <Num className="mt-1 block text-body font-medium">{e.metric_line}</Num>}
            {e.reasons.length > 0 && <p className="mt-2 text-sec text-ink-3">Why this is here: {e.reasons.join(", ")}</p>}
          </div>

          {ex?.held && (
            <div className="grid grid-cols-3 border-t border-rule">
              <div className="px-4 py-3"><p className="text-small text-ink-3">Weight</p><Num className="text-item font-semibold">{ex.weight?.toFixed(1)}%</Num></div>
              <div className="border-l border-rule px-3 py-3"><p className="text-small text-ink-3">{ex.move ? `Move ${ex.move.date.slice(5).split("-").reverse().join("/")}` : "Move"}</p><Num className={`text-item font-semibold ${tone(ex.move?.ret)}`}>{signedPct(ex.move?.ret)}</Num></div>
              <div className="border-l border-rule px-3 py-3"><p className="text-small text-ink-3">Your P&amp;L that day</p><Num className={`text-item font-semibold ${tone(ex.day_rs)}`}>{rupees(ex.day_rs, true)}</Num></div>
            </div>
          )}

          {e.category === "results" && <ResultsBlock en={en} />}
          {!e.verify_ok && (
            <Section title="Numbers">
              <p className="px-4 text-body">Results filed. FINN couldn't verify the numbers automatically, so it shows none. Open the PDF to read them.</p>
            </Section>
          )}
          {(e.category === "kmp_change" || e.category === "auditor_change") && <KmpBlock en={en} />}
          {en.move && <MoveBlock m={en.move} related={e.related_filing} noFiling={!en.related_filing_id} />}
          <OtherBlock en={en} />

          {(e.facts.length > 0 || e.source) && (
            <Section title="From the filing" right={e.source?.url && (
              <a href={e.source.url + (e.source.page ? `#page=${e.source.page}` : "")} target="_blank" rel="noreferrer" className="flex min-h-[44px] items-center text-sec font-medium text-link">Open PDF</a>)}>
              {e.facts.filter((f) => f.quote).map((f) => (
                <p key={f.k} className="px-4 pb-2 text-body"><Quote>{f.v}</Quote></p>
              ))}
              {e.facts.filter((f) => !f.quote).map((f) => <Row key={f.k} label={f.k}>{f.v}</Row>)}
              {e.summary && <p className="px-4 pt-2 text-body text-ink-2">{e.summary}</p>}
              {e.source && <p className="px-4 pt-2 text-small text-ink-3">Filed on {e.source.exchange}: {e.source.subject.slice(0, 140)}</p>}
            </Section>
          )}

          {e.context.length > 0 && (
            <Section title="What FINN noticed">
              <ul className="space-y-1 px-4">{e.context.map((c, i) => <li key={i} className="text-body">{c}</li>)}</ul>
              <p className="mt-2 px-4 text-small text-ink-3">Computed from stored filings and prices.</p>
            </Section>
          )}

          {e.last_decision && (
            <Section title="Last time">
              <p className="px-4 text-body">On {e.last_decision.date} you chose <b>{e.last_decision.action}</b>{e.last_decision.note ? `: “${e.last_decision.note}”` : "."}</p>
            </Section>
          )}

          {e.symbol && ["P0", "P1"].includes(e.tier) && (
            <Section title="Does this change your thesis?">
              <div className="px-4">
                <Segmented label="Thesis" value={e.thesis_tag} onChange={tag}
                  options={[{ value: "strengthens", label: "Strengthens" }, { value: "neutral", label: "No change" }, { value: "weakens", label: "Weakens" }]} />
              </div>
            </Section>
          )}

          {e.decisions.length > 0 && (
            <Section title="Your decisions on this">
              <ul className="px-4">{e.decisions.map((d) => <li key={d.id} className="text-body"><b className="capitalize">{d.action}</b>{d.note ? `: ${d.note}` : ""} <span className="text-small text-ink-3">{d.date}</span></li>)}</ul>
            </Section>
          )}

          <div className="grid grid-cols-2 gap-3 border-t border-rule px-4 pt-4">
            {e.symbol ? <Link href={`/company/${encodeURIComponent(e.symbol)}`} className="flex min-h-[48px] items-center justify-center rounded-ctl bg-ink text-body font-semibold text-sheet">Open company</Link>
              : <span />}
            <Button onClick={() => openAsk({ symbol: e.symbol, eventId: e.id, label: `${e.company || "Portfolio"}, ${e.title}` })}>Ask about this</Button>
            {e.symbol && <Button kind="tertiary" onClick={() => setDecide(true)}>Decide</Button>}
            <Button kind="tertiary" onClick={share}>Share</Button>
            <Button kind="tertiary" onClick={dismiss}>Dismiss</Button>
          </div>
          <DecideSheet open={decide} onClose={() => setDecide(false)} symbol={e.symbol} eventId={e.id} />
        </>
      )}
    </main>
  );
}
