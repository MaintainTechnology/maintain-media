"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

// Mobile booking bar from the landing HTML. It steps aside once the closing CTA
// (same button) is on screen or scrolled past, so it never covers the shared footer.
export function MobileCta({ until }: { until: string }) {
  const [hidden, setHidden] = useState(false);

  // A position check, not IntersectionObserver: an anchor jump from below the
  // CTA to above it never "intersects", so an observer would leave stale state.
  useEffect(() => {
    const target = document.getElementById(until);
    if (!target) return;
    const update = () => setHidden(target.getBoundingClientRect().top < window.innerHeight);
    const frame = requestAnimationFrame(update);
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [until]);

  return (
    <div
      inert={hidden}
      className={`fixed inset-x-0 bottom-0 z-40 flex items-center justify-between gap-3.5 border-t border-brand-300/20 bg-canvas/98 px-4.5 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3 transition-[translate,opacity] duration-300 ease-out-expo motion-reduce:duration-200 md:hidden ${hidden ? "translate-y-full motion-reduce:translate-y-0 motion-reduce:opacity-0" : ""}`}
    >
      <span className="text-[0.8rem] leading-snug max-[380px]:max-w-28">
        <strong className="block text-sm text-ink">Ready for your next step?</strong>
        Let&rsquo;s talk about growth.
      </span>
      <Link href="/contact" className="btn btn-primary px-5 py-2.5 text-sm">
        Book a call
      </Link>
    </div>
  );
}
