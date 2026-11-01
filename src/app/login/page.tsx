"use client";
import { useState } from "react";
import { Icon } from "@/components/ui";

export default function Login() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <main className="login-page"><div className="login-content"><span className="login-brand">StudAb<span>27</span></span><Icon name="shield" size={32} /><h1>A little space for your next chapter.</h1><p>Sign in to your private scholarship workspace.</p><form className="stacked-form" onSubmit={async e => {
    e.preventDefault(); setError(""); setBusy(true);
    const password = new FormData(e.currentTarget).get("password");
    try {
      const response = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not sign in.");
      window.location.assign("/");
    } catch (err) { setError(err instanceof Error ? err.message : "Connection failed. Try again."); setBusy(false); }
  }}><label>Workspace password<input name="password" type="password" autoComplete="current-password" required maxLength={500} autoFocus /></label>{error && <p className="form-error" role="alert">{error}</p>}<button className="button primary" disabled={busy}>{busy ? "Signing in…" : "Open my workspace"}<Icon name="arrow" size={17} /></button></form><p className="fine-print">Hosted on your homelab. Your session stays on this browser.</p></div></main>;
}
