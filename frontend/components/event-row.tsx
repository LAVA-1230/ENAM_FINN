"use client";
import Link from "next/link";
import type { EventCard } from "@/lib/types";
import { MarginNote, Num, Quote, Urgency } from "./ui";

function impactTone(line: string | null) {
  if (!line) return "text-ink-2";
  return /[−-]₹/.test(line) ? "text-down" : /\+₹/.test(line) ? "text-up" : "text-ink-2";
}

/** A ledger row: the margin column holds time and urgency; content aligns to one left edge (design 5.1). */
export function EventRow({ e, active, draw }: { e: EventCard; active?: boolean; draw?: boolean }) {
  return (
    <Link href={`/event/${e.id}`} className={`row-press flex border-t border-rule first:border-t-0 ${active ? "bg-paper" : ""}`}>
      <div className="w-14 shrink-0 py-3.5 pl-4">
        <Num className="block text-small text-ink-3">{e.time_ist}</Num>
        <span className="block text-small text-ink-3">{e.date_ist}</span>
      </div>
      <div className="min-w-0 flex-1 py-3.5 pr-4">
        <div className="flex flex-wrap items-center gap-2">
          <Urgency tier={e.tier} />
          <span className="text-sec font-medium text-ink-2">{e.company || "Your portfolio"}</span>
        </div>
        <h3 className="mt-1 text-item font-semibold">{e.title}</h3>
        {e.quote && <p className="mt-1.5 text-body"><Quote draw={draw}>{e.quote}</Quote></p>}
        {e.metric_line && <Num className="mt-1 block text-body font-medium">{e.metric_line}</Num>}
        {e.impact_line && <Num className={`block text-sec ${impactTone(e.impact_line)}`}>{e.impact_line}</Num>}
        {!e.verify_ok && <p className="mt-1 text-sec text-down">Couldn't verify the numbers automatically. Open the PDF.</p>}
        {e.reasons.length > 0 && (
          <p className="mt-1.5 text-sec text-ink-3">Why this is here: {e.reasons.slice(0, 3).join(", ")}</p>
        )}
        {e.last_decision && (
          <MarginNote lead="Last time:" action={e.last_decision.action} date={e.last_decision.date} note={e.last_decision.note} />
        )}
      </div>
    </Link>
  );
}

/** One-line FYI row. */
export function FyiRow({ e }: { e: EventCard }) {
  return (
    <Link href={`/event/${e.id}`} className="row-press flex border-t border-rule first:border-t-0">
      <div className="w-14 shrink-0 py-3 pl-4"><Num className="text-small text-ink-3">{e.date_ist}</Num></div>
      <div className="min-w-0 flex-1 py-3 pr-4 text-body">
        <span className="font-medium">{e.company || "Portfolio"}:</span> {e.summary && e.kind === "filing" ? e.summary : e.title}
        {e.metric_line && <Num className="block text-sec text-ink-2">{e.metric_line}</Num>}
      </div>
    </Link>
  );
}
