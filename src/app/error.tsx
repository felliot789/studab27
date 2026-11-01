"use client";
export default function ErrorPage({ reset }: { reset: () => void }) { return <main className="loading-shell"><h1>Your workspace couldn’t open</h1><p>Check that the local vault JSON and Python runtime are available. Your files have been preserved.</p><button onClick={reset} className="button primary">Try again</button></main>; }
