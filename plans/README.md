# Animation plans

Written by the `improve-animations` audit (after `remove-animations`). Execute in order.

| # | Title | Severity | Status |
| --- | --- | --- | --- |
| 001 | Share the mic level without per-frame style recalculation | HIGH | DONE |
| 002 | Reduced motion: drop movement, keep fades | MEDIUM | DONE |
| 003 | Motion value polish (press depth, colour easing, unused token) | LOW | DONE |
| 004 | Re-fade the ghost word when the mood changes in place | LOW | DONE |

Dependencies: 001 before 002 (002's `.mic-glow` rule assumes the glow transform is set inline by 001). 003 and 004 are independent.
