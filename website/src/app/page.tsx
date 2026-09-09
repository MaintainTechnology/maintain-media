import Link from "next/link";
import {
  ArrowRight,
  ChartLineUp,
  CheckCircle,
  Globe,
  Target,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";
import { HomeHero } from "@/components/home-hero";
import { ProcessStack } from "@/components/process-stack";
import { StatCounter } from "@/components/stat-counter";
import { IndustriesMarquee } from "@/components/marquee";
import { CtaBand } from "@/components/cta-band";
import { Reveal } from "@/components/reveal";
import { Mark } from "@/components/mark";

const stats = [
  { value: 120, suffix: "+", label: "Brands grown" },
  { value: 3.4, decimals: 1, suffix: "x", label: "Average return on ad spend" },
  { value: 48, suffix: "hr", label: "Campaign turnaround" },
  { value: 15, suffix: "+", label: "Years of combined expertise" },
];

const oneRoof = [
  "One strategy across every channel",
  "Creative sharpened by performance data",
  "No handoffs between three different agencies",
  "Reporting in plain numbers, tied to revenue",
];

export default function Home() {
  return (
    <>
      <HomeHero />

      {/* Proof strip */}
      <section aria-label="Results at a glance" className="border-y border-line">
        <div className="shell grid grid-cols-2 gap-y-10 py-14 md:grid-cols-4">
          {stats.map((stat) => (
            <StatCounter key={stat.label} {...stat} />
          ))}
        </div>
      </section>

      {/* Capabilities bento */}
      <section className="shell py-24 md:py-32">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
              Full-funnel marketing, one team.
            </h2>
            <p className="mt-5 text-lg text-ink-2">
              Everything you need to build a brand, fill the funnel and
              convert, delivered by specialists who actually talk to each
              other.
            </p>
          </div>
          <Link
            href="/services"
            className="group inline-flex items-center gap-2 font-semibold text-brand-300 transition-colors hover:text-ink"
          >
            Explore services
            <ArrowRight
              size={18}
              weight="bold"
              className="transition-transform group-hover:translate-x-1"
            />
          </Link>
        </div>

        <div className="mt-14 grid gap-5 md:grid-cols-6">
          <Reveal className="md:col-span-4">
            <Link
              href="/services#brand"
              className="group relative flex h-full min-h-[17rem] flex-col justify-end overflow-hidden rounded-lg border border-line bg-surface p-8 transition-colors hover:border-brand/50"
            >
              <Mark className="absolute -right-8 -top-12 h-56 w-auto text-brand/10 transition-transform duration-500 group-hover:scale-105" />
              <Target size={34} weight="duotone" className="text-brand" />
              <h3 className="mt-4 font-display text-2xl font-bold">
                Brand &amp; Creative
              </h3>
              <p className="mt-2 max-w-md text-ink-2">
                Positioning, identity and campaign creative that make you
                impossible to ignore and instantly recognisable.
              </p>
            </Link>
          </Reveal>

          <Reveal delay={0.08} className="md:col-span-2">
            <Link
              href="/services#performance"
              className="group relative flex h-full min-h-[17rem] flex-col justify-end overflow-hidden rounded-lg border border-line bg-[linear-gradient(160deg,#3a1f6b_0%,#0c2a30_75%)] p-8 transition-colors hover:border-brand/50"
            >
              <ChartLineUp size={34} weight="duotone" className="text-brand-300" />
              <h3 className="mt-4 font-display text-2xl font-bold">
                Digital &amp; Performance
              </h3>
              <p className="mt-2 text-ink-2">
                SEO, paid search and paid social engineered around return.
              </p>
            </Link>
          </Reveal>

          <Reveal delay={0.12} className="md:col-span-2">
            <Link
              href="/services#content"
              className="group relative flex h-full min-h-[15rem] flex-col justify-end overflow-hidden rounded-lg border border-line bg-surface p-8 transition-colors hover:border-brand/50"
            >
              <UsersThree size={34} weight="duotone" className="text-brand" />
              <h3 className="mt-4 font-display text-2xl font-bold">
                Content &amp; Social
              </h3>
              <p className="mt-2 text-ink-2">
                Always-on content that builds audiences and keeps you top of
                feed.
              </p>
            </Link>
          </Reveal>

          <Reveal delay={0.16} className="md:col-span-4">
            <Link
              href="/services#web"
              className="group relative flex h-full min-h-[15rem] flex-col justify-end overflow-hidden rounded-lg border border-line bg-surface-2 p-8 transition-colors hover:border-brand/50"
            >
              <div
                aria-hidden
                className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-brand/15 blur-3xl"
              />
              <Globe size={34} weight="duotone" className="text-brand" />
              <h3 className="mt-4 font-display text-2xl font-bold">
                Web &amp; Development
              </h3>
              <p className="mt-2 max-w-md text-ink-2">
                Fast, beautiful websites and landing pages built to turn
                traffic into revenue.
              </p>
            </Link>
          </Reveal>
        </div>
      </section>

      {/* Difference */}
      <section className="border-y border-line bg-brand-dark/30">
        <div className="shell grid items-center gap-14 py-24 md:grid-cols-2 md:py-32">
          <Reveal>
            <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
              Not your typical marketing agency.
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink-2">
              Most agencies sell you activity. We are obsessed with outcomes.
              Every campaign ties back to the metrics that actually build your
              business.
            </p>
            <p className="mt-4 text-lg leading-relaxed text-ink-2">
              Strategy, creative, media and web live under one roof, so nothing
              gets lost in handoffs and everything pulls in the same direction.
              Fewer meetings, sharper work, faster results.
            </p>
            <Link
              href="/about"
              className="group mt-8 inline-flex items-center gap-2 font-semibold text-brand-300 transition-colors hover:text-ink"
            >
              Why Maintain Media
              <ArrowRight
                size={18}
                weight="bold"
                className="transition-transform group-hover:translate-x-1"
              />
            </Link>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="relative overflow-hidden rounded-lg border border-line bg-surface p-8 md:p-10">
              <div
                aria-hidden
                className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-brand/15 blur-3xl"
              />
              <ul className="relative space-y-6">
                {oneRoof.map((line) => (
                  <li key={line} className="flex items-start gap-4">
                    <CheckCircle
                      size={26}
                      weight="duotone"
                      className="mt-0.5 shrink-0 text-brand"
                    />
                    <span className="text-lg text-ink">{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </section>

      <ProcessStack />

      {/* Quote + industries */}
      <section className="border-y border-line bg-brand-dark/30 py-24 md:py-28">
        <div className="shell">
          <Reveal className="mx-auto max-w-3xl text-center">
            <div
              aria-hidden
              className="font-display text-6xl font-extrabold leading-none text-brand"
            >
              &ldquo;
            </div>
            <blockquote className="mt-2 text-2xl font-medium leading-snug text-ink md:text-3xl">
              Maintain Media rebuilt our funnel from the ground up and tripled
              our qualified leads in a single quarter. The reporting is
              refreshingly honest.
            </blockquote>
            <cite className="mt-6 block text-[0.95rem] not-italic text-mist">
              Marketing Director, national retail brand
            </cite>
          </Reveal>
          <div className="mt-16">
            <IndustriesMarquee />
          </div>
        </div>
      </section>

      <div className="pt-16">
        <CtaBand
          title="Ready to grow faster?"
          body="Book a free strategy call. We will show you exactly where the opportunities are and what it takes to capture them."
          secondaryHref="/services"
          secondaryLabel="Explore services"
        />
      </div>
    </>
  );
}
