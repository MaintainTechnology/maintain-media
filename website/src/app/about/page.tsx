import type { Metadata } from "next";
import Image from "next/image";
import {
  ChartBar,
  ChatCircleText,
  FastForward,
  Sparkle,
} from "@phosphor-icons/react/dist/ssr";
import { CtaBand } from "@/components/cta-band";
import { Reveal } from "@/components/reveal";
import { StatCounter } from "@/components/stat-counter";

export const metadata: Metadata = {
  title: "About",
  description:
    "Maintain Media is a full-service marketing agency built for momentum. Meet the team, our values and the way we work.",
};

const values = [
  {
    icon: FastForward,
    title: "Move fast",
    body: "Momentum beats perfection. We launch, learn and improve while others are still scheduling the kickoff meeting.",
  },
  {
    icon: ChartBar,
    title: "Own the outcome",
    body: "We measure success by your results, not our hours. Every campaign ties back to a real business metric.",
  },
  {
    icon: ChatCircleText,
    title: "Keep it honest",
    body: "Plain-English reporting and straight talk. No vanity metrics, no jargon, no black boxes.",
  },
  {
    icon: Sparkle,
    title: "Stay creative",
    body: "Data tells us what works. Creativity makes it unforgettable. We refuse to choose between the two.",
  },
];

const aboutStats = [
  { value: 120, suffix: "+", label: "Brands grown" },
  { value: 3.4, decimals: 1, suffix: "x", label: "Average return on ad spend" },
  { value: 98, suffix: "%", label: "Client retention" },
  { value: 15, suffix: "+", label: "Years of combined expertise" },
];

export default function AboutPage() {
  return (
    <>
      {/* Page hero */}
      <section className="relative overflow-hidden border-b border-line">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-32 -top-40 h-[26rem] w-[26rem] rounded-full bg-brand/15 blur-3xl"
        />
        <div className="shell relative py-20 md:py-28">
          <h1 className="max-w-3xl font-display text-5xl font-extrabold tracking-tight md:text-6xl">
            A marketing team built for momentum.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-2 md:text-xl">
            We started Maintain Media on a simple belief: marketing should be
            accountable, fast and genuinely creative. No silos, no fluff. Just
            a sharp team obsessed with growing the brands we work with.
          </p>
        </div>
      </section>

      {/* Story */}
      <section className="shell grid items-center gap-14 py-20 md:grid-cols-2 md:py-28">
        <Reveal>
          <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
            Strategy, creative and media under one roof.
          </h2>
          <p className="mt-6 text-lg leading-relaxed text-ink-2">
            Too many brands get bounced between a brand agency, a media agency
            and a web developer who never speak to each other. We built
            Maintain Media to fix that: one team that owns the whole journey
            from first impression to final conversion.
          </p>
          <p className="mt-4 text-lg leading-relaxed text-ink-2">
            The result is marketing that is joined up and fast. Strategy
            informs creative, creative feeds performance, and performance data
            sharpens everything. Fewer handoffs, less waste, better outcomes.
          </p>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-line bg-surface">
            <Image
              src="/brand/mountain-forms.webp"
              alt="The Maintain Media wireframe mountain landscape"
              fill
              sizes="(min-width: 768px) 45vw, 90vw"
              className="object-cover"
            />
          </div>
        </Reveal>
      </section>

      {/* Values */}
      <section className="border-y border-line bg-brand-dark/30">
        <div className="shell py-20 md:py-28">
          <div className="max-w-2xl">
            <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
              The way we work.
            </h2>
            <p className="mt-5 text-lg text-ink-2">
              Four principles that shape every project we take on.
            </p>
          </div>
          <div className="mt-14 grid gap-x-14 gap-y-12 md:grid-cols-2">
            {values.map((value, i) => (
              <Reveal key={value.title} delay={i * 0.06}>
                <div className="flex items-start gap-5 border-t border-line pt-7">
                  <value.icon
                    size={30}
                    weight="duotone"
                    className="mt-1 shrink-0 text-brand"
                  />
                  <div>
                    <h3 className="font-display text-2xl font-bold">
                      {value.title}
                    </h3>
                    <p className="mt-3 leading-relaxed text-ink-2">
                      {value.body}
                    </p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Numbers */}
      <section className="shell py-20 md:py-24">
        <div className="grid gap-12 md:grid-cols-[1fr_1.4fr] md:items-center">
          <div>
            <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
              Results we are proud of.
            </h2>
            <p className="mt-4 max-w-sm text-lg text-ink-2">
              Numbers from the brands we run, not vanity metrics.
            </p>
          </div>
          <div className="grid grid-cols-2">
            {aboutStats.map((stat, i) => (
              <div
                key={stat.label}
                className={`border-line p-6 md:p-8 ${i % 2 === 0 ? "border-r" : ""} ${
                  i < 2 ? "border-b" : ""
                }`}
              >
                <StatCounter {...stat} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <CtaBand
        title={
          <>
            Let&rsquo;s build something
            <br />
            that grows.
          </>
        }
        body="Launching, scaling or rebuilding, we would love to hear what you are working on."
        secondaryHref="/services"
        secondaryLabel="Explore services"
      />
    </>
  );
}
