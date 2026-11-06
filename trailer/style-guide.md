# MoodMix trailer: style guide

All values come from the shipped app (`web/app/globals.css`, `moods.ts`) unless marked DECISION.

## Palette
| Role | Hex |
| --- | --- |
| Ground | `#14151D` |
| Surface (glass) | `rgba(28,29,40,.78)`, hairline `rgba(236,235,241,.13)` |
| Ivory text | `#ECEBF1` |
| Muted text | `#C9C9D8` / `#A3A5BD` |
| Action (lilac) | `#E2D4E0` on ink `#14151D` |
| Idle shader ramp | `#14151D #1C1B2C #2C2E45 #4C5372 #8E8AA6` |
| Mood swatches | happy `#F5B82E`, sad `#4A8BE8`, angry `#E5484D`, calm `#4CC38A`, fearful `#9174DC`, surprised `#F28C38`, disgusted `#8E9A95` |

## Type
- **Display:** Bricolage Grotesque 700/800, tracking -0.035 to -0.055 em. Ghost word: 800, about 22% of frame height, overlay blend (as in the app).
- **Text:** Instrument Sans 500/600.
- **Captions** (DECISION): sentence case, left-aligned on a 120 px (16:9) / 96 px (9:16) margin, display 700. 16:9: 64 px; 9:16: 88 px. Max 5 words per card, one card on screen at a time. No accent-coloured word, no all-caps eyebrow.

## Composition
- The eye goes first to the colour field, then the one caption, then the UI.
- 16:9: UI captures sit right of centre in a rounded card (radius 28 px, hairline, soft shadow); captions sit left.
- 9:16: phone-width captures, larger; caption in the top third.
- Safe area: 6% inset; no type within 96 px of any edge.

## Motion (one rule per class)
| Class | Rule |
| --- | --- |
| Colour field (shader) | Always flowing; mood changes blend over 18 frames (0.6 s), per-mood speed and warp exactly as in the app |
| Headlines / captions | Strong entrance: 10 frames, translateY 24 px → 0 + opacity, ease-out `cubic-bezier(0.23,1,0.32,1)`; stable hold; exit 6 frames opacity only |
| UI card | Controlled settle: 16 frames, scale 0.96 → 1 + opacity, ease-out; camera push on cards ≤ 4% over a shot |
| Micro UI (press, chip) | 4-frame press to scale 0.96, release 6 frames |
| Logo | Draw-on by mask, 20 frames, then hold |
| Cuts | Hard cuts on music beats. No whoosh transitions. The single orchestrated moment is the mood montage. |

- **Pacing** (DECISION): a new state every ~2 s; the montage cuts every beat (~0.5 s).
- **Texture:** the app's film grain (opacity 0.06) over everything.

## Do not
Copy other products' trailers; invent screens or numbers; show album art or artist names unblurred; use more than 3 SFX; end on a logo with nothing else on screen before it.
