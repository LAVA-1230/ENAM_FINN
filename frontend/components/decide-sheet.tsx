"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { send } from "@/lib/api";
import { canDictate, dictate } from "@/lib/voice";
import { IconMic } from "./icons";
import { BottomSheet, Button, Segmented } from "./ui";

const ACTIONS = [
  { value: "hold", label: "Hold" }, { value: "add", label: "Add" }, { value: "trim", label: "Trim" },
  { value: "exit", label: "Exit" }, { value: "note", label: "Note" },
] as const;
type Action = (typeof ACTIONS)[number]["value"];

/** Decision journal: an action plus a one-line reason, typed or dictated. */
export function DecideSheet({ open, onClose, symbol, eventId }: { open: boolean; onClose: () => void; symbol?: string | null; eventId?: number }) {
  const qc = useQueryClient();
  const [action, setAction] = useState<Action>("hold");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await send("/decisions", "POST", { symbol: symbol || null, event_id: eventId || null, action, note });
      await qc.invalidateQueries();
      setNote("");
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet open={open} onClose={onClose} label="Record a decision">
      <form className="px-4 pb-6 pt-3" onSubmit={(e) => { e.preventDefault(); save(); }}>
        <h2 className="text-item font-semibold">Your decision</h2>
        <p className="text-sec text-ink-3">The next item about this company will remind you of it.</p>
        <div className="mt-4"><Segmented<Action> label="Action" options={[...ACTIONS]} value={action} onChange={setAction} /></div>
        <label htmlFor="decision-note" className="mt-4 block text-sec text-ink-2">Reason, in one line</label>
        <div className="mt-1 flex gap-2">
          <input id="decision-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300}
            placeholder="e.g. watch for more exits" className="min-h-[48px] min-w-0 flex-1 rounded-ctl border border-rule bg-paper px-3 text-body text-ink placeholder:text-ink-3" />
          {canDictate() && (
            <button type="button" aria-label="Dictate the reason" aria-pressed={listening}
              onClick={() => { setListening(true); dictate((t) => setNote(t), () => setListening(false)); }}
              className={`flex h-12 w-12 items-center justify-center rounded-ctl border ${listening ? "pulse border-down text-down" : "border-rule"}`}>
              <IconMic />
            </button>
          )}
        </div>
        <Button kind="primary" type="submit" disabled={busy} className="mt-5 w-full">Save decision</Button>
      </form>
    </BottomSheet>
  );
}
