import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ABN Lead Gen",
  robots: { index: false, follow: false, nocache: true },
};

export default function LeadGenLayout({ children }: { children: React.ReactNode }) {
  return children;
}
