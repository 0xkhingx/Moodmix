"use client";

import dynamic from "next/dynamic";
import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { Bricolage_Grotesque, Instrument_Sans } from "next/font/google";

import { MicButton } from "./components/MicButton";
import { LogoMark } from "./logo";
import { micLevel } from "./micLevel";
import { MoodFace } from "./components/MoodFace";
import {
  ArrowRight,
  ClockIcon,
  CloseIcon,
  KeyboardIcon,
  MicIcon,
  PauseIcon,
  PlayIcon,
  ResetIcon,
  SpotifyIcon,
} from "./components/icons";
import {
  IDLE_CSS,
  IDLE_MOTION,
  IDLE_RAMP,
  MOODS,
  MOOD_STYLE,
  isMood,
  moodStyle,
  timeAgo,
} from "./moods";

// WebGL background is client-only and loaded after first paint; the CSS
// gradient underneath shows until it is ready (or if WebGL is unavailable).
const MoodBackground = dynamic(() => import("./components/MoodBackground"), {
  ssr: false,
});

// Cuzzon type pairing: Bricolage Grotesque (display) + Instrument Sans (text).
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-display",
  display: "swap",
});
const textFont = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-text",
  display: "swap",
});

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

// The speech model scores ~2.5s windows; a few seconds is plenty.
const MAX_RECORD_SECONDS = 8;
// After this long, assume the backend is cold-starting and say so.
const SLOW_REQUEST_MS = 5000;
const REQUEST_TIMEOUT_MS = 90000;

// Preferred recording formats, in order. Safari/iOS has no webm support.
const RECORDING_FORMATS: { mime: string; ext: string }[] = [
  { mime: "audio/webm;codecs=opus", ext: "webm" },
  { mime: "audio/webm", ext: "webm" },
  { mime: "audio/mp4", ext: "m4a" },
  { mime: "audio/ogg;codecs=opus", ext: "ogg" },
];

type Track = {
  id: string;
  name: string;
  artist: string;
  album: string;
  album_image: string | null;
  preview_url: string | null;
  uri: string;
  external_url: string;
};

type Mode = "match" | "lift";

type PredictResponse = {
  emotion: string;
  confidence: number;
  probabilities?: Record<string, number>;
  source: string;
  mode?: Mode;
  icon: string;
  description: string;
  query: string;
  tracks: Track[];
  // Set client-side when the user corrects the detected mood.
  predicted?: string;
};

type TracksResponse = {
  mood: string;
  mode: Mode;
  query: string;
  description: string;
  tracks: Track[];
};

type HistoryEntry = { emotion: string; source: string; at: number };

type Tab = "voice" | "text";
const TABS: Tab[] = ["voice", "text"];

const HISTORY_KEY = "moodmix.history.v1";
const BG_PAUSED_KEY = "moodmix.bgPaused.v1";
const MODE_KEY = "moodmix.mode.v1";
const HISTORY_MAX = 30;

const STEPS = [
  {
    title: "Input",
    body: "Record a short voice clip (up to 8 seconds) or type how you feel.",
  },
  {
    title: "Detection",
    body: "Machine-learning models classify it into one of 7 moods.",
  },
  {
    title: "Music",
    body: "Finds Spotify tracks that match your mood, or lift it.",
  },
  {
    title: "Display",
    body: "The page takes on your mood's colour with a detailed breakdown.",
  },
];

// Browser storage can throw (private mode, blocked storage); never let it break the app.
function readStore<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStore(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

function haptic(ms = 12) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* unsupported */
  }
}

function pickRecordingFormat() {
  if (typeof MediaRecorder === "undefined") return null;
  for (const f of RECORDING_FORMATS) {
    if (MediaRecorder.isTypeSupported(f.mime)) return f;
  }
  // Let the browser choose; extension is a best guess the API accepts.
  return { mime: "", ext: "webm" };
}

async function callApi<T = PredictResponse>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (!API_URL) {
    throw new Error(
      "The app is misconfigured (no API URL). Please try again later.",
    );
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let r: Response;
  try {
    r = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("The server took too long to respond. Please try again.");
    }
    throw new Error(
      "Couldn't reach the server. Check your connection and try again.",
    );
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    if (r.status === 429)
      throw new Error("You're going a bit fast. Wait a minute and try again.");
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new Error(
      detail ?? `Something went wrong (${r.status}). Please try again.`,
    );
  }
  return r.json();
}

