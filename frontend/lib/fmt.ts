// Same rules as backend/app/fmt.py: true minus sign, Indian grouping, one abbreviation style.
export const MINUS = "−";

export function signedPct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  return (x >= 0 ? "+" : MINUS) + Math.abs(x).toFixed(digits) + "%";
}

export function pts(x: number | null | undefined): string {
  if (x === null || x === undefined) return "n/a";
  return (x >= 0 ? "+" : MINUS) + Math.abs(x).toFixed(1) + " pts";
}

export function indianGroup(n: number): string {
  const s = Math.round(Math.abs(n)).toString();
  if (s.length <= 3) return s;
  let head = s.slice(0, -3);
  const tail = s.slice(-3);
  const parts: string[] = [];
  while (head.length > 2) {
    parts.unshift(head.slice(-2));
    head = head.slice(0, -2);
  }
  if (head) parts.unshift(head);
  return parts.join(",") + "," + tail;
}

export function rupees(x: number | null | undefined, signed = false): string {
  if (x === null || x === undefined) return "n/a";
  const a = Math.abs(x);
  const body = a >= 1e7 ? `${(a / 1e7).toFixed(2)} cr` : a >= 1e5 ? `${(a / 1e5).toFixed(1)} lakh`
    : a >= 1e3 ? `${(a / 1e3).toFixed(1)}k` : a.toFixed(0);
  const sign = signed ? (x >= 0 ? "+" : MINUS) : x < 0 ? MINUS : "";
  return `${sign}₹${body}`;
}

export function crore(x: number | null | undefined): string {
  if (x === null || x === undefined) return "n/a";
  const sign = x < 0 ? MINUS : "";
  return Math.abs(x) >= 100 ? `${sign}₹${indianGroup(x)} cr` : `${sign}₹${Math.abs(x).toFixed(1)} cr`;
}

export function price(x: number | null | undefined): string {
  if (x === null || x === undefined) return "n/a";
  const [i, d] = Math.abs(x).toFixed(2).split(".");
  return `₹${indianGroup(Number(i))}.${d}`;
}

export const tone = (x: number | null | undefined) =>
  x === null || x === undefined ? "" : x >= 0 ? "text-up" : "text-down";

export function day(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function weekday(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

export const tierWord = (t: string) =>
  t === "P0" ? "Urgent" : t === "P1" ? "Today" : t === "P2" ? "For your information" : "Routine";
