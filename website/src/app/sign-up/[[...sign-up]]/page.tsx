import type { Metadata } from "next";
import { AuthEntry } from "@/components/auth/auth-entry";

export const metadata: Metadata = { title: "Sign up", robots: { index: false, follow: false } };

export default function SignUpPage() {
  return <AuthEntry mode="sign-up" />;
}
