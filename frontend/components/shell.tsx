"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { api, onReplay, onSlow } from "@/lib/api";
import { IconAlerts, IconAsk, IconBell, IconBrief, IconPortfolio, IconResearch } from "./icons";
import { AskContext, useSheets } from "./providers";

const TABS = [
  { href: "/", label: "Brief", Icon: IconBrief },
  { href: "/portfolio", label: "Portfolio", Icon: IconPortfolio },
  { href: "/research", label: "Research", Icon: IconResearch },
  { href: "/alerts", label: "Alerts", Icon: IconAlerts },
];

export function BottomNav() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" || path.startsWith("/event") : path.startsWith(href) ||
    (href === "/research" && path.startsWith("/company")));
  return (
    <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-sheet"
         style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <ul className="mx-auto flex max-w-app">
        {TABS.map(({ href, label, Icon }) => (
          <li key={href} className="flex-1">
            <Link href={href} aria-current={active(href) ? "page" : undefined}
              className={`relative flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-small font-medium ${
                active(href) ? "text-ink" : "text-ink-3"}`}>
              {active(href) && <span className="absolute inset-x-6 top-0 h-0.5 bg-ink" aria-hidden />}
              <Icon size={22} />
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function TopBar({ title, sub, ask, back }: { title?: ReactNode; sub?: ReactNode; ask?: AskContext; back?: ReactNode }) {
  const { openAsk } = useSheets();
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: () => api<{ unread: number }>("/notifications"),
                              refetchInterval: 120_000 });
  return (
    <header className="px-4 pt-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">{back || (title ?? <span className="num text-[20px] font-semibold tracking-tight">FINN</span>)}</div>
        <div className="-mr-2 flex shrink-0">
          <Link href="/inbox" aria-label={`Inbox${data?.unread ? `, ${data.unread} unread` : ""}`}
                className="relative flex h-11 w-11 items-center justify-center text-ink">
            <IconBell />
            {!!data?.unread && (
              <span className="num absolute right-1 top-1 min-w-[18px] rounded-full bg-down px-1 text-center text-small font-semibold text-white">
                {data.unread > 9 ? "9+" : data.unread}
              </span>
            )}
          </Link>
          <button aria-label="Ask FINN" onClick={() => openAsk(ask)} className="flex h-11 w-11 items-center justify-center text-ink">
            <IconAsk />
          </button>
        </div>
      </div>
      {sub && <div className="text-sec text-ink-2">{sub}</div>}
    </header>
  );
}

/** Replay banner, "waking up" note for sleeping free hosts, and an offline line. */
export function Banners() {
  const [replay, setReplay] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const [offline, setOffline] = useState(false);
  useEffect(() => onReplay(setReplay), []);
  useEffect(() => onSlow(setSlow), []);
  useEffect(() => {
    const set = () => setOffline(!navigator.onLine);
    set();
    window.addEventListener("online", set);
    window.addEventListener("offline", set);
    return () => { window.removeEventListener("online", set); window.removeEventListener("offline", set); };
  }, []);
  return (
    <div aria-live="polite">
      {replay && (
        <div className="bg-ink px-4 py-2 text-sec font-medium text-sheet">
          {replay}. <Link href="/alerts#data" className="underline">Switch to live</Link>
        </div>
      )}
      {offline && <div className="bg-down px-4 py-2 text-sec text-white">You're offline. Showing the last data loaded.</div>}
      {slow && !offline && <div className="border-b border-rule bg-sheet px-4 py-2 text-sec text-ink-2">Waking up FINN. The free server sleeps when idle; this takes up to a minute.</div>}
    </div>
  );
}
