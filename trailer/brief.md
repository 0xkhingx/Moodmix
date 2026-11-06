# MoodMix trailer: director's brief

## Film
- **One sentence:** Say or type how you feel, and the whole screen becomes your mood, with music to match it or lift it.
- **Audience:** people who'd try a playful music web app; portfolio and social viewers.
- **Duration:** ~25 s (750 frames @ 30 fps).
- **Formats:** 16:9 1920x1080 (primary), 9:16 1080x1920 (social). Separate layouts, same timeline.

## Assets (real only)
- **Logo:** the owner's mark, `web/app/logo.tsx` (single-path SVG), plus wordmark "MoodMix".
- **Type:** Bricolage Grotesque (display), Instrument Sans (text). Font files from the app build (`web/.next/static/media`).
- **Colours:** Cuzzon kit (`web/app/globals.css` tokens) + per-mood ramps (`web/app/moods.ts`).
- **Motion source:** the app's own WebGL mood shader (`web/app/components/MoodBackground.tsx`), re-hosted as a seekable frame function.
- **UI:** real screenshots of the running app (http://localhost:3002), captured in headless Chrome in real states: idle, typing, result (real model output), corrected mood, mood chips.
  - Album art, track titles and artist names are **blurred** in captures. They are third-party content, and showing them in a promo would imply endorsement. Nothing is replaced with invented content.
- **Facts used on screen** (all true for the current build): 7 moods; voice (up to 8 s) or text; tracks to *match* or *lift* a mood; "Not quite right?" lets you correct the mood. Any confidence number shown comes from a real captured result.
- **Audio:** one licensed music track + at most 2-3 subtle UI sounds, sourced with the `real-sound` workflow (licence checked per file, credits recorded). No voiceover.

## Visual rules
- **Keep:** dark blue-hour ground (#14151D), lilac action colour, hairline glass, the living mood gradient as the hero, the ghost mood word, real UI.
- **Avoid:** big centred title on a gradient as the opener; everything fading in; whoosh on every cut; HUD frames, timecodes, corner labels; one accented word per headline; all-caps tracked eyebrows.
- **Never** invent product screens, metrics or claims.

## Deliverables
`shotlist.md` (frames), stills of 3-4 beats, rough cut + contact sheet, critic pass, final `out/moodmix-trailer-16x9.mp4` + `out/moodmix-trailer-9x16.mp4`, poster frames, music credit, source in `src/`.
