import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

const base = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

/** Waveform mark from the MoodMix design. */
export function WaveLogo(p: P) {
  const bars = [6, 12, 18, 24, 16, 10, 20, 8];
  return (
    <svg viewBox="0 0 34 26" width={34} height={26} aria-hidden focusable={false} {...p}>
      {bars.map((h, i) => (
        <rect key={i} x={i * 4.3} y={(26 - h) / 2} width={2.6} height={h} rx={1.3} fill="currentColor" />
      ))}
    </svg>
  );
}

export const MicIcon = (p: P) => (
  <svg {...base} {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v3" />
  </svg>
);

export const StopIcon = (p: P) => (
  <svg {...base} {...p}>
    <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" />
  </svg>
);

export const KeyboardIcon = (p: P) => (
  <svg {...base} {...p}>
    <rect x="2.5" y="6" width="19" height="12" rx="2" />
    <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" />
  </svg>
);

export const ClockIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const CloseIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const ArrowRight = (p: P) => (
  <svg {...base} {...p}>
    <path d="M5 12h14" />
    <path d="m13 6 6 6-6 6" />
  </svg>
);

export const ResetIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7" />
    <path d="M3 4v5h5" />
  </svg>
);

export const SpotifyIcon = (p: P) => (
  <svg viewBox="0 0 24 24" width={20} height={20} aria-hidden focusable={false} {...p}>
    <circle cx="12" cy="12" r="12" fill="#1DB954" />
    <path
      d="M17.3 16.6a.75.75 0 0 1-1 .25c-2.8-1.7-6.3-2.1-10.4-1.2a.75.75 0 1 1-.33-1.46c4.5-1 8.4-.56 11.5 1.4.35.21.46.67.24 1.01Zm1.4-3.2a.94.94 0 0 1-1.3.3c-3.2-2-8.1-2.5-11.9-1.4a.94.94 0 1 1-.55-1.8c4.3-1.3 9.7-.68 13.4 1.6.44.27.58.85.31 1.3Zm.12-3.3C15 7.8 8.6 7.6 4.9 8.7a1.13 1.13 0 1 1-.66-2.16c4.2-1.3 11.3-1 15.8 1.6a1.13 1.13 0 0 1-1.16 1.94Z"
      fill="#000"
    />
  </svg>
);

export const PauseIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M9 6v12M15 6v12" />
  </svg>
);

export const PlayIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M8 5.5v13l10-6.5-10-6.5Z" fill="currentColor" stroke="none" />
  </svg>
);
