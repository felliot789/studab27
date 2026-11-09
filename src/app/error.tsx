"use client";
import Link from "next/link";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main className="recovery-page"><span className="eyebrow">StudAb27</span><h1>Workspace unavailable</h1><p>The workspace couldn’t load. Existing vault files have been preserved. Try again, or return to Today.</p><button className="button primary" onClick={reset}>Try again</button><Link className="text-button" href="/">Back to Today</Link></main>;
}
