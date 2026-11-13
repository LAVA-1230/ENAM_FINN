import { api, send } from "./api";

export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function isIosNotInstalled(): boolean {
  if (typeof window === "undefined") return false;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = (navigator as any).standalone || window.matchMedia("(display-mode: standalone)").matches;
  return ios && !standalone;
}

function urlB64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** Ask permission, subscribe and register with the backend. Returns a sentence describing the outcome. */
export async function enablePush(): Promise<string> {
  if (!pushSupported()) return "This browser can't receive push. Urgent items still go to your inbox.";
  const { public_key } = await api<{ public_key: string | null }>("/push/key");
  if (!public_key) return "Push isn't set up on the server yet. Urgent items go to your inbox.";
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return "Notifications are blocked. Urgent items still go to your inbox.";
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8Array(public_key) });
  const json = sub.toJSON();
  await send("/push/subscribe", "POST", { endpoint: json.endpoint, keys: json.keys });
  return "Push is on. Only urgent items will notify you.";
}
