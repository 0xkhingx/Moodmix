# MoodMix trailer: shot list (30 fps, 750 frames)

Music: "Pop Track 03" by Lily J (Mixkit 729), window from 0.0 s, measured ~107.7 BPM (1 beat ≈ 16.7 f). Beat frames below are re-snapped to the measured beat positions of this track before rendering. What the viewer KNOWS at each exit is the point of each beat.

UI states used (real captures): IDLE (voice) → TEXT TYPING → ANALYZING → RESULT happy → CHIPS (correction) → RESULT sad → HISTORY.
The recognisable component carried through every state: the **colour field + ghost word**.

| # | Frames | Time | Beat | On screen | Viewer knows at exit | Sound |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0–74 | 0.0–2.5 s | HOOK | Macro of the real mic button over the blue-hour field. The ring fills clockwise and the glow breathes on the music. Caption (left): "How are you feeling?" | "This listens to me" | Music in (soft intro); no SFX |
| 2 | 75–164 | 2.5–5.5 s | INPUT | Real input screen (card, right). Text tab; captures step through typing "Finally got the job. I can't stop smiling." Caption: "Say it. Or type it." | Two ways in: voice or text | 1 soft key-tick bed (optional) |
| 3 | 165–224 | 5.5–7.5 s | TURN | Press on "Detect mood" (4 f press, 6 f release). The field blooms from blue-hour to happy gold over 18 f; the ghost word "Happy" rises behind the card | Your mood became the screen | **Hit/swell on the bloom frame (≈180)**: the music's lift lands here |
| 4 | 225–329 | 7.5–11 s | PROOF | Real happy result capture: breakdown "Happy 98%" (real value from the captured run), player card (art blurred). Slow 3% push toward the breakdown. Caption: "Every mood gets its own colour, and music." | It detected it, with real numbers, and found music | Music full |
| 5 | 330–509 | 11–17 s | MONTAGE (the one orchestrated moment) | Full-bleed field cycles through the moods on beats: sad → calm → angry → fearful → surprised → disgusted → happy (about 1 every 2 beats, 25 f). Each mood's ghost word + face, the app's per-mood motion (calm slow, angry fast, sad sinking). No UI | 7 moods, each with its own feel | Cuts land exactly on beats; no whooshes |
| 6 | 510–614 | 17–20.5 s | TACTILE | Real result card; a finger-sized press on the "Sad" chip → field blends to blue, ghost re-fades. Caption: "Not quite right? Tell it." | You're in control; it adapts | 1 soft tap on the press frame |
| 7 | 615–749 | 20.5–25 s | CLOSE | The field settles back to blue-hour; the owner's mark draws on (20 f) beside the "MoodMix" wordmark; line under: "Your mood. Our music." The last 20 f hold. The URL `themoodmix.vercel.app` is shown small only if confirmed live (DECISION: confirm at delivery) | Name + promise | Music resolves on frame 749 → silence tail |

## Beat-locked timing (measured: 109.0 BPM, beat = 16.51 f, bar = 66 f; downbeats 49 115 181 247 313 380 446 512 578 644 710)

| # | Beat | Frames | Time | Snap |
| --- | --- | --- | --- | --- |
| 1 | HOOK | 0–114 | 0.0–3.8 s | music intro; caption enters on downbeat 49 |
| 2 | INPUT | 115–180 | 3.8–6.0 s | card settles on downbeat 115 |
| 3 | TURN | 181–246 | 6.0–8.2 s | **bloom starts on downbeat 181** (press at 175–180) |
| 4 | PROOF | 247–312 | 8.2–10.4 s | result card on downbeat 247 |
| 5 | MONTAGE | 313–511 | 10.4–17.0 s | 6 moods × 2 beats (33 f): sad 313, calm 346, angry 380, fearful 413, surprised 446, disgusted 479 |
| 6 | TACTILE | 512–643 | 17.1–21.4 s | happy result back on 512; **chip press on beat 545**; blend to sad |
| 7 | CLOSE | 644–749 | 21.5–25.0 s | logo draw-on from downbeat 644; "Your mood. Our music." on 677; music fades out to 0 by frame 749 |

## Cue list (picture frames for sound)
```
GLOBAL FRAME  TIME    EVENT
0             0.00s   music in (track starts at 0.0 s)
181           6.03s   bloom: field turns gold (downbeat)
313           10.43s  montage first cut (then every 33 f, on beats)
545           18.17s  chip press (soft tap)
644           21.47s  logo mark begins draw-on (downbeat)
719-749       24.0s   music fade, silent on 749
```

## 9:16 variant
Same states and frames. Captures at phone width (390x844 @2x → 780x1688, scaled to 1080 width). Caption in the top third at 88 px. The montage ghost words are larger (30% of height). No side-by-side layout.
