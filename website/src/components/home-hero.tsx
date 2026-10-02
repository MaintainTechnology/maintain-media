"use client";

import Image from "next/image";
import Link from "next/link";
import { Check } from "@phosphor-icons/react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";

// Entrance is CSS (animate-rise in globals.css) so it plays from first paint,
// without waiting for hydration. Motion only drives the scroll-linked parallax.
const enter = "motion-safe:animate-rise motion-reduce:animate-fade";

export function HomeHero() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const parallaxY = useTransform(scrollY, [0, 900], [0, 130]);

  return (
    <section
      aria-labelledby="hero-heading"
      className="relative flex min-h-[calc(100dvh-72px)] flex-col justify-center overflow-hidden"
    >
      {/* Atmosphere: purple glow + the brand wireframe mountain landscape */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -right-40 -top-56 h-[34rem] w-[34rem] rounded-full bg-brand/20 blur-3xl" />
        <motion.div
          className="absolute inset-x-0 bottom-0 h-[64%] md:h-[58%]"
          style={{ y: reduce ? 0 : parallaxY }}
        >
          <div className="absolute inset-0 [--delay:150ms] [--rise:60px] motion-safe:animate-[rise_1.4s_var(--ease-out-expo)_var(--delay)_both] motion-reduce:animate-fade">
            <Image
              src="/brand/mountain-forms.webp"
              alt=""
              fill
              loading="eager"
              fetchPriority="high"
              sizes="100vw"
              className="object-cover object-[72%_25%] [mask-image:linear-gradient(to_top,black_55%,transparent)] md:object-top"
            />
          </div>
        </motion.div>
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-canvas to-transparent" />
      </div>

      <div className="shell relative z-10 grid items-center gap-10 pb-40 pt-16 md:grid-cols-[minmax(0,1.6fr)_minmax(14rem,0.7fr)] md:gap-12 md:pb-52 lg:gap-16">
        <div>
          <p
            className={`${enter} mb-6 inline-flex items-center gap-2 rounded-full border border-brand/35 bg-brand/10 px-4 py-2 text-sm font-semibold text-brand-300`}
          >
            {/* Clip-path reveal: the tick confirms "your enquiry is in" once the badge lands. */}
            <Check size={16} weight="bold" aria-hidden className="[--delay:450ms] motion-safe:animate-wipe" />
            Your enquiry is in. Let&rsquo;s build on it.
          </p>
          <h1
            id="hero-heading"
            className={`${enter} max-w-4xl font-display text-[clamp(2.6rem,6.5vw,4.75rem)] font-extrabold leading-[1.04] tracking-tight [--delay:60ms]`}
          >
            You&rsquo;ve made the first move.
            <br />
            <span className="text-brand-300">Now see the potential.</span>
          </h1>

          <p
            className={`${enter} mt-7 max-w-xl text-lg leading-relaxed text-ink-2 [--delay:120ms] md:text-xl`}
          >
            You bring the expertise. We help you find the customers. Explore
            what a consistent flow of qualified leads could mean for your
            business.
          </p>

          <div className={`${enter} mt-10 flex flex-wrap items-center gap-4 [--delay:220ms]`}>
            <Link href="#calculator" className="btn btn-primary">
              Calculate my potential
            </Link>
            <Link href="/contact" className="btn btn-ghost">
              Book a growth call
            </Link>
          </div>
          <p className={`${enter} mt-6 text-sm text-ink-2 [--delay:280ms]`}>
            A clearer picture of your next stage of growth. In about a minute.
          </p>
        </div>

        <aside
          aria-labelledby="guarantee-title"
          className={`${enter} rounded-lg border border-brand-300/40 bg-[linear-gradient(160deg,#3a1f6b_0%,#0c2a30_75%)] p-7 [--delay:300ms]`}
        >
          <p className="mb-5 text-sm font-semibold text-brand-300">
            Our lead generation guarantee
          </p>
          <h2
            id="guarantee-title"
            className="font-display text-2xl font-bold leading-[1.3] tracking-tight md:text-[1.7rem]"
          >
            <span className="sr-only">Get </span>
            <span className="mb-2.5 block text-[clamp(3.8rem,5vw,4.8rem)] leading-[1.08] text-brand-300">
              10–20
            </span>
            extra leads.
            <span className="mt-3 block font-sans text-lg font-medium tracking-normal text-ink-2">
              In your first 30 days.
            </span>
          </h2>
          <p className="mt-6 border-t border-brand-300/25 pt-5 font-display text-[1.6rem] font-bold leading-tight text-ink md:text-[1.7rem]">
            Or it&rsquo;s free.
          </p>
        </aside>
      </div>
    </section>
  );
}
