"use client";

import Image from "next/image";
import Link from "next/link";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";

const ease: [number, number, number, number] = [0.16, 1, 0.3, 1];

export function HomeHero() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const parallaxY = useTransform(scrollY, [0, 900], [0, 130]);

  // Keep initial styles identical during server rendering and hydration.
  // Reduced motion changes timing, so content still reaches its visible state.
  const rise = (delay: number) => ({
    initial: { opacity: 0, y: 34 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: reduce ? 0 : 0.9, delay: reduce ? 0 : delay, ease },
  });

  return (
    <section className="relative flex min-h-[calc(100dvh-72px)] flex-col justify-center overflow-hidden">
      {/* Atmosphere: purple glow + the brand wireframe mountain landscape */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -right-40 -top-56 h-[34rem] w-[34rem] rounded-full bg-brand/20 blur-3xl" />
        <motion.div
          className="absolute inset-x-0 bottom-0 h-[64%] md:h-[58%]"
          style={{ y: reduce ? 0 : parallaxY }}
        >
          <motion.div
            className="absolute inset-0"
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduce ? 0 : 1.4, delay: reduce ? 0 : 0.15, ease }}
          >
            <Image
              src="/brand/mountain-forms.webp"
              alt=""
              fill
              priority
              sizes="100vw"
              className="object-cover object-[72%_25%] [mask-image:linear-gradient(to_top,black_55%,transparent)] md:object-top"
            />
          </motion.div>
        </motion.div>
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-canvas to-transparent" />
      </div>

      <div className="shell relative z-10 pb-40 pt-16 md:pb-52">
        <motion.p
          {...rise(0)}
          className="mb-6 inline-flex rounded-full border border-brand/35 bg-brand/10 px-4 py-2 text-sm font-semibold text-brand-300"
        >
          New business. Zero cost to start.
        </motion.p>
        <motion.h1
          {...rise(0.06)}
          className="max-w-4xl font-display text-[clamp(2.6rem,6.5vw,4.75rem)] font-extrabold leading-[1.04] tracking-tight"
        >
          You&rsquo;ve started a business. <span className="text-brand-300">Let&rsquo;s find your customers.</span>
        </motion.h1>

        <motion.p
          {...rise(0.12)}
          className="mt-7 max-w-xl text-lg leading-relaxed text-ink-2 md:text-xl"
        >
          We help newly registered Australian businesses build their customer
          base with qualified leads and zero cost to start. No website, business
          email or social presence yet? That&rsquo;s where we come in.
        </motion.p>

        <motion.div
          {...rise(0.22)}
          className="mt-10 flex flex-wrap items-center gap-4"
        >
          <Link href="/contact" className="btn btn-primary">
            Discuss the partnership
          </Link>
          <Link href="#new-business" className="btn btn-ghost">
            See how it works
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
