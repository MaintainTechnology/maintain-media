"use client";

import { useClerk } from "@clerk/nextjs";
import { useState } from "react";
import styles from "./auth-shell.module.css";

/** Do not mount Clerk's sign-in widget with a server-revoked, locally stale session. */
export function SessionRecovery() {
  const clerk = useClerk();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function restartSignIn() {
    if (pending) return;
    if (!clerk.loaded) { setError("Account controls are still loading. Reload this page if they do not connect."); return; }
    setPending(true);
    setError(null);
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        clerk.signOut(() => { window.location.replace("/sign-in"); }),
        new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new Error("timeout")), 20000); }),
      ]);
    } catch {
      setError("We could not reset your sign-in. Check your connection and try again, or reload this page to refresh your account session.");
      setPending(false);
    } finally { clearTimeout(timeout); }
  }

  return <div className={styles.loading}>
    <p>Your previous session has ended. Clear it from this browser to start a fresh sign-in.</p>
    <button type="button" className={styles.resetButton} disabled={pending} onClick={() => void restartSignIn()}>{pending ? "Resetting sign-in…" : "Start a fresh sign-in"}</button>
    <p role="alert" hidden={!error}>{error}</p>
    <button type="button" onClick={() => window.location.reload()}>Reload account session</button>
  </div>;
}
