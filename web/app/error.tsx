"use client";

import { useEffect } from "react";

// Last-resort screen if rendering throws. Keeps the user one tap from recovery.
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="fallback">
      <h1>Something went off-key.</h1>
      <p>MoodMix hit an unexpected error. Your history in this browser is safe.</p>
      <div className="fallback-actions">
        <button type="button" className="btn-accent" onClick={reset}>
          Try again
        </button>
        <a href="/">Go home</a>
      </div>
    </main>
  );
}
