"use client";

import { useEffect } from "react";

// Progressive scroll reveal for [data-reveal] groups (styles in globals.css).
// Only groups still below the fold get armed (hidden), so server HTML is never
// hidden on screen and nothing is lost without JS. Each group plays once.
export function ScrollReveal() {
  useEffect(() => {
    const groups = [...document.querySelectorAll<HTMLElement>("[data-reveal]")].filter(
      (el) => el.getBoundingClientRect().top > window.innerHeight,
    );
    if (!groups.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          (entry.target as HTMLElement).dataset.reveal = "in";
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.2 },
    );
    for (const group of groups) {
      group.dataset.reveal = "armed";
      observer.observe(group);
    }
    return () => observer.disconnect();
  }, []);

  return null;
}
