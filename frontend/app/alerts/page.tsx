"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { TopBar } from "@/components/shell";
import { Button, ErrorLine, Num, SectionLabel, Segmented, Sheet, Skeleton, Toggle } from "@/components/ui";
import { api, send } from "@/lib/api";
import { enablePush, isIosNotInstalled } from "@/lib/push";
import { applyTheme, type ThemeChoice } from "@/lib/theme";
import type { Settings } from "@/lib/types";

type Health = { replay: boolean; snapshots: string[]; last: Record<string, { label: string | null }>; eod_date: string | null;
                llm: { enabled: boolean; provider: string | null }; push: boolean; websearch: boolean };

type Usage = { total_cost_usd: number; calls: number; cache_hit_rate: number; cost_per_day_per_20_companies_usd: number };
const usd = (x: number) => (x > 0 && x < 0.01 ? "under $0.01" : `$${x.toFixed(2)}`);

function Stepper({ label, hint, value, step, min, max, unit, onChange }: {
  label: string; hint: string; value: number; step: number; min: number; max: number; unit: string; onChange: (v: number) => void;
}) {
  const set = (v: number) => onChange(Math.min(max, Math.max(min, Math.round(v * 100) / 100)));
  return (
    <div className="flex items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0">
      <div className="min-w-0"><p className="text-body">{label}</p><p className="text-sec text-ink-3">{hint}</p></div>
      <div className="flex shrink-0 items-center">
        <button aria-label={`Lower ${label}`} onClick={() => set(value - step)} className="h-11 w-11 rounded-ctl border border-rule text-item">{"−"}</button>
        <Num className="w-16 text-center text-item font-semibold">{value}{unit}</Num>
        <button aria-label={`Raise ${label}`} onClick={() => set(value + step)} className="h-11 w-11 rounded-ctl border border-rule text-item">+</button>
      </div>
    </div>
  );
}

const TIERS = [{ value: "P0", label: "Urgent" }, { value: "P1", label: "Today" }, { value: "P2", label: "FYI" }, { value: "P3", label: "Routine" }];

