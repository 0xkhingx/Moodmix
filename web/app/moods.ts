// Mood palette (from the MoodMix design): one hue per mood, used for the
// WebGL background, breakdown dots, faces, chips and history.

export type Mood = "happy" | "sad" | "angry" | "calm" | "fearful" | "surprised" | "disgusted";

export const MOODS: Mood[] = ["happy", "sad", "angry", "calm", "fearful", "surprised", "disgusted"];

/** How the background moves for a mood (all values blend smoothly on change). */
export type Motion = {
  /** Flow speed (1 = baseline). */
  speed: number;
  /** Domain-warp strength: low = smooth silk, high = turbulent. */
  warp: number;
  /** Feature size: low = big soft blobs, high = busier detail. */
  scale: number;
  /** Constant drift direction (x, y per second), e.g. sad sinks. */
  drift: [number, number];
  /** 0..1 subtle brightness flicker (nervous moods). */
  flicker: number;
};

type MoodStyle = {
  label: string;
  /** Solid swatch (dots, faces, active chips). */
  color: string;
  /** WebGL gradient ramp, dark -> light: ground, deep, mid, light, highlight. */
  ramp: string[];
  motion: Motion;
  /** Static CSS fallback when WebGL is unavailable or still loading. */
  css: string;
  /** Text color that reads on `color` (chips, faces). */
  onColor: string;
};

export const MOOD_STYLE: Record<Mood, MoodStyle> = {
  happy: {
    label: "Happy",
    color: "#F5B82E",
    ramp: ["#E8891A", "#F6A928", "#FFC93C", "#FFE380", "#FFF9E3"],
    motion: { speed: 1.45, warp: 2.2, scale: 0.85, drift: [0.015, 0.06], flicker: 0 },
    css: "radial-gradient(120% 90% at 30% 20%, #FFF9E3 0%, #FFC93C 45%, #E8891A 100%)",
    onColor: "#2B1D00",
  },
  sad: {
    label: "Sad",
    color: "#4A8BE8",
    ramp: ["#11295A", "#2459B0", "#4A8BE8", "#8DBBF2", "#E2EEFF"],
    motion: { speed: 0.45, warp: 1.9, scale: 0.8, drift: [0, -0.05], flicker: 0 },
    css: "radial-gradient(120% 90% at 30% 20%, #8DBBF2 0%, #3E7BD6 45%, #173E7E 100%)",
    onColor: "#06162E",
  },
  angry: {
    label: "Angry",
    color: "#E5484D",
    ramp: ["#4A0A10", "#A51F28", "#E5484D", "#FF8A7A", "#FFD9CF"],
    motion: { speed: 2.2, warp: 3.6, scale: 1.5, drift: [0.04, 0], flicker: 0.04 },
    css: "radial-gradient(120% 90% at 30% 20%, #FF9A7A 0%, #E5484D 45%, #7A1219 100%)",
    onColor: "#2A0306",
  },
  calm: {
    label: "Calm",
    color: "#4CC38A",
    ramp: ["#0A3826", "#1F8A60", "#4CC38A", "#9BE7C4", "#E6FCF1"],
    motion: { speed: 0.4, warp: 1.3, scale: 0.65, drift: [0.015, 0], flicker: 0 },
    css: "radial-gradient(120% 90% at 30% 20%, #A8EBCB 0%, #3DBE8B 45%, #135E45 100%)",
    onColor: "#03261A",
  },
  fearful: {
    label: "Fearful",
    color: "#9174DC",
    ramp: ["#1E1247", "#5638A6", "#9174DC", "#C5B3F5", "#F1EBFF"],
    motion: { speed: 1.0, warp: 3.0, scale: 1.3, drift: [-0.02, 0.01], flicker: 0.12 },
    css: "radial-gradient(120% 90% at 30% 20%, #CDBDF6 0%, #8E6CD8 45%, #33206F 100%)",
    onColor: "#170B33",
  },
  surprised: {
    label: "Surprised",
    color: "#F28C38",
    ramp: ["#5A2206", "#C85E1F", "#F28C38", "#FFC27A", "#FFEFD9"],
    motion: { speed: 1.7, warp: 2.8, scale: 1.15, drift: [0, 0.04], flicker: 0.03 },
    css: "radial-gradient(120% 90% at 30% 20%, #FFCB8E 0%, #F28C38 45%, #A9400F 100%)",
    onColor: "#2E1203",
  },
  disgusted: {
    label: "Disgusted",
    color: "#8E9A95",
    ramp: ["#1B2220", "#4A5753", "#8E9A95", "#C2CCC8", "#F0F4F2"],
    motion: { speed: 0.7, warp: 3.3, scale: 1.45, drift: [0.01, -0.02], flicker: 0 },
    css: "radial-gradient(120% 90% at 30% 20%, #C2CCC8 0%, #7D8A86 45%, #2F3936 100%)",
    onColor: "#111816",
  },
};

/** Idle (no result yet): Cuzzon's blue-hour palette (ground, deep, blue, slate, lilac). */
// Weighted dark like the Cuzzon hero: lilac is a muted top highlight, not a fill.
export const IDLE_RAMP = ["#14151D", "#1C1B2C", "#2C2E45", "#4C5372", "#8E8AA6"];
export const IDLE_MOTION: Motion = { speed: 0.7, warp: 2.8, scale: 1.1, drift: [0.008, 0.004], flicker: 0 };
export const IDLE_CSS = [
  "radial-gradient(60% 70% at 82% 26%, rgba(124,126,157,.55), transparent 70%)",
  "radial-gradient(40% 50% at 70% 10%, rgba(226,212,224,.22), transparent 70%)",
  "radial-gradient(70% 60% at 95% 70%, rgba(76,83,114,.7), transparent 70%)",
  "radial-gradient(80% 80% at 20% 90%, #1b1a2c, transparent 70%)",
  "#14151D",
].join(", ");

export function isMood(x: string): x is Mood {
  return (MOODS as string[]).includes(x);
}

export function moodStyle(m: string): MoodStyle {
  return isMood(m) ? MOOD_STYLE[m] : MOOD_STYLE.disgusted;
}

export function timeAgo(ts: number, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - ts) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}