/** Top-3 moods plus an "Others" remainder, as in the design's breakdown card. */
function breakdown(probs: Record<string, number> | undefined) {
  if (!probs) return [];
  const sorted = Object.entries(probs).sort((a, b) => b[1] - a[1]);
  const top = sorted
    .slice(0, 3)
    .map(([label, p]) => ({ label, p, color: moodStyle(label).color }));
  const rest = sorted.slice(3).reduce((s, [, p]) => s + p, 0);
  if (rest > 0.005) top.push({ label: "Others", p: rest, color: "#7C7E9D" });
  return top;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("voice");
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [activeTrack, setActiveTrack] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("match");
  const [tracksLoading, setTracksLoading] = useState(false);
  const [shareText, setShareText] = useState(false);
  const [lastText, setLastText] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [now, setNow] = useState(() => Date.now());
  // Last cleared history, kept so "Clear" can be undone.
  const [cleared, setCleared] = useState<HistoryEntry[] | null>(null);
  const [bgPaused, setBgPaused] = useState(false);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const levelRafRef = useRef(0);
  const glowRef = useRef<HTMLSpanElement | null>(null);
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({
    voice: null,
    text: null,
  });
  const historyRef = useRef<HTMLDialogElement | null>(null);
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const undoRef = useRef<HTMLButtonElement | null>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement | null>(null);

  // Per-viewer conveniences restored after mount (avoids SSR/hydration mismatch).
  useEffect(() => {
    setHistory(readStore<HistoryEntry[]>(HISTORY_KEY, []));
    const savedMode = readStore<Mode>(MODE_KEY, "match");
    setMode(savedMode === "lift" ? "lift" : "match");
    setBgPaused(readStore<boolean>(BG_PAUSED_KEY, false) === true);
  }, []);

  // Keep "2h ago" labels fresh.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  function pushHistory(entry: HistoryEntry, replaceLast = false) {
    setHistory((prev) => {
      const base = replaceLast ? prev.slice(1) : prev;
      const next = [entry, ...base].slice(0, HISTORY_MAX);
      writeStore(HISTORY_KEY, next);
      return next;
    });
  }

  function clearHistory() {
    setCleared(history);
    setHistory([]);
    writeStore(HISTORY_KEY, []);
  }

  function undoClear() {
    if (!cleared) return;
    setHistory(cleared);
    writeStore(HISTORY_KEY, cleared);
    setCleared(null);
  }

  // The Clear button disappears with the list; put focus on Undo instead.
  useEffect(() => {
    if (cleared) undoRef.current?.focus();
  }, [cleared]);

  function toggleBgPaused() {
    setBgPaused((p) => {
      writeStore(BG_PAUSED_KEY, !p);
      return !p;
    });
  }

  // Release the mic and audio graph if the page unmounts mid-recording.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      cancelAnimationFrame(levelRafRef.current);
      audioCtxRef.current?.close().catch(() => undefined);
    };
  }, []);

  // Recording timer + auto-stop.
  useEffect(() => {
    if (!recording) return;
    const startedAt = Date.now();
    setElapsed(0);
    const id = setInterval(() => {
      const secs = (Date.now() - startedAt) / 1000;
      setElapsed(secs);
      if (secs >= MAX_RECORD_SECONDS) stopRecording();
    }, 100);
    return () => clearInterval(id);
  }, [recording]);

  // Flag slow requests so a cold-starting backend doesn't look broken.
  useEffect(() => {
    if (!loading) {
      setSlow(false);
      return;
    }
    const t = setTimeout(() => setSlow(true), SLOW_REQUEST_MS);
    return () => clearTimeout(t);
  }, [loading]);

  // Move focus to the result heading so keyboard/screen-reader users land on it.
  const resultKey = result ? `${result.emotion}-${result.predicted ?? ""}` : "";
  useEffect(() => {
    if (resultKey && !result?.predicted) resultHeadingRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultKey]);

  /** Live mic level -> shared store + the glow's inline transform (no React re-render, no style recalc). */
  function startLevelMeter(stream: MediaStream) {
    try {
      const Ctx =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new Ctx();
      // iOS Safari can start the context suspended after the permission prompt.
      if (ctx.state === "suspended") ctx.resume().catch(() => undefined);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      audioCtxRef.current = ctx;
      const buf = new Uint8Array(analyser.fftSize);
      let smooth = 0;
      const loop = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.min(1, Math.sqrt(sum / buf.length) * 4);
        smooth = smooth * 0.75 + rms * 0.25;
        micLevel.value = smooth;
        const g = glowRef.current;
        if (g) {
          g.style.opacity = String(0.45 + smooth * 0.55);
          g.style.transform = `scale(${1 + smooth * 0.35})`;
        }
        levelRafRef.current = requestAnimationFrame(loop);
      };
      loop();
    } catch {
      /* level meter is optional */
    }
  }

  function stopLevelMeter() {
    cancelAnimationFrame(levelRafRef.current);
    micLevel.value = 0;
    if (glowRef.current) {
      glowRef.current.style.opacity = "";
      glowRef.current.style.transform = "";
    }
    audioCtxRef.current?.close().catch(() => undefined);
    audioCtxRef.current = null;
  }

  async function startRecording() {
    setError(null);
    const format = pickRecordingFormat();
    if (!format || !navigator.mediaDevices?.getUserMedia) {
      setError("This browser can't record audio. Use Text instead.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      setError(
        name === "NotFoundError"
          ? "No microphone found. Plug one in or use Text instead."
          : "Microphone access denied. Allow mic access or use Text instead.",
      );
      return;
    }
    try {
      const rec = format.mime
        ? new MediaRecorder(stream, { mimeType: format.mime })
        : new MediaRecorder(stream);
      const mime = rec.mimeType || format.mime || "audio/webm";
      const ext = mime.includes("mp4")
        ? "m4a"
        : mime.includes("ogg")
          ? "ogg"
          : format.ext;
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mime });
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        stopLevelMeter();
        submitSpeech(blob, ext);
      };
      rec.start();
      recorderRef.current = rec;
      streamRef.current = stream;
      startLevelMeter(stream);
      setRecording(true);
      haptic();
    } catch {
      stream.getTracks().forEach((t) => t.stop());
      setError("Recording isn't supported in this browser. Use Text instead.");
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
      haptic(8);
    }
    setRecording(false);
  }

  async function run(path: string, init: RequestInit) {
    setLoading(true);
    setError(null);
    setActiveTrack(null);
    try {
      const data = await callApi(path, init);
      setResult(data);
      setActiveTrack(data.tracks[0]?.id ?? null);
      pushHistory({
        emotion: data.emotion,
        source: data.source,
        at: Date.now(),
      });
      haptic(18);
      // Spotify can be slow; the API returns the mood first. Fetch tracks now.
      if (data.tracks.length === 0) loadTracks(data.emotion, mode);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Request failed. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  function submitText() {
    if (!text.trim()) {
      setError("Type something first.");
      textRef.current?.focus();
      return;
    }
    setLastText(text);
    setShareText(false);
    run("/predict/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode }),
    });
  }

  function submitSpeech(blob: Blob, ext: string) {
    if (blob.size === 0) {
      setError("Nothing was recorded. Try again.");
      return;
    }
    const form = new FormData();
    form.append("file", blob, `clip.${ext}`);
    form.append("mode", mode);
    run("/predict/speech", { method: "POST", body: form });
  }

  // Refresh tracks for a mood without re-running the model.
  async function loadTracks(mood: string, nextMode: Mode): Promise<boolean> {
    setTracksLoading(true);
    setError(null);
    try {
      const data = await callApi<TracksResponse>(
        `/tracks?mood=${encodeURIComponent(mood)}&mode=${nextMode}`,
      );
      setResult((prev) =>
        prev
          ? {
              ...prev,
              emotion: data.mood,
              description: data.description,
              query: data.query,
              tracks: data.tracks,
              mode: data.mode,
            }
          : prev,
      );
      setActiveTrack(data.tracks[0]?.id ?? null);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load tracks.");
      return false;
    } finally {
      setTracksLoading(false);
    }
  }

  async function changeMode(next: Mode) {
    if (next === mode || tracksLoading) return;
    const prev = mode;
    setMode(next);
    writeStore(MODE_KEY, next);
    haptic(6);
    // If the tracks for the new direction fail to load, keep the old direction
    // so the label and the pressed button match the tracks still on screen.
    if (result && !(await loadTracks(result.emotion, next))) {
      setMode(prev);
      writeStore(MODE_KEY, prev);
    }
  }

  async function correctMood(mood: string) {
    if (!result || mood === result.emotion || tracksLoading) return;
    const predicted = result.predicted ?? result.emotion;
    // Fire-and-forget: a failed feedback post must not block the user.
    callApi<{ id: number }>("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: result.source,
        predicted,
        corrected: mood,
        confidence: result.confidence,
        text: result.source === "text" && shareText ? lastText : null,
      }),
    }).catch(() => undefined);
    setResult({ ...result, predicted, emotion: mood });
    pushHistory({ emotion: mood, source: result.source, at: Date.now() }, true);
    haptic(10);
    await loadTracks(mood, mode);
  }

  function reset() {
    setResult(null);
    setError(null);
    setActiveTrack(null);
    window.scrollTo({ top: 0 });
  }

  function onTabKey(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const i = TABS.indexOf(tab);
    const next =
      TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
    setTab(next);
    tabRefs.current[next]?.focus();
  }

  const mood = result && isMood(result.emotion) ? result.emotion : null;
  const ramp = mood ? MOOD_STYLE[mood].ramp : IDLE_RAMP;
  const motion = mood ? MOOD_STYLE[mood].motion : IDLE_MOTION;
  const bgCss = mood ? MOOD_STYLE[mood].css : IDLE_CSS;
  const rows = breakdown(result?.probabilities);
  const hasTracks = !!result && result.tracks.length > 0;
  const nowPlaying =
    result?.tracks.find((t) => t.id === activeTrack) ?? result?.tracks[0];
  const spotifyHref = result
    ? `https://open.spotify.com/search/${encodeURIComponent(result.query || result.emotion)}`
    : null;
  const micState =
    loading && tab === "voice"
      ? "processing"
      : recording
        ? "recording"
        : "idle";

  return (
    <div
      className={`${display.variable} ${textFont.variable} app`}
      data-view={result ? "result" : "input"}
    >
      {/* Background: CSS gradient (instant) under the WebGL shader gradient. */}
      <div className="bg" aria-hidden>
        <div className="bg-css" style={{ background: bgCss }} />
        <MoodBackground
          ramp={ramp}
          motion={motion}
          pulseKey={resultKey}
          paused={bgPaused}
        />
        <div className="bg-veil" />
      </div>

      <header className="topbar">
        <button
          type="button"
          className="brand"
          onClick={reset}
          aria-label="MoodMix home"
        >
          <span
            className="brand-mark"
            style={{ color: mood ? MOOD_STYLE[mood].color : "var(--accent)" }}
          >
            <LogoMark />
          </span>
          <span className="brand-word">MoodMix</span>
        </button>
        <div className="topbar-actions">
          <button
            type="button"
            className="glass-btn icon-btn"
            aria-label="Pause background animation"
            aria-pressed={bgPaused}
            onClick={toggleBgPaused}
          >
            {bgPaused ? <PlayIcon /> : <PauseIcon />}
          </button>
          <button
            type="button"
            className="glass-btn icon-btn"
            aria-label="Recent moods"
            aria-haspopup="dialog"
            onClick={() => historyRef.current?.showModal()}
          >
            <ClockIcon />
          </button>
        </div>
      </header>

      <main>
        <h1 className="visually-hidden">
          MoodMix: tell us how you feel, get the perfect soundtrack
        </h1>

        {!result ? (
          <section className="stage" aria-labelledby="ask">
            <h2 id="ask" className="ask">
              How are you feeling?
            </h2>
            <p className="ask-sub">Speak your mind or type it out.</p>

            <div className="seg" role="tablist" aria-label="Input method">
              {TABS.map((t) => (
                <button
                  key={t}
                  ref={(el) => {
                    tabRefs.current[t] = el;
                  }}
                  id={`tab-${t}`}
                  role="tab"
                  aria-selected={tab === t}
                  aria-controls={`panel-${t}`}
                  tabIndex={tab === t ? 0 : -1}
                  onClick={() => setTab(t)}
                  onKeyDown={onTabKey}
                  disabled={recording}
                >
                  {t === "voice" ? (
                    <MicIcon width={16} height={16} />
                  ) : (
                    <KeyboardIcon width={16} height={16} />
                  )}
                  {t === "voice" ? "Voice" : "Text"}
                </button>
              ))}
            </div>

            {tab === "voice" ? (
              <div
                className="panel"
                role="tabpanel"
                id="panel-voice"
                aria-labelledby="tab-voice"
              >
                <div className="mic-wrap">
                  <MicButton
                    state={micState}
                    progress={
                      recording ? Math.min(1, elapsed / MAX_RECORD_SECONDS) : 0
                    }
                    onClick={recording ? stopRecording : startRecording}
                    glowRef={glowRef}
                  />
                </div>
                <p className="mic-hint" aria-live="polite">
                  {micState === "recording"
                    ? `Listening… ${Math.max(0, Math.ceil(MAX_RECORD_SECONDS - elapsed))}s left. Tap to finish.`
                    : micState === "processing"
                      ? slow
                        ? "Waking up the server…"
                        : "Reading your mood…"
                      : `Tap to record (up to ${MAX_RECORD_SECONDS} seconds)`}
                </p>
              </div>
            ) : (
              <div
                className="panel"
                role="tabpanel"
                id="panel-text"
                aria-labelledby="tab-text"
              >
                <div className="glass compose">
                  <textarea
                    ref={textRef}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey))
                        submitText();
                    }}
                    maxLength={2000}
                    aria-label="Describe how you feel"
                    aria-invalid={!!error && !text.trim()}
                    aria-describedby={error ? "form-error" : undefined}
                    placeholder="e.g. Finally got the job, I can't stop smiling"
                  />
                  <div className="compose-foot">
                    <span className="hint">Ctrl + Enter to send</span>
                    <button
                      type="button"
                      className="btn-accent"
                      onClick={submitText}
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <span className="spinner" aria-hidden />
                          {slow ? "Waking up the server…" : "Analyzing…"}
                        </>
                      ) : (
                        <>
                          Detect mood <ArrowRight width={16} height={16} />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div
              className="seg seg-small"
              role="group"
              aria-label="Music direction"
            >
              {(["match", "lift"] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={mode === m}
                  onClick={() => changeMode(m)}
                >
                  {m === "match" ? "Match my mood" : "Lift my mood"}
                </button>
              ))}
            </div>

            <p
              role="status"
              className={slow && loading ? "note" : "visually-hidden"}
            >
              {slow && loading
                ? "First request after a quiet spell can take up to a minute while the server starts."
                : ""}
            </p>
            {error && (
              <p className="error" role="alert" id="form-error">
                {error}
              </p>
            )}
          </section>
        ) : (
          <section className="result" aria-labelledby="result-h">
            <div className="ghost" aria-hidden key={result.emotion}>
              {moodStyle(result.emotion).label}
            </div>

            <div className="result-head">
              <h2
                id="result-h"
                ref={resultHeadingRef}
                tabIndex={-1}
                className="glass result-title"
              >
                {mood && <MoodFace mood={mood} size={40} />}
                <span>
                  <span className="result-mood">
                    {moodStyle(result.emotion).label}
                  </span>
                  <span className="result-meta">
                    {result.predicted
                      ? `You picked this · we detected ${moodStyle(result.predicted).label.toLowerCase()}`
                      : `${Math.round(result.confidence * 100)}% confident · ${result.description}`}
                  </span>
                </span>
              </h2>
              <button type="button" className="glass-btn again" onClick={reset}>
                <ResetIcon width={16} height={16} />
                Check another mood
              </button>
            </div>

            <div className="grid">
              <div className="glass card player" aria-busy={tracksLoading}>
                {hasTracks && nowPlaying ? (
                  <>
                    <div className="np">
                      {nowPlaying.album_image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={nowPlaying.album_image}
                          alt=""
                          width={88}
                          height={88}
                        />
                      ) : (
                        <span className="np-art" aria-hidden />
                      )}
                      <div className="np-meta">
                        <span className="np-title">{nowPlaying.name}</span>
                        <span className="np-artist">{nowPlaying.artist}</span>
                      </div>
                      <a
                        className="np-spotify"
                        href={nowPlaying.external_url}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Open ${nowPlaying.name} in Spotify`}
                      >
                        <SpotifyIcon width={26} height={26} />
                      </a>
                    </div>
                    <iframe
                      key={nowPlaying.id}
                      className="embed"
                      title={`Spotify player: ${nowPlaying.name}`}
                      src={`https://open.spotify.com/embed/track/${nowPlaying.id}?utm_source=generator&theme=0`}
                      height={80}
                      allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
                      loading="lazy"
                    />
                  </>
                ) : (
                  <div className="np-empty">
                    {tracksLoading ? (
                      <p className="hint">
                        <span className="spinner" aria-hidden /> Finding tracks…
                      </p>
                    ) : (
                      <>
                        <p className="hint">
                          Couldn&apos;t load tracks right now.
                        </p>
                        <div className="np-empty-actions">
                          <button
                            type="button"
                            className="btn-accent"
                            onClick={() => loadTracks(result.emotion, mode)}
                          >
                            <ResetIcon width={16} height={16} /> Retry tracks
                          </button>
                          {spotifyHref && (
                            <a
                              href={spotifyHref}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Search Spotify instead
                            </a>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

              {rows.length > 0 && (
                <div className="glass card breakdown">
                  <h3 className="card-h">
                    {result.predicted ? "What we detected" : "Mood breakdown"}
                  </h3>
                  <ul>
                    {rows.map((r) => (
                      <li key={r.label}>
                        <span
                          className="dot"
                          style={{ background: r.color }}
                          aria-hidden
                        />
                        <span className="bd-label">
                          {r.label === "Others"
                            ? "Others"
                            : moodStyle(r.label).label}
                        </span>
                        <span className="bd-bar" aria-hidden>
                          <span
                            style={{
                              transform: `scaleX(${Math.max(0.02, r.p)})`,
                              background: r.color,
                            }}
                          />
                        </span>
                        <span className="bd-val">{Math.round(r.p * 100)}%</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {(hasTracks || tracksLoading) && (
                <div className="glass card tracks" aria-busy={tracksLoading}>
                  <div className="card-head">
                    <h3 className="card-h">
                      {tracksLoading
                        ? "Finding tracks…"
                        : (result.mode ?? mode) === "lift"
                          ? "To lift your mood"
                          : "Matching your mood"}
                    </h3>
                    <div
                      className="seg seg-small"
                      role="group"
                      aria-label="Music direction"
                    >
                      {(["match", "lift"] as Mode[]).map((m) => (
                        <button
                          key={m}
                          type="button"
                          aria-pressed={mode === m}
                          onClick={() => changeMode(m)}
                          aria-disabled={tracksLoading}
                        >
                          {m === "match" ? "Match" : "Lift"}
                        </button>
                      ))}
                    </div>
                  </div>
                  {hasTracks && (
                    <ul className="track-list">
                      {result.tracks.map((t) => (
                        <li key={t.id}>
                          <button
                            type="button"
                            className="track"
                            aria-pressed={activeTrack === t.id}
                            onClick={() => {
                              setActiveTrack(t.id);
                              haptic(6);
                            }}
                          >
                            {t.album_image ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={t.album_image}
                                alt=""
                                width={44}
                                height={44}
                                loading="lazy"
                              />
                            ) : (
                              <span className="track-noart" aria-hidden />
                            )}
                            <span className="track-meta">
                              <span className="track-name">{t.name}</span>
                              <span className="track-artist">{t.artist}</span>
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div className="glass card correct">
                <h3 className="card-h" aria-live="polite">
                  {result.predicted ? "Updated. Thanks!" : "Not quite right?"}
                </h3>
                <p className="hint">
                  {result.predicted
                    ? "Your correction helps train MoodMix."
                    : "Pick how you actually feel. We'll swap the tracks and learn from it."}
                </p>
                <div
                  className="chips"
                  role="group"
                  aria-label="Choose your actual mood"
                >
                  {MOODS.map((m) => (
                    <button
                      key={m}
                      type="button"
                      className="chip"
                      aria-pressed={result.emotion === m}
                      aria-disabled={tracksLoading}
                      onClick={() => correctMood(m)}
                      style={{
                        ["--chip" as string]: MOOD_STYLE[m].color,
                        ["--on-chip" as string]: MOOD_STYLE[m].onColor,
                      }}
                    >
                      {MOOD_STYLE[m].label}
                    </button>
                  ))}
                </div>
                {result.source === "text" && !result.predicted && (
                  <label className="share">
                    <input
                      type="checkbox"
                      checked={shareText}
                      onChange={(e) => setShareText(e.target.checked)}
                    />
                    Include what I typed with my correction
                  </label>
                )}
              </div>

              {history.length > 0 && (
                <div className="glass card recent">
                  <h3 className="card-h">Your recent moods</h3>
                  <ol className="pills">
                    {history.slice(0, 8).map((h) => (
                      <li
                        key={`${h.at}-${h.emotion}`}
                        className="pill"
                        style={{
                          ["--chip" as string]: moodStyle(h.emotion).color,
                          ["--on-chip" as string]: moodStyle(h.emotion).onColor,
                        }}
                        title={new Date(h.at).toLocaleString()}
                      >
                        {moodStyle(h.emotion).label}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>

            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
          </section>
        )}

        {!result && (
          <section className="about" aria-labelledby="how">
            <h2 id="how" className="section-h">
              How it <span className="accent">works</span>
            </h2>
            <ol className="steps">
              {STEPS.map((s, i) => (
                <li key={s.title}>
                  <span className="step-n" aria-hidden>
                    {i + 1}
                  </span>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                </li>
              ))}
            </ol>

            <h2 className="section-h center">
              7 moods. <span className="accent">Endless vibes.</span>
            </h2>
            <ul className="faces">
              {MOODS.map((m) => (
                <li key={m}>
                  <MoodFace mood={m} size={64} />
                  <span>{MOOD_STYLE[m].label}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>

      <dialog
        ref={historyRef}
        className="history"
        aria-labelledby="history-h"
        onClose={() => setCleared(null)}
        onClick={(e) => {
          // A click on the backdrop (the dialog element itself) closes it.
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
      >
        <div className="history-inner">
          <div className="history-head">
            <h2 id="history-h">Your recent moods</h2>
            <button
              type="button"
              className="glass-btn icon-btn"
              aria-label="Close"
              onClick={() => historyRef.current?.close()}
            >
              <CloseIcon />
            </button>
          </div>
          {history.length === 0 ? (
            cleared ? (
              <p className="hint" role="status">
                History cleared.{" "}
                <button
                  type="button"
                  className="link"
                  ref={undoRef}
                  onClick={undoClear}
                >
                  Undo
                </button>
              </p>
            ) : (
              <p className="hint">
                No moods yet. Record or type how you feel to start your history.
              </p>
            )
          ) : (
            <>
              <ol className="history-grid">
                {history.map((h) => (
                  <li
                    key={`${h.at}-${h.emotion}`}
                    title={new Date(h.at).toLocaleString()}
                  >
                    {isMood(h.emotion) && (
                      <MoodFace mood={h.emotion} size={44} />
                    )}
                    <span className="h-mood">{moodStyle(h.emotion).label}</span>
                    <span className="h-time">{timeAgo(h.at, now)}</span>
                  </li>
                ))}
              </ol>
              <div className="history-foot">
                <span className="hint">Saved only in this browser.</span>
                <button
                  type="button"
                  className="link"
                  onClick={clearHistory}
                  aria-label="Clear mood history"
                >
                  Clear
                </button>
              </div>
            </>
          )}
        </div>
      </dialog>
    </div>
  );
}
