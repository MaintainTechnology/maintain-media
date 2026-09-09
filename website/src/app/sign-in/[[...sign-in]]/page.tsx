import type { Metadata } from "next";
import { AuthEntry } from "@/components/auth/auth-entry";

export const metadata: Metadata = { title: "Sign in", robots: { index: false, follow: false } };

export default function SignInPage() {
  return <AuthEntry mode="sign-in" />;
}
