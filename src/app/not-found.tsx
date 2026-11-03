import Link from "next/link";
export default function NotFound() {
  return <main className="recovery-page"><span className="eyebrow">StudAb27</span><h1>Page not found</h1><p>The requested page does not exist. Check the link or return to your workspace.</p><Link className="button primary" href="/scholarships">Find a scholarship</Link><Link className="text-button" href="/">Back to Today</Link></main>;
}
