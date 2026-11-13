"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { canListen, speakParts } from "@/lib/voice";
import { IconPause, IconPlay } from "./icons";

type Script = { text: string; parts: { id: number | null; text: string }[]; seconds: number };

/** Audio brief: a templated script read by the phone's own voice. Hidden where speechSynthesis is missing. */
export function Listen({ window: w, onItem }: { window: string; onItem: (id: number | null) => void }) {
  const [ok, setOk] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [seconds, setSeconds] = useState<number | null>(null);
  const stop = useRef<(() => void) | null>(null);

  useEffect(() => setOk(canListen()), []);
  useEffect(() => () => stop.current?.(), []);
  if (!ok) return null;

  async function toggle() {
    if (playing) {
      stop.current?.();
      setPlaying(false);
      onItem(null);
      return;
    }
    const s = await api<Script>(`/brief/audio-script?window=${w}`);
    setSeconds(s.seconds);
    setPlaying(true);
    stop.current = speakParts(s.parts.map((p) => p.text), (i) => {
      setProgress((i + 1) / s.parts.length);
      onItem(s.parts[i].id);
    }, () => { setPlaying(false); setProgress(0); onItem(null); });
  }

  return (
    <div className="flex items-center gap-3">
      <button onClick={toggle} aria-pressed={playing}
        className="flex min-h-[44px] items-center gap-2 rounded-ctl border border-on-head-2 px-3 text-sec font-semibold text-on-head">
        {playing ? <IconPause size={18} /> : <IconPlay size={18} />}
        {playing ? "Pause" : `Listen${seconds ? `, ${Math.max(1, Math.round(seconds / 60))} min` : ""}`}
      </button>
      {playing && (
        <div className="h-1 w-20 overflow-hidden rounded-full" style={{ background: "rgba(255,255,255,0.2)" }} aria-hidden>
          <div className="h-full bg-on-head transition-[width]" style={{ width: `${progress * 100}%` }} />
        </div>
      )}
    </div>
  );
}
