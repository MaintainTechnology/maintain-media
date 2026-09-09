"use client";

import { ClerkFailed, SignIn, SignUp } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import styles from "./auth-shell.module.css";

function AuthLoading() {
  const [slow, setSlow] = useState(false);
  useEffect(() => { const timer = setTimeout(() => setSlow(true), 12000); return () => clearTimeout(timer); }, []);
  return <div className={styles.loading} role="status"><p>{slow ? "Sign-in is taking longer than expected. Check your connection, then try loading this page again." : "Loading your account’s secure sign-in…"}</p>{slow && <button type="button" onClick={() => window.location.reload()}>Reload sign-in</button>}</div>;
}

export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  return <>
    <ClerkFailed><div className={styles.loading} role="alert"><p>Account access is temporarily unavailable. Check your connection and reload to try again.</p><button type="button" onClick={() => window.location.reload()}>Try again</button></div></ClerkFailed>
    {mode === "sign-in"
      ? <SignIn path="/sign-in" routing="path" signUpUrl="/sign-up" forceRedirectUrl="/abn-lead-gen/dashboard" signUpForceRedirectUrl="/abn-lead-gen/dashboard" fallback={<AuthLoading />} />
      : <SignUp path="/sign-up" routing="path" signInUrl="/sign-in" forceRedirectUrl="/abn-lead-gen/dashboard" signInForceRedirectUrl="/abn-lead-gen/dashboard" fallback={<AuthLoading />} />}
  </>;
}
