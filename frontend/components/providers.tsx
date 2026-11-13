"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import type { Citation } from "@/lib/types";
import { AskSheet } from "./ask-sheet";
import { SourceSheet } from "./source-sheet";

export interface AskContext { symbol?: string | null; eventId?: number | null; label?: string | null; question?: string }

interface Sheets {
  openAsk: (ctx?: AskContext) => void;
  openSource: (c: Citation) => void;
}
const SheetCtx = createContext<Sheets>({ openAsk: () => {}, openSource: () => {} });
export const useSheets = () => useContext(SheetCtx);

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: true } },
  }));
  const [ask, setAsk] = useState<AskContext | null>(null);
  const [source, setSource] = useState<Citation | null>(null);
  const openAsk = useCallback((ctx?: AskContext) => setAsk(ctx || {}), []);
  const openSource = useCallback((c: Citation) => setSource(c), []);

  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  return (
    <QueryClientProvider client={client}>
      <SheetCtx.Provider value={{ openAsk, openSource }}>
        {children}
        <AskSheet ctx={ask} onClose={() => setAsk(null)} onCite={openSource} />
        <SourceSheet citation={source} onClose={() => setSource(null)} />
      </SheetCtx.Provider>
    </QueryClientProvider>
  );
}
