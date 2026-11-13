"use client";
import type { Citation } from "@/lib/types";
import { BottomSheet, Quote } from "./ui";

/** Tap any citation: the document, period and page, the cited excerpt, and the PDF opened at that page. */
export function SourceSheet({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const c = citation;
  const external = c?.url && /^https?:/.test(c.url);
  return (
    <BottomSheet open={!!c} onClose={onClose} label="Source">
      {c && (
        <div className="overflow-y-auto px-4 pb-6 pt-3">
          <p className="pr-10 text-sec text-ink-3">Source {c.n > 0 ? `[${c.n}]` : ""}</p>
          <h3 className="mt-1 pr-10 text-item font-semibold">{c.label}</h3>
          {c.excerpt && (
            <p className="mt-4 text-body"><Quote>{c.excerpt}</Quote></p>
          )}
          <p className="mt-3 text-small text-ink-3">The highlighted words are copied from the source, not written by FINN.</p>
          {c.url && (
            <a href={c.url} target={external ? "_blank" : undefined} rel="noreferrer"
               className="mt-5 flex min-h-[48px] items-center justify-center rounded-ctl bg-ink text-body font-semibold text-sheet">
              {external ? (c.page ? `Open PDF at page ${c.page}` : "Open the document") : "Open"}
            </a>
          )}
        </div>
      )}
    </BottomSheet>
  );
}
