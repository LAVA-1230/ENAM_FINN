"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect } from "react";
import { TopBar } from "@/components/shell";
import { Empty, ErrorLine, Num, Sheet, Skeleton } from "@/components/ui";
import { api, send } from "@/lib/api";
import { day } from "@/lib/fmt";

type Inbox = { unread: number; items: { id: number; title: string; body: string | null; url: string | null; channel: string; sent_at: string; read: boolean }[] };

export default function InboxPage() {
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({ queryKey: ["inbox"], queryFn: () => api<Inbox>("/notifications") });
  useEffect(() => {
    if (data?.unread) send("/notifications/read", "POST").then(() => qc.invalidateQueries({ queryKey: ["notifications"] })).catch(() => {});
  }, [data?.unread, qc]);
  return (
    <main>
      <TopBar title={<h1 className="text-title font-semibold">Inbox</h1>} sub="Every urgent alert lands here, with or without push permission." />
      {isLoading && <Skeleton lines={6} />}
      {error && <ErrorLine error={error} />}
      {data && (data.items.length ? (
        <Sheet className="mt-3">
          {data.items.map((n) => (
            <Link key={n.id} href={n.url || "/"} className="row-press flex gap-3 border-t border-rule px-4 py-3 first:border-t-0">
              <span className="w-14 shrink-0 text-small text-ink-3">
                <Num className="block">{new Date(n.sent_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}</Num>{day(n.sent_at)}
              </span>
              <span className="min-w-0 flex-1">
                <span className={`block text-body ${n.read ? "" : "font-semibold"}`}>{n.title}</span>
                {n.body && <span className="block text-sec text-ink-2">{n.body}</span>}
                <span className="block text-small text-ink-3">{n.channel === "webpush" ? "Sent as push" : "Inbox only"}</span>
              </span>
            </Link>
          ))}
        </Sheet>
      ) : <Empty>No urgent alerts yet. That is the point: FINN interrupts only when your thesis might be broken.</Empty>)}
    </main>
  );
}
