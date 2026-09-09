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

  const rise = (delay: number) =>
    reduce
      ? {}
      : {
          initial: { opacity: 0, y: 34 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.9, delay, ease },
        };

  return (
    <section className="relative flex min-h-[calc(100dvh-72px)] flex-col justify-center overflow-hidden">
      {/* Atmosphere: purple glow + the brand wireframe mountain landscape */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -right-40 -top-56 h-[34rem] w-[34rem] rounded-full bg-brand/20 blur-3xl" />
        <motion.div
          className="absolute inset-x-0 bottom-0 h-[64%] md:h-[58%]"
          style={reduce ? undefined : { y: parallaxY }}
        >
          <motion.div
            className="absolute inset-0"
            initial={reduce ? false : { opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1.4, delay: 0.15, ease }}
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
        <motion.h1
          {...rise(0)}
          className="max-w-4xl font-display text-[clamp(2.6rem,6.5vw,4.75rem)] font-extrabold leading-[1.04] tracking-tight"
        >
          The growth team behind Australia&rsquo;s{" "}
          <span className="text-brand-300">boldest brands.</span>
        </motion.h1>

        <motion.p
          {...rise(0.12)}
          className="mt-7 max-w-xl text-lg leading-relaxed text-ink-2 md:text-xl"
        >
          Brand, performance, content and web run as one engine, built in
          Brisbane, measured by the numbers that matter.
        </motion.p>

        <motion.div
          {...rise(0.22)}
          className="mt-10 flex flex-wrap items-center gap-4"
        >
          <Link href="/contact" className="btn btn-primary">
            Start a project
          </Link>
          <Link href="/services" className="btn btn-ghost">
            Explore services
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
