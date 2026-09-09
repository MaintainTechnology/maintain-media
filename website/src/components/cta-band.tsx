import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import { Reveal } from "@/components/reveal";
import { Mark } from "@/components/mark";

// Closing band shared across pages. Signature brand gradient, one primary CTA.
export function CtaBand({
  title,
  body,
  secondaryHref,
  secondaryLabel,
}: {
  title: ReactNode;
  body: string;
  secondaryHref: Route;
  secondaryLabel: string;
}) {
  return (
    <section className="shell pb-24 pt-8">
      <Reveal>
        <div className="relative overflow-hidden rounded-lg border border-line bg-[linear-gradient(155deg,#3a1f6b_0%,#0c2a30_58%,#061518_100%)] px-8 py-16 md:px-16 md:py-20">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-24 -top-32 h-96 w-96 rounded-full bg-brand/25 blur-3xl"
          />
          <Mark className="pointer-events-none absolute -bottom-10 -right-6 h-44 w-auto text-ink/10" />
          <div className="relative max-w-2xl">
            <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
              {title}
            </h2>
            <p className="mt-5 max-w-xl text-lg text-ink-2">{body}</p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link href="/contact" className="btn btn-primary">
                Start a project
              </Link>
              <Link
                href={secondaryHref}
                className="group inline-flex items-center gap-2 font-semibold text-brand-300 transition-colors hover:text-ink"
              >
                {secondaryLabel}
                <ArrowRight
                  size={18}
                  weight="bold"
                  className="transition-transform group-hover:translate-x-1"
                />
              </Link>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
