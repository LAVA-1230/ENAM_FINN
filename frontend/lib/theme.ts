// Light/dark choice: "system" follows the phone; "light"/"dark" pin it. The page colours come from globals.css
// via [data-theme]; the browser chrome (status bar, address bar, pull-to-refresh area) comes from theme-color
// metas, which must follow the same choice or the phone shows the other theme around the app.
// Those metas are created by script, never by React: React "repairs" a meta whose content changed after
// server render by inserting a second one, which put the phone's own theme back in the status bar.
export const THEME_COLOR = { light: "#E6EBE7", dark: "#12171F" } as const; // = --paper in globals.css

export type ThemeChoice = "system" | "light" | "dark";

// One function, used inline before first paint and by the picker. `t` is the saved choice.
const SET_THEME = `function(t){var d=document,h=d.documentElement;if(t==='light'||t==='dark')h.setAttribute('data-theme',t);else h.removeAttribute('data-theme');d.querySelectorAll('meta[name="theme-color"]').forEach(function(m){m.remove()});var add=function(c,q){var m=d.createElement('meta');m.name='theme-color';m.content=c;if(q)m.media=q;d.head.appendChild(m)};if(t==='light'||t==='dark')add(t==='dark'?'${THEME_COLOR.dark}':'${THEME_COLOR.light}');else{add('${THEME_COLOR.light}','(prefers-color-scheme: light)');add('${THEME_COLOR.dark}','(prefers-color-scheme: dark)')}}`;

/** Inline in <head>: applies the saved choice before first paint. */
export const THEME_SCRIPT = `try{window.__finnSetTheme=${SET_THEME};var s=null;try{s=localStorage.getItem('finn-theme')}catch(e){}window.__finnSetTheme(s)}catch(e){}`;

export function applyTheme(choice: ThemeChoice) {
  try { localStorage.setItem("finn-theme", choice); } catch {}
  const set = (window as unknown as { __finnSetTheme?: (t: string) => void }).__finnSetTheme;
  if (set) set(choice);
  else if (choice === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", choice);
}
