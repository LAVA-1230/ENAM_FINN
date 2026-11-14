"use client";
import { useEffect, useRef, useState } from "react";
import { api, send } from "@/lib/api";
import type { AskAnswer, Citation } from "@/lib/types";
import { canDictate, canListen, dictate, speakParts } from "@/lib/voice";
import type { AskContext } from "./providers";
import { IconMic, IconPause, IconPlay, IconSend, IconSpeaker } from "./icons";
import { BottomSheet } from "./ui";

type Turn = { q: string; a?: AskAnswer; error?: string };

/** Renders "text [1][2]" with the markers as tappable citation buttons. */
export function CitedText({ text, citations, onCite }: { text: string; citations: Citation[]; onCite: (c: Citation) => void }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (!m) return <span key={i}>{p}</span>;
        const c = citations.find((x) => x.n === Number(m[1]));
        if (!c) return null;
        return (
          <button key={i} onClick={() => onCite(c)} aria-label={`Source ${c.n}: ${c.label}`}
            className="num mx-0.5 inline-flex min-h-[28px] min-w-[28px] items-center justify-center rounded-tag align-baseline text-sec font-semibold text-link underline underline-offset-2">
            {c.n}
          </button>
        );
      })}
    </>
  );
}

export function AskSheet({ ctx, onClose, onCite }: { ctx: AskContext | null; onClose: () => void; onCite: (c: Citation) => void }) {
  const [context, setContext] = useState<AskContext | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [saved, setSaved] = useState<number | null>(null);
  const [speech, setSpeech] = useState<{ turn: number; playing: boolean } | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const stopSpeech = useRef<(() => void) | null>(null);
  const speechPos = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ctx) return;
    setContext(ctx.symbol || ctx.eventId ? ctx : null);
    setTurns([]);
    setText(ctx.question || "");
    const qs = new URLSearchParams();
    if (ctx.symbol) qs.set("symbol", ctx.symbol);
    if (ctx.eventId) qs.set("event_id", String(ctx.eventId));
    api<{ suggested: string[] }>(`/ask/suggested?${qs}`).then((r) => setSuggested(r.suggested)).catch(() => setSuggested([]));
  }, [ctx]);

  // Closing the sheet, switching context or leaving the page silences any answer being read.
  useEffect(() => {
    stopSpeech.current?.();
    stopSpeech.current = null;
    setSpeech(null);
  }, [ctx]);
  useEffect(() => () => stopSpeech.current?.(), []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);

  async function ask(q: string) {
    q = q.trim();
    if (!q || busy) return;
    setText("");
    setBusy(true);
    setTurns((t) => [...t, { q }]);
    try {
      const a = await send<AskAnswer>("/ask", "POST", { question: q, symbol: context?.symbol || null, event_id: context?.eventId || null });
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: (e as Error).message } : x)));
    } finally {
      setBusy(false);
    }
  }

  function mic() {
    if (listening) { stopRef.current?.(); return; }
    setListening(true);
    stopRef.current = dictate((t) => setText(t), () => setListening(false));
  }

  /** Read aloud / Pause / Resume for one answer. Pause remembers the sentence, so Resume carries on from there. */
  function readAloud(i: number, answer: string) {
    stopSpeech.current?.();
    stopSpeech.current = null;
    if (speech?.turn === i && speech.playing) {
      setSpeech({ turn: i, playing: false });
      return;
    }
    const parts = answer.replace(/\[\d+\]/g, "").replace(/([.!?])\s+/g, "$1\n").split("\n").filter((p) => p.trim());
    if (!parts.length) return;
    const start = speech?.turn === i && speechPos.current < parts.length ? speechPos.current : 0;
    speechPos.current = start;
    stopSpeech.current = speakParts(parts.slice(start), (k) => { speechPos.current = start + k; },
      () => { stopSpeech.current = null; speechPos.current = 0; setSpeech(null); });
    setSpeech({ turn: i, playing: true });
  }

  async function saveNote(i: number, a: AskAnswer, q: string) {
    if (!context?.symbol && !context?.eventId) return;
    await send("/decisions", "POST", { symbol: context?.symbol || null, event_id: context?.eventId || null, action: "note",
      note: `Asked: ${q} Answer: ${a.answer.replace(/\[\d+\]/g, "").slice(0, 380)}` });
    setSaved(i);
  }

  const label = context?.label || (context?.symbol ? context.symbol : "Your portfolio");

  return (
    <BottomSheet open={!!ctx} onClose={onClose} label="Ask FINN">
      <div className="px-4 pb-2 pt-2">
        <h2 className="text-item font-semibold">Ask</h2>
        <div className="mt-1 flex items-center gap-2 pr-10 text-sec text-ink-2">
          <span>Context:</span>
          <span className="inline-flex min-h-[32px] items-center gap-1 rounded-tag border border-rule px-2">
            <span className="max-w-[220px] truncate">{label}</span>
            {context && (
              <button aria-label="Remove context" className="px-1 text-ink-3" onClick={() => setContext(null)}>×</button>
            )}
          </span>
        </div>
      </div>
      <div className="min-h-[120px] flex-1 overflow-y-auto px-4">
        {turns.length === 0 && (
          <div className="pb-3">
            <p className="text-sec text-ink-3">Answers come only from {context ? "this company's transcripts, annual report and filings" : "your stored portfolio data"}. Every sentence links to its source.</p>
            <ul className="mt-2">
              {suggested.map((s) => (
                <li key={s}>
                  <button onClick={() => ask(s)} className="row-press min-h-[44px] w-full border-t border-rule py-2 text-left text-body text-link">{s}</button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="mb-4">
            <p className="ml-auto w-fit max-w-[85%] rounded-ctl bg-ink px-3 py-2 text-body text-sheet">{t.q}</p>
            {!t.a && !t.error && <p className="pulse mt-3 text-sec text-ink-3">Reading the sources…</p>}
            {t.error && <p className="mt-3 text-sec text-down">{t.error}</p>}
            {t.a && (
              <div className="mt-3 rounded-head border border-rule bg-sheet p-3">
                <p className="text-body"><CitedText text={t.a.answer} citations={t.a.citations} onCite={onCite} /></p>
                {t.a.citations.length > 0 && (
                  <ol className="mt-3 space-y-1 border-t border-rule pt-2">
                    {t.a.citations.map((c) => (
                      <li key={c.n}>
                        <button onClick={() => onCite(c)} className="min-h-[32px] text-left text-sec text-link">
                          <span className="num">{c.n}.</span> {c.label}
                        </button>
                      </li>
                    ))}
                  </ol>
                )}
                {t.a.method === "extractive" && t.a.found && (
                  <p className="mt-2 text-small text-ink-3">Quoted from the best-matching passages (no language model configured).</p>
                )}
                <div className="mt-2 flex gap-4">
                  {canListen() && (
                    <button className="flex min-h-[40px] items-center gap-1 text-sec text-link" aria-pressed={speech?.turn === i && speech.playing}
                      onClick={() => readAloud(i, t.a!.answer)}>
                      {speech?.turn === i
                        ? (speech.playing ? <><IconPause size={18} /> Pause</> : <><IconPlay size={18} /> Resume</>)
                        : <><IconSpeaker size={18} /> Read aloud</>}
                    </button>
                  )}
                  <button className="min-h-[40px] text-sec text-link" onClick={() => navigator.clipboard?.writeText(t.a!.answer.replace(/\[\d+\]/g, ""))}>Copy</button>
                  {context && t.a.found && (
                    <button className="min-h-[40px] text-sec text-link" onClick={() => saveNote(i, t.a!, t.q)}>
                      {saved === i ? "Saved to notes" : "Save to notes"}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form className="flex items-center gap-2 border-t border-rule px-3 py-3" onSubmit={(e) => { e.preventDefault(); ask(text); }}
            style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}>
        <label htmlFor="ask-input" className="sr-only">Your question</label>
        <input id="ask-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? "Listening…" : "Ask about the filings"}
          className="min-h-[48px] min-w-0 flex-1 rounded-ctl border border-rule bg-paper px-3 text-body text-ink placeholder:text-ink-3" />
        {canDictate() && (
          <button type="button" onClick={mic} aria-pressed={listening} aria-label={listening ? "Stop listening" : "Speak your question"}
            className={`flex h-12 w-12 items-center justify-center rounded-ctl border ${listening ? "pulse border-down text-down" : "border-rule text-ink"}`}>
            <IconMic />
          </button>
        )}
        <button type="submit" disabled={busy || !text.trim()} aria-label="Send"
          className="flex h-12 w-12 items-center justify-center rounded-ctl bg-ink text-sheet disabled:opacity-40">
          <IconSend />
        </button>
      </form>
    </BottomSheet>
  );
}
