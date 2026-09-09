"use client";

import { usePathname } from "next/navigation";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { SmoothScroll } from "@/components/smooth-scroll";

/** The operator workspace has its own navigation and native browser scrolling. */
export function SiteShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const workspace = pathname === "/abn-lead-gen" || pathname.startsWith("/abn-lead-gen/");
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-ink focus:px-5 focus:py-2.5 focus:font-bold focus:text-brand-dark"
        onClick={(event) => {
          if (workspace) {
            event.preventDefault();
            document.getElementById("main")?.focus();
          }
        }}>
        Skip to content
      </a>
      {!workspace && <><SmoothScroll /><Header key={pathname} /></>}
      <main id="main" tabIndex={-1} className="flex-1">{children}</main>
      {!workspace && <Footer />}
    </>
  );
}
