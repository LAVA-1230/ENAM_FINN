"use client";
import { ReactNode, useEffect } from "react";
import { IconClose } from "./icons";

/** Urgency marks replace P0-P3 chips: words, with hierarchy by weight (design system 6.1). */
export function Urgency({ tier }: { tier: string }) {
  if (tier === "P0") return <span className="inline-block rounded-tag bg-down px-1.5 text-small font-semibold text-white">Urgent</span>;
  if (tier === "P1") return <span className="inline-block rounded-tag border border-ink px-1.5 text-small font-semibold">Today</span>;
  return null;
}

export function SectionLabel({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 mt-6 flex items-baseline justify-between px-4">
      <h2 className="text-sec font-semibold text-ink-2">{children}</h2>
      {right}
    </div>
  );
}

export function Sheet({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`border-y border-rule bg-sheet ${className}`}>{children}</div>;
}

/** Verbatim words from a source document: serif italic on the highlighter. Nothing else uses it. */
export function Quote({ children, draw = false }: { children: ReactNode; draw?: boolean }) {
  return <q className={`mark text-body ${draw ? "mark-draw" : ""}`} style={{ quotes: "'“' '”'" }}>{children}</q>;
}

export function Num({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`num ${className}`}>{children}</span>;
}

const DID: Record<string, string> = { hold: "Held", add: "Added", trim: "Trimmed", exit: "Exited", note: "Noted" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function shortDate(iso: string) {
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]}`;
}

/** The investor's own words, written in the margin like a pencil note: a thin rule, the action as a stamp, the
 *  reason in plain italic sans (never the serif or highlighter, which belong to source documents). */
export function MarginNote({ action, date, note, lead }: { action: string; date: string; note: string | null; lead?: string }) {
  return (
    <div className="mt-2 border-l-2 border-ink-3 pl-2.5">
      <p className="text-sec text-ink-2">
        {lead && <span>{lead} </span>}
        <span className="mr-1.5 inline-block rounded-tag border border-ink-3 px-1 text-small font-semibold text-ink-2">{DID[action] || action}</span>
        <Num className="text-small text-ink-3">{shortDate(date)}</Num>
      </p>
      {note && <p className="mt-0.5 text-sec italic text-ink-2">{note}</p>}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-3 px-4 py-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-4" style={{ width: `${90 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function ErrorLine({ error, cached }: { error: unknown; cached?: boolean }) {
  const msg = error instanceof Error ? error.message : "Couldn't reach FINN.";
  return (
    <p className="px-4 py-3 text-sec text-down" role="alert">
      {cached ? `Couldn't refresh. Showing the last data loaded. (${msg})` : msg}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-6 text-body text-ink-2">{children}</p>;
}

/** Segmented control (window picker, thesis, filters) instead of rows of pills. */
export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string }[]; value: T | null; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex overflow-x-auto rounded-ctl border border-rule bg-sheet p-0.5 no-scrollbar">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={`min-h-[40px] flex-1 whitespace-nowrap rounded-[8px] px-3 text-sec font-medium ${
            value === o.value ? "bg-ink text-sheet" : "text-ink-2"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Button({ children, onClick, kind = "secondary", className = "", disabled, type = "button" }: {
  children: ReactNode; onClick?: () => void; kind?: "primary" | "secondary" | "tertiary"; className?: string;
  disabled?: boolean; type?: "button" | "submit";
}) {
  const k = kind === "primary" ? "bg-ink text-sheet" : kind === "secondary" ? "border border-ink text-ink" : "text-link";
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`min-h-[48px] rounded-ctl px-4 text-body font-semibold disabled:opacity-50 ${k} ${className}`}>
      {children}
    </button>
  );
}

/** Bottom sheet: 20px top radius, drag handle, the one floating shadow, max 80% height. */
export function BottomSheet({ open, onClose, children, label }: { open: boolean; onClose: () => void; children: ReactNode; label: string }) {
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", esc); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" role="dialog" aria-modal="true" aria-label={label}>
      <button className="absolute inset-0 fade-in" style={{ background: "rgba(18, 23, 31, 0.35)" }} aria-label="Close" onClick={onClose} />
      <div className="sheet-up relative flex max-h-[80vh] w-full max-w-app flex-col rounded-t-sheet bg-sheet"
           style={{ boxShadow: "var(--float)" }}>
        <div className="flex items-center justify-between px-4 pt-2">
          <span className="mx-auto mt-1 block h-1 w-10 rounded-full bg-rule" aria-hidden />
        </div>
        <button onClick={onClose} aria-label="Close" className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center text-ink-2">
          <IconClose size={20} />
        </button>
        {children}
      </div>
    </div>
  );
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 border-t border-rule px-4 py-2.5 first:border-t-0">
      <span className="w-28 shrink-0 text-sec text-ink-3">{label}</span>
      <span className="min-w-0 flex-1 text-body">{children}</span>
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="flex min-h-[52px] cursor-pointer items-center justify-between gap-3 border-t border-rule px-4 py-2 first:border-t-0">
      <span>
        <span className="block text-body">{label}</span>
        {hint && <span className="block text-sec text-ink-3">{hint}</span>}
      </span>
      <input type="checkbox" className="h-5 w-5 accent-[var(--ink)]" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}
