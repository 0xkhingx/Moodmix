export default function NotFound() {
  return (
    <main className="fallback">
      <h1>This page isn&apos;t in the mix.</h1>
      <p>The link may be old or mistyped.</p>
      <div className="fallback-actions">
        <a className="btn-accent" href="/">
          Back to MoodMix
        </a>
      </div>
    </main>
  );
}
