import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./auth-shell.module.css";

export function AuthShell({ eyebrow = "Maintain Media account", title, description, children, note }: {
  eyebrow?: string;
  title: string;
  description: string;
  children: ReactNode;
  note?: string;
}) {
  return <div className={styles.page}>
    <div className={styles.shell}>
      <Link href="/" className={styles.logo} aria-label="Maintain Media home">
        <Image src="/brand/logo-darkbg.svg" alt="Maintain Media" width={180} height={38} style={{ height: "auto" }} priority />
      </Link>
      <div className={styles.layout}>
        <section className={styles.introduction} aria-labelledby="auth-heading">
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 id="auth-heading">{title}</h1>
          <p className={styles.description}>{description}</p>
          <div className={styles.workspaceNote}>
            <span className={styles.mark} aria-hidden="true">M</span>
            <div><strong>One account. Your workspace.</strong><p>Your profile, sign-in and account security, together in one place.</p></div>
          </div>
        </section>
        <section className={styles.formSection} aria-label="Account access">
          {children}
          {note && <p className={styles.note}>{note}</p>}
        </section>
      </div>
      <footer className={styles.footer}><Link href="/">Back to Maintain Media <span aria-hidden="true">↗</span></Link><span>Maintain Media · Brisbane, Australia</span></footer>
    </div>
  </div>;
}
