"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import styles from "./sign-in.module.css";

export function SignInForm({ configured }: { configured: boolean }) {
  const router = useRouter();
  const submitting = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current || !configured) return;
    const values = new FormData(event.currentTarget);
    submitting.current = true;
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/abn-lead-gen/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: values.get("username"), password: values.get("password") }),
        signal: AbortSignal.timeout(15000),
      });
      const result: unknown = await response.json();
      if (!response.ok || typeof result !== "object" || result === null || !("ok" in result) || result.ok !== true) {
        const message = typeof result === "object" && result !== null && "message" in result && typeof result.message === "string"
          ? result.message : "Sign-in could not be completed. Please try again.";
        throw new Error(message);
      }
      router.replace("/abn-lead-gen/dashboard");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error && !["TypeError", "TimeoutError", "AbortError", "SyntaxError"].includes(reason.name)
        ? reason.message : "The website could not be reached. Check your connection and try again.");
      submitting.current = false;
      setPending(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={signIn} aria-busy={pending}>
      <div className={styles.field}>
        <label htmlFor="admin-username">Username</label>
        <input id="admin-username" name="username" type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} required maxLength={128} disabled={pending || !configured} />
      </div>
      <div className={styles.field}>
        <label htmlFor="admin-password">Password</label>
        <div className={styles.password}>
          <input id="admin-password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required maxLength={1024} disabled={pending || !configured} />
          <button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-controls="admin-password" aria-pressed={showPassword} disabled={pending || !configured}>
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>
      </div>
      <p className={styles.error} role="alert" aria-atomic="true">{configured ? error : "Admin access is not configured yet. Ask the person managing this website to provision an admin account, then refresh setup."}</p>
      {configured ? <button className={styles.submit} type="submit" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}<span aria-hidden="true">→</span>
      </button> : <button className={styles.submit} type="button" onClick={() => router.refresh()}>Refresh setup<span aria-hidden="true">↻</span></button>}
    </form>
  );
}
