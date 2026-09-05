"use client";

import { useEffect, useRef, useState } from "react";
import { Anton } from "next/font/google";
import { LogoMark } from "./logo";

const anton = Anton({ subsets: ["latin"], weight: "400" });

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Same mood gradients as the Streamlit app (app.py MOOD_COLORS).
const MOOD_GRADIENTS: Record<string, string> = {
  happy: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
  sad: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
  angry: "linear-gradient(135deg, #ff6a88 0%, #ff99ac 100%)",
  calm: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
  fearful: "linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)",
  surprised: "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)",
  disgusted: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
};

const FALLBACK_BG = "#0f0f0f";

// Logo ink per mood — each tuned for contrast against its gradient (and the
// white ghost text behind the mark). Darkest gradients keep white.
const MOOD_INK: Record<string, string> = {
  happy: "#571b3d",
  sad: "#08304f",
  angry: "#5e1224",
  calm: "#05402c",
  fearful: "#3c2350",
  surprised: "#5a2c12",
  disgusted: "#ffffff",
};

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

type PredictResponse = {
  emotion: string;
  confidence: number;
  source: string;
  icon: string;
  description: string;
  query: string;
  tracks: Track[];
};

export default function Home() {
  const [tab, setTab] = useState<"record" | "type">("record");
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [clip, setClip] = useState<Blob | null>(null);
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  // Two-layer crossfade for the hero backdrop (650ms, see .hero-bg-fade CSS).
  const [baseBg, setBaseBg] = useState<string>(FALLBACK_BG);
  const [fadeBg, setFadeBg] = useState<string | null>(null);
  const [fadeOn, setFadeOn] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    return () => {
      if (clipUrl) URL.revokeObjectURL(clipUrl);
    };
  }, [clipUrl]);

  const heroBg = result
    ? (MOOD_GRADIENTS[result.emotion] ?? MOOD_GRADIENTS.disgusted)
    : FALLBACK_BG;

  useEffect(() => {
    if (heroBg === baseBg) return;
    setFadeBg(heroBg);
    setFadeOn(false);
    const raf = requestAnimationFrame(() =>
      requestAnimationFrame(() => setFadeOn(true)),
    );
    const t = setTimeout(() => {
      setBaseBg(heroBg);
      setFadeBg(null);
      setFadeOn(false);
    }, 680);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(t);
    };
  }, [heroBg, baseBg]);

  async function startRecording() {
    setError(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setClip(blob);
        setClipUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((t) => t.stop());
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch {
      setError("Microphone access denied. Allow mic access or use the Type tab.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  async function submitText() {
    if (!text.trim()) {
      setError("Type something first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch(`${API_URL}/predict/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error(`API error (${r.status})`);
      setResult(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed. Is the API running?");
    } finally {
      setLoading(false);
    }
  }

  async function submitSpeech() {
    if (!clip) {
      setError("Record a clip first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", clip, "clip.webm");
      const r = await fetch(`${API_URL}/predict/speech`, { method: "POST", body: form });
      if (!r.ok) {
        const body = await r.json().catch(() => null);
        throw new Error(body?.detail ?? `API error (${r.status})`);
      }
      setResult(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed. Is the API running?");
    } finally {
      setLoading(false);
    }
  }

  const ghostWord = (result?.emotion ?? "MOODMIX").toUpperCase();
  const logoInk = result ? (MOOD_INK[result.emotion] ?? "#ffffff") : "#ffffff";
  const spotifyHref = result
    ? `https://open.spotify.com/search/${encodeURIComponent(result.query || result.emotion)}`
    : null;

  return (
    <>
      <main className="hero">
        <div aria-hidden className="hero-bg" style={{ background: baseBg }} />
        {fadeBg && (
          <div
            aria-hidden
            className="hero-bg hero-bg-fade"
            style={{ background: fadeBg, opacity: fadeOn ? 1 : 0 }}
          />
        )}
        <div aria-hidden className="ghost">
          <span className={anton.className}>{ghostWord}</span>
        </div>
        <div className="hero-inner">
          <div className="hero-nav">
            <div className="hero-logo-wrap" style={{ color: logoInk }}>
              <LogoMark />
            </div>
          </div>
          <div className="hero-body">
            <div className="hero-panel">
              <div className="tabs" role="tablist">
                <button
                  role="tab"
                  aria-selected={tab === "record"}
                  onClick={() => setTab("record")}
                >
                  Record
                </button>
                <button
                  role="tab"
                  aria-selected={tab === "type"}
                  onClick={() => setTab("type")}
                >
                  Type
                </button>
              </div>

              {tab === "record" ? (
                <div className="card">
                  <div className="row">
                    {!recording ? (
                      <button className="secondary" onClick={startRecording}>
                        Start recording
                      </button>
                    ) : (
                      <button className="secondary" onClick={stopRecording}>
                        Stop
                      </button>
                    )}
                    <button
                      className="primary"
                      onClick={submitSpeech}
                      disabled={loading || !clip}
                    >
                      {loading ? "Analyzing…" : "Detect mood"}
                    </button>
                  </div>
                  {recording && (
                    <p className="hint">Recording… speak for a few seconds.</p>
                  )}
                  {clipUrl && !recording && (
                    <div style={{ marginTop: 12 }}>
                      <audio controls src={clipUrl} />
                      <p className="hint">Preview your clip, then hit Detect mood.</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="card">
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="e.g. I'm feeling great today!"
                  />
                  <div className="row">
                    <button className="primary" onClick={submitText} disabled={loading}>
                      {loading ? "Analyzing…" : "Detect mood"}
                    </button>
                  </div>
                </div>
              )}

              {error && <p className="error">{error}</p>}
            </div>
          </div>

          <div className="hero-foot">
            <div className="hero-foot-left">
              <p className="hero-kick">
                {result
                  ? `${result.emotion} · ${(result.confidence * 100).toFixed(0)}%`
                  : "How are you feeling?"}
              </p>
              <p className="hero-lede">
                {result?.description ||
                  "Record your voice or type a line — I'll detect the mood and find Spotify tracks for it."}
              </p>
            </div>
            {spotifyHref && (
              <a
                className={`${anton.className} discover`}
                href={spotifyHref}
                target="_blank"
                rel="noreferrer"
              >
                Discover it
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.25"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M5 12h14" />
                  <path d="m13 6 6 6-6 6" />
                </svg>
              </a>
            )}
          </div>
        </div>

        <div aria-hidden className="grain" />
      </main>
    </>
  );
}
