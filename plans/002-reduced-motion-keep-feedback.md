# 002 — Reduced motion: drop movement, keep fades

- **Status**: DONE
- **Commit**: a434e8a (working tree had uncommitted frontend changes at audit time)
- **Severity**: MEDIUM
- **Category**: Accessibility
- **Estimated scope**: 1 file, ~30 lines

## Problem

`web/app/globals.css:1161` makes every animation and transition effectively instant:

```css
/* current */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 1ms !important;
    animation-delay: 0ms !important;
    transition-duration: 1ms !important;
  }
  ...
}
```

Reduced motion means fewer and gentler animations, not zero. This also removes opacity fades (result cards, ghost word, track-list dimming, background fade-in) and colour transitions that aid comprehension.

## Target

Remove only movement; keep opacity/colour transitions at their normal durations:

```css
@media (prefers-reduced-motion: reduce) {
  /* No press scaling. */
  button:not(:disabled):active,
  .mic:not(:disabled):active {
    transform: none;
  }
  /* Mic glow: no scaling with the voice (opacity still tracks it). */
  .mic-glow {
    transform: none !important;
  }
  /* History sheet: fade only. */
  .history[open] {
    animation-name: fade-in;
  }
  /* Spinners keep turning (loading indicators), just slower. */
  .mic[data-state="processing"] .mic-ring,
  .spinner {
    animation-duration: 2s;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
}
```

(The ghost word and result cards are already opacity-only.)

## Steps

1. Replace the whole existing `@media (prefers-reduced-motion: reduce)` block at the end of `web/app/globals.css` with the target block above (including the `@keyframes fade-in`).
2. Confirm no other reduced-motion block uses `!important` duration overrides.

## Boundaries

- Do NOT change any non-reduced-motion rule.
- The WebGL background already handles reduced motion in JS (one still frame); leave it.

## Verification

- **Mechanical**: `cd web && npx tsc --noEmit` passes.
- **Feel check**: DevTools → Rendering → emulate `prefers-reduced-motion: reduce`. Get a result: cards and ghost word still fade in (no movement); pressing a button does not shrink it; the history sheet fades without sliding; recording: the glow brightens but does not grow.
- **Done when**: all of the above hold.
