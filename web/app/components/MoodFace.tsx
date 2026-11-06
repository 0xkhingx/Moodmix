import { useId } from "react";

import { type Mood, MOOD_STYLE } from "../moods";

const INK = "#1A1712";

/** Simple drawn faces for the seven moods (decorative; pair with a text label). */
export function MoodFace({ mood, size = 48 }: { mood: Mood; size?: number }) {
  const s = MOOD_STYLE[mood];
  const shine = `shine-${useId().replace(/:/g, "")}`;
  const stroke = { stroke: INK, strokeWidth: 2.6, strokeLinecap: "round" as const, fill: "none" };
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden focusable={false} className="mood-face">
      <circle cx="24" cy="24" r="22" fill={s.color} />
      <circle cx="24" cy="24" r="22" fill={`url(#${shine})`} />
      <defs>
        <radialGradient id={shine} cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#fff" stopOpacity="0.35" />
          <stop offset="0.6" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
      </defs>
      {mood === "happy" && (
        <>
          <circle cx="17" cy="20" r="2.4" fill={INK} />
          <circle cx="31" cy="20" r="2.4" fill={INK} />
          <path d="M15 28c4 6 14 6 18 0" {...stroke} />
        </>
      )}
      {mood === "sad" && (
        <>
          <circle cx="17" cy="21" r="2.4" fill={INK} />
          <circle cx="31" cy="21" r="2.4" fill={INK} />
          <path d="M16 34c4-5 12-5 16 0" {...stroke} />
        </>
      )}
      {mood === "angry" && (
        <>
          <path d="M13 16l7 3M35 16l-7 3" {...stroke} />
          <circle cx="18" cy="23" r="2.2" fill={INK} />
          <circle cx="30" cy="23" r="2.2" fill={INK} />
          <path d="M17 34c4-4 10-4 14 0" {...stroke} />
        </>
      )}
      {mood === "calm" && (
        <>
          <path d="M13 21c2 2 6 2 8 0M27 21c2 2 6 2 8 0" {...stroke} />
          <path d="M17 29c3 3 11 3 14 0" {...stroke} />
        </>
      )}
      {mood === "fearful" && (
        <>
          <path d="M13 17l6-2M35 17l-6-2" {...stroke} />
          <circle cx="18" cy="22" r="2.4" fill={INK} />
          <circle cx="30" cy="22" r="2.4" fill={INK} />
          <path d="M17 33c2-2 4-2 7 0s5 2 7 0" {...stroke} />
        </>
      )}
      {mood === "surprised" && (
        <>
          <path d="M13 15c2-2 5-2 7 0M28 15c2-2 5-2 7 0" {...stroke} />
          <circle cx="17" cy="21" r="2.6" fill={INK} />
          <circle cx="31" cy="21" r="2.6" fill={INK} />
          <ellipse cx="24" cy="32" rx="4" ry="5" fill={INK} />
        </>
      )}
      {mood === "disgusted" && (
        <>
          <path d="M13 18l7 2M35 18l-7 2" {...stroke} />
          <path d="M15 23h6M27 23h6" {...stroke} />
          <path d="M16 33l4-3 4 3 4-3 4 3" {...stroke} />
        </>
      )}
    </svg>
  );
}
