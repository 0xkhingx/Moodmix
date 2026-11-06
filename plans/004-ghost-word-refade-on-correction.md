# 004 — Re-fade the ghost word when the mood changes in place

- **Status**: DONE
- **Commit**: a434e8a (working tree had uncommitted frontend changes at audit time)
- **Severity**: LOW (missed opportunity)
- **Category**: Missed opportunities
- **Estimated scope**: 1 file, 1 line

## Problem

When the user corrects the mood ("Not quite right?" chips), the background blends to the new colours over ~0.9s, but the big ghost word teleports from e.g. "Happy" to "Sad" because the element is not remounted, so its 250ms opacity entrance never replays:

```tsx
/* web/app/page.tsx — current */
<div className="ghost" aria-hidden>
  {moodStyle(result.emotion).label}
</div>
```

## Target

Key the element by the mood so React remounts it and the existing `ghost-in` (250ms opacity, `var(--ease-out)`) plays again:

```tsx
<div className="ghost" aria-hidden key={result.emotion}>
  {moodStyle(result.emotion).label}
</div>
```

## Boundaries

- No new keyframes or durations; reuse `ghost-in`.

## Verification

- **Mechanical**: `npx tsc --noEmit` passes.
- **Feel check**: on a result, tap a different mood chip: the ghost word fades in as the new word while the background blends; it no longer snaps.
- **Done when**: that holds.
