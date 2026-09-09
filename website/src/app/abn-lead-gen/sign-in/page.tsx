import { redirect } from "next/navigation";

/** Retain old bookmarks while Clerk owns the canonical sign-in route. */
export default function LegacySignInPage() {
  redirect("/sign-in");
}
