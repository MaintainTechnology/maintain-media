import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { adminAccessConfigured, getAdminSession } from "@/lib/abn-lead-gen/auth";
import { SignInForm } from "./sign-in-form";
import styles from "./sign-in.module.css";

export const metadata: Metadata = {
  title: "Admin sign-in | ABN Lead Gen",
  robots: { index: false, follow: false },
};

export default async function SignInPage() {
  if (await getAdminSession()) redirect("/abn-lead-gen/dashboard");
  const configured = await adminAccessConfigured();
  return (
    <div className={styles.page}>
      <section className={styles.panel} aria-labelledby="sign-in-heading">
        <Link href="/" className={styles.logo} aria-label="Maintain Media home">
          <Image src="/brand/logo-darkbg.svg" alt="Maintain Media" width={180} height={38} style={{ height: "auto" }} priority />
        </Link>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>ABN Lead Gen</p>
          <h1 id="sign-in-heading">Your lead workspace.</h1>
          <p>Sign in with your admin account to review businesses, run the engine and manage your settings.</p>
        </div>
        <SignInForm configured={configured} />
        <p className={styles.note}>Access is limited to provisioned Maintain Media admins. Ask the person managing this website if you need an account.</p>
        <Link href="/" className={styles.back}>Back to Maintain Media <span aria-hidden="true">↗</span></Link>
      </section>
    </div>
  );
}
