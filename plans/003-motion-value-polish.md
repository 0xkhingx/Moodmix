# 003 — Motion value polish (press depth, colour easing, unused token)

- **Status**: DONE
- **Commit**: a434e8a (working tree had uncommitted frontend changes at audit time)
- **Severity**: LOW
- **Category**: Physicality & origin / Easing & duration / Cohesion & tokens
- **Estimated scope**: 1 file, 3 small edits

## Problem

All in `web/app/globals.css`:

1. Mic press is deeper than the 0.95–0.98 range used for press feedback:
   ```css
   .mic:not(:disabled):active {
     transform: scale(0.94);
   }
   ```
2. The logo colour change (mood switch) uses the ease-out token; colour changes should use `ease`:
   ```css
   .brand .hero-logo { ... transition: color 600ms var(--ease-out); }
   ```
   600ms is intentional: it matches the ~0.9s background colour blend. Keep the duration.
3. `--ease-spring: cubic-bezier(0.34, 1.4, 0.64, 1);` in `:root` is referenced nowhere.

## Target

```css
.mic:not(:disabled):active {
  transform: scale(0.96);
}
.brand .hero-logo { ... transition: color 600ms ease; }
/* :root — --ease-spring line removed */
```

## Steps

1. Change `scale(0.94)` to `scale(0.96)` in `.mic:not(:disabled):active`.
2. Change `transition: color 600ms var(--ease-out);` to `transition: color 600ms ease;` in `.brand .hero-logo`.
3. Delete the `--ease-spring` line from `:root` after confirming `grep -rn "ease-spring" web/app` shows only that line.

## Boundaries

- Only these three declarations.

## Verification

- **Mechanical**: `grep -rn "ease-spring" web/app` returns nothing; `npx tsc --noEmit` passes.
- **Feel check**: press the mic button: it gives the same subtle press as the other buttons, not a deep squish. Correct a mood: the logo colour follows the background smoothly.
- **Done when**: both hold.
