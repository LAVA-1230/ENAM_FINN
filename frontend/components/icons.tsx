// Six line icons drawn once at a 1.75px stroke (design system 6.7). Always paired with a label in navigation.
type P = { size?: number; className?: string };
const base = (size = 22) => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.75,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
});

export const IconBrief = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M5 4h14v16H5z" /><path d="M8.5 8.5h7M8.5 12h7M8.5 15.5h4" /></svg>
);
export const IconPortfolio = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 20V10M10 20V4M16 20v-7M21 20H3" /></svg>
);
export const IconResearch = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><circle cx="10.5" cy="10.5" r="6" /><path d="M15 15l5 5" /></svg>
);
export const IconAlerts = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></svg>
);
export const IconBell = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z" /><path d="M10 20.5a2 2 0 0 0 4 0" /></svg>
);
export const IconAsk = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 5h16v11H9l-5 4z" /></svg>
);
export const IconMic = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" /></svg>
);
export const IconSend = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 12l16-8-6 16-2.5-6.5z" /></svg>
);
export const IconBack = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M15 5l-7 7 7 7" /></svg>
);
export const IconPlay = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M8 5v14l11-7z" /></svg>
);
export const IconPause = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M8 5v14M16 5v14" /></svg>
);
export const IconClose = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M6 6l12 12M18 6L6 18" /></svg>
);
export const IconSpeaker = ({ size, className }: P) => (
  <svg {...base(size)} className={className}><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M16.5 9a4 4 0 0 1 0 6" /></svg>
);
