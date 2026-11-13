import type { Config } from "tailwindcss";

// Only the design-system tokens exist (FINN_DESIGN_SYSTEM.md section 10): Tailwind's default palette is replaced.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      white: "#FFFFFF",
      paper: "var(--paper)", sheet: "var(--sheet)", ink: "var(--ink)", "ink-2": "var(--ink-2)", "ink-3": "var(--ink-3)",
      rule: "var(--rule)", link: "var(--link)", mark: "var(--mark)", up: "var(--up)", down: "var(--down)",
      head: "var(--head)", "on-head": "var(--on-head)", "on-head-2": "var(--on-head-2)",
    },
    fontFamily: {
      sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      num: ["var(--font-num)", "var(--font-sans)", "sans-serif"],
      quote: ["var(--font-quote)", "Georgia", "serif"],
    },
    borderRadius: { none: "0", tag: "4px", ctl: "10px", head: "14px", sheet: "20px", full: "9999px" },
    extend: {
      fontSize: { hero: ["40px", "44px"], title: ["24px", "30px"], item: ["17px", "23px"], body: ["15px", "22px"],
                  sec: ["13px", "18px"], small: ["12px", "16px"] },
      maxWidth: { app: "480px" },
    },
  },
  plugins: [],
};
export default config;