export default function AlertsPage() {
  const qc = useQueryClient();
  const { data: s, error, isLoading } = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("/settings") });
  const { data: h } = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });
  const { data: u } = useQuery({ queryKey: ["usage"], queryFn: () => api<Usage>("/admin/usage"), retry: false });
  const [t, setT] = useState<{ price_pct: number; volume_x: number; impact_pct: number } | null>(null);
  const [preview, setPreview] = useState<Settings["preview"] | null>(null);
  const [pushMsg, setPushMsg] = useState<string | null>(null);
  const [theme, setTheme] = useState<string>("system");

  useEffect(() => { if (s && !t) setT({ price_pct: s.price_pct, volume_x: s.volume_x, impact_pct: s.impact_pct }); }, [s, t]);
  useEffect(() => { try { setTheme(localStorage.getItem("finn-theme") || "system"); } catch {} }, []);
  useEffect(() => {
    if (!t || !s) return;
    if (t.price_pct === s.price_pct && t.volume_x === s.volume_x && t.impact_pct === s.impact_pct) { setPreview(null); return; }
    const id = setTimeout(() => api<Settings["preview"]>(`/settings/preview?price_pct=${t.price_pct}&volume_x=${t.volume_x}&impact_pct=${t.impact_pct}`)
      .then(setPreview).catch(() => {}), 300);
    return () => clearTimeout(id);
  }, [t, s]);

  async function put(body: Omit<Partial<Settings>, "tier_overrides"> & { tier_overrides?: Record<string, string | null> }) {
    const prev = qc.getQueryData<Settings>(["settings"]);
    // flip the control at once; the server's answer replaces it (or the old value comes back on error).
    // Tier changes wait for the server: it owns the category list they show in.
    const { tier_overrides: _tiers, ...flat } = body;
    if (prev) qc.setQueryData<Settings>(["settings"], { ...prev, ...flat,
      tripwire_defaults: { ...prev.tripwire_defaults, ...(flat.tripwire_defaults || {}) } });
    let next: Settings;
    try {
      next = await send<Settings>("/settings", "PUT", body);
    } catch (e) {
      if (prev) qc.setQueryData(["settings"], prev);
      throw e;
    }
    qc.setQueryData<Settings>(["settings"], (cur) => ({ ...next, preview: next.preview ?? cur?.preview ?? prev!.preview }));
    qc.invalidateQueries({ queryKey: ["brief"] });
    qc.invalidateQueries({ queryKey: ["health"] });
  }
  function chooseTheme(v: string) {
    setTheme(v);
    applyTheme(v as ThemeChoice);
  }

  const changed = s && t && (t.price_pct !== s.price_pct || t.volume_x !== s.volume_x || t.impact_pct !== s.impact_pct);
  const p = preview || s?.preview;

  return (
    <main>
      <TopBar title={<h1 className="text-title font-semibold">Alerts</h1>} sub="Only urgent items interrupt you. Everything else waits for the brief." />
      {isLoading && <Skeleton lines={10} />}
      {error && <ErrorLine error={error} />}
      {s && t && (
        <>
          <SectionLabel>What counts as unusual</SectionLabel>
          <Sheet>
            <Stepper label="Price move" hint="Stock-specific, after removing its sector index" value={t.price_pct} step={0.5} min={0.5} max={20} unit="%"
              onChange={(v) => setT({ ...t, price_pct: v })} />
            <Stepper label="Volume" hint="Times the 20-day average" value={t.volume_x} step={0.5} min={1} max={10} unit="x"
              onChange={(v) => setT({ ...t, volume_x: v })} />
            <Stepper label="Portfolio impact" hint="A move this big in your whole book becomes urgent" value={t.impact_pct} step={0.05} min={0.05} max={5} unit="%"
              onChange={(v) => setT({ ...t, impact_pct: v })} />
          </Sheet>
          {p && (
            <p className="mt-2 px-4 text-sec text-ink-2" aria-live="polite">
              With {changed ? "these" : "your"} settings, the last <Num>{p.sessions}</Num> sessions would have produced <Num className="font-semibold">{p.alerts}</Num> price and volume alerts
              (<Num>{p.price}</Num> price, <Num>{p.volume}</Num> volume).
            </p>
          )}
          {changed && <div className="px-4 pt-3"><Button kind="primary" className="w-full" onClick={() => put(t)}>Save thresholds</Button></div>}

          <SectionLabel>Priority by event type</SectionLabel>
          <Sheet>
            {s.categories.map((c) => (
              <div key={c.key} className="border-t border-rule px-4 py-2.5 first:border-t-0">
                <div className="flex items-baseline justify-between">
                  <span className="text-body">{c.label}</span>
                  {c.tier !== c.default && <button className="min-h-[32px] text-sec text-link" onClick={() => put({ tier_overrides: { [c.key]: null } })}>Reset</button>}
                </div>
                <div className="mt-1"><Segmented label={`Priority for ${c.label}`} value={c.tier} options={TIERS}
                  onChange={(v) => put({ tier_overrides: { [c.key]: v } })} /></div>
              </div>
            ))}
          </Sheet>

          <SectionLabel>Delivery</SectionLabel>
          <Sheet>
            <Toggle label="Notify only for urgent items" hint="Everything else waits for the brief" checked={s.push_p0_only} onChange={(v) => put({ push_p0_only: v })} />
            <Toggle label="Let urgent items through quiet hours" checked={s.p0_in_quiet} onChange={(v) => put({ p0_in_quiet: v })} />
            <div className="flex items-center justify-between gap-3 border-t border-rule px-4 py-3">
              <span className="text-body">Quiet hours</span>
              <span className="flex items-center gap-2">
                <input type="time" aria-label="Quiet hours start" value={s.quiet_start} onChange={(e) => put({ quiet_start: e.target.value })}
                  className="num min-h-[44px] rounded-ctl border border-rule bg-paper px-2 text-ink" />
                <span className="text-sec text-ink-3">to</span>
                <input type="time" aria-label="Quiet hours end" value={s.quiet_end} onChange={(e) => put({ quiet_end: e.target.value })}
                  className="num min-h-[44px] rounded-ctl border border-rule bg-paper px-2 text-ink" />
              </span>
            </div>
            <div className="border-t border-rule px-4 py-3">
              <p className="text-body">Brief times: <Num>{s.brief_times.join(" and ")}</Num></p>
              {isIosNotInstalled() && <p className="mt-1 text-sec text-ink-2">On iPhone, add FINN to your Home Screen first: push works only for installed web apps.</p>}
              <div className="mt-2 flex flex-wrap gap-3">
                <Button onClick={async () => setPushMsg(await enablePush().catch((e) => String(e.message)))}>Enable push</Button>
                <Button kind="tertiary" onClick={async () => { const r = await send<{ note: string | null }>("/push/test", "POST"); setPushMsg(r.note || "Test alert sent."); qc.invalidateQueries({ queryKey: ["notifications"] }); }}>Send test alert</Button>
              </div>
              {pushMsg && <p className="mt-2 text-sec text-ink-2" aria-live="polite">{pushMsg}</p>}
            </div>
          </Sheet>

          <SectionLabel>Tripwire defaults for every holding</SectionLabel>
          <Sheet>
            {Object.entries(s.tripwire_labels).map(([k, label]) => (
              <Toggle key={k} label={label} checked={s.tripwire_defaults[k]} onChange={(v) => put({ tripwire_defaults: { [k]: v } })} />
            ))}
          </Sheet>

          <SectionLabel>Display</SectionLabel>
          <div className="px-4">
            <Segmented label="Theme" value={theme} onChange={chooseTheme}
              options={[{ value: "system", label: "Match phone" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
          </div>

          <div id="data"><SectionLabel>Data</SectionLabel></div>
          <Sheet>
            <Toggle label="Replay mode" hint={h?.snapshots.includes("demo") ? "Serve a recorded window, for demos when live sources are thin" : "No demo snapshot recorded yet"}
              checked={s.replay} onChange={(v) => put({ replay: v })} />
            <div className="border-t border-rule px-4 py-3 text-sec text-ink-2">
              <p>Filings checked: {h?.last.ingest_filings?.label || "never"}</p>
              <p>Prices: {h?.eod_date ? `EOD ${h.eod_date}` : "none stored"}</p>
              <p>Language model: {h?.llm.enabled ? h.llm.provider : "not configured, using rules and templates"}</p>
              <p>Bio web search: {h?.websearch ? "on" : "off"}. Web push: {h?.push ? "configured" : "inbox only"}.</p>
              {u && u.calls > 0 && (
                <p>Language model spend: <Num>{usd(u.total_cost_usd)}</Num> in total, about <Num>{usd(u.cost_per_day_per_20_companies_usd)}</Num> a day for 20 companies.{" "}
                  <Num>{Math.round(u.cache_hit_rate * 100)}%</Num> of <Num>{u.calls}</Num> calls were answered from cache at no cost.</p>
              )}
              <p className="mt-1 text-small text-ink-3">Data refreshes on a schedule. FINN never claims real-time prices.</p>
            </div>
          </Sheet>
        </>
      )}
    </main>
  );
}
