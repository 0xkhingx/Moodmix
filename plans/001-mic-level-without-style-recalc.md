# 001 — Share the mic level without per-frame style recalculation

- **Status**: DONE
- **Commit**: a434e8a (working tree had uncommitted frontend changes at audit time)
- **Severity**: HIGH
- **Category**: Performance
- **Estimated scope**: 4 files, ~40 lines

## Problem

The live microphone level is passed around as a CSS custom property on `<html>`:

```ts
/* web/app/page.tsx:302 — current (inside the rAF level loop while recording) */
document.documentElement.style.setProperty("--level", smooth.toFixed(3));
/* web/app/page.tsx:313 — current */
document.documentElement.style.setProperty("--level", "0");
```

```ts
/* web/app/components/MoodBackground.tsx:216 — current (called every animation frame, always) */
const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--level"));
```

```css
/* web/app/globals.css:372-373 — current */
.mic[data-state="recording"] .mic-glow {
  opacity: calc(0.45 + var(--level) * 0.55);
  transform: scale(calc(1 + var(--level) * 0.35));
```

Two costs: (1) the background calls `getComputedStyle` on every frame even when idle, forcing style resolution 60x/second for the whole session; (2) while recording, writing a custom property on the root invalidates styles for every element in the document every frame. Driving a child transform through a CSS variable on a parent is an audit finding: set `transform` directly on the element.

## Target

- A tiny module-level store holds the level: `web/app/micLevel.ts` exporting `export const micLevel = { value: 0 };`
- The page writes `micLevel.value` and sets the glow element's `transform` / `opacity` directly via a ref.
- `MoodBackground` reads `micLevel.value` (no `getComputedStyle`).
- `--level` is removed from CSS.

```css
/* target: recording glow driven by inline transform/opacity from JS */
.mic[data-state="recording"] .mic-glow {
  transition: transform 70ms linear, opacity 70ms linear;
}
```

## Repo conventions to follow

- Per-frame values already live in refs, not React state (see `MoodBackground.tsx`, `pulseRef` / `rampRef`).
- Keep the 70ms linear tracking transition (constant motion → `linear`).

## Steps

1. Create `web/app/micLevel.ts`:
   ```ts
   /** Live microphone level 0..1, shared without React state or CSS variables. */
   export const micLevel = { value: 0 };
   ```
2. `MicButton.tsx`: accept `glowRef?: React.Ref<HTMLSpanElement>` and attach it to `<span className="mic-glow">`. Update the doc comment.
3. `page.tsx`: create `const glowRef = useRef<HTMLSpanElement | null>(null)`, pass it to `MicButton`. In the level loop replace the `setProperty` line with:
   ```ts
   micLevel.value = smooth;
   const g = glowRef.current;
   if (g) {
     g.style.opacity = String(0.45 + smooth * 0.55);
     g.style.transform = `scale(${1 + smooth * 0.35})`;
   }
   ```
   In `stopLevelMeter` set `micLevel.value = 0` and clear `glowRef.current.style.opacity/transform` (`""`).
4. `MoodBackground.tsx`: delete `readLevel` and replace its use with `micLevel.value`.
5. `globals.css`: delete `--level: 0;` from `:root` and the two `calc(... var(--level) ...)` declarations from `.mic[data-state="recording"] .mic-glow` (keep its `transition`).

## Boundaries

- Do NOT change the glow's look, scale range (1 → 1.35) or opacity range (0.45 → 1).
- Do NOT change the background shader.
- If code differs from the excerpts, STOP and report.

## Verification

- **Mechanical**: `cd web && npx tsc --noEmit` passes; `grep -rn "\-\-level\|getComputedStyle" web/app` returns nothing.
- **Feel check**: record and speak: the glow still swells with your voice and the background still brightens/stirs. In DevTools Performance, record 5s idle: no repeating "Recalculate Style" every frame.
- **Done when**: both checks pass.
