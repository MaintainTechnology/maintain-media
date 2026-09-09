"use client";

import { useEffect, useRef } from "react";
import { animate, useInView, useReducedMotion } from "motion/react";

// Counts up once when scrolled into view. Static under reduced motion.
export function StatCounter({
  value,
  decimals = 0,
  suffix,
  label,
}: {
  value: number;
  decimals?: number;
  suffix: string;
  label: string;
}) {
  const numberRef = useRef<HTMLSpanElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const inView = useInView(rootRef, { once: true, amount: 0.6 });
  const reduce = useReducedMotion();

  useEffect(() => {
    const el = numberRef.current;
    if (!el || !inView) return;
    if (reduce) {
      el.textContent = value.toFixed(decimals);
      return;
    }
    const controls = animate(0, value, {
      duration: 1.4,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        el.textContent = v.toFixed(decimals);
      },
    });
    return () => controls.stop();
  }, [inView, reduce, value, decimals]);

  return (
    <div ref={rootRef}>
      <div className="font-display text-4xl font-extrabold tracking-tight text-ink md:text-5xl">
        <span ref={numberRef}>{reduce ? value.toFixed(decimals) : "0"}</span>
        <span className="text-brand">{suffix}</span>
      </div>
      <div className="mt-2 text-[0.95rem] text-mist">{label}</div>
    </div>
  );
}
