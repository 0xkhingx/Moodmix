import type { Ref } from "react";

import { MicIcon, StopIcon } from "./icons";

type Props = {
  state: "idle" | "recording" | "processing";
  /** 0..1 share of the max recording time used. */
  progress: number;
  disabled?: boolean;
  onClick: () => void;
  /** The page sets this element's transform/opacity directly from the live mic level. */
  glowRef?: Ref<HTMLSpanElement>;
};

const R = 54;
const C = 2 * Math.PI * R;

/**
 * Big circular record control. The ring fills over the recording window and a
 * glow follows the live mic level (the page drives it through `glowRef`),
 * so the button visibly "hears" you.
 */
export function MicButton({ state, progress, disabled, onClick, glowRef }: Props) {
  const recording = state === "recording";
  const label =
    state === "recording" ? "Stop recording" : state === "processing" ? "Analyzing" : "Start recording";
  return (
    <button
      type="button"
      className="mic"
      data-state={state}
      onClick={onClick}
      disabled={disabled || state === "processing"}
      aria-label={label}
      aria-pressed={recording}
    >
      <span className="mic-glow" ref={glowRef} aria-hidden />
      <svg className="mic-ring" viewBox="0 0 120 120" aria-hidden focusable={false}>
        <circle cx="60" cy="60" r={R} className="mic-ring-track" />
        <circle
          cx="60"
          cy="60"
          r={R}
          className="mic-ring-fill"
          strokeDasharray={C}
          strokeDashoffset={state === "processing" ? C * 0.75 : C * (1 - progress)}
        />
      </svg>
      <span className="mic-core">
        {recording ? <StopIcon width={30} height={30} /> : <MicIcon width={34} height={34} />}
      </span>
    </button>
  );
}
