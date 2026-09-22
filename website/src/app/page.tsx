import Link from "next/link";
import type { Metadata } from "next";
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
import { IndustriesMarquee } from "@/components/marquee";
import { CtaBand } from "@/components/cta-band";
import { Reveal } from "@/components/reveal";
import { Mark } from "@/components/mark";

export const metadata: Metadata = {
  title: "Lead generation for new businesses",
  description:
    "New ABN and no digital presence yet? Maintain Media helps newly registered Australian businesses find qualified leads through a zero-cost-to-start growth partnership.",
};

const partnershipBenefits = [
  "Zero cost to start your lead generation partnership",
  "Qualified leads matched to the work you do",
  "Support to establish your digital presence",
  "Progress measured by leads becoming customers",
];

export default function Home() {
  return (
    <>
      <HomeHero />

      <section id="new-business" aria-labelledby="new-business-title" className="scroll-mt-24 border-y border-line bg-brand-dark/30">
        <div className="shell grid gap-10 py-16 md:grid-cols-[1.15fr_0.85fr] md:gap-16 md:py-20">
          <div>
            <h2 id="new-business-title" className="max-w-xl font-display text-3xl font-bold tracking-tight md:text-4xl">
              Built for the first days of your business.
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-2">
              Registered your ABN in the last 7 days? Your next priority is
              customers. We focus on early-stage businesses with a limited
              budget and an online presence still to build.
            </p>
            <p className="mt-4 max-w-xl text-lg leading-relaxed text-ink-2">
              We start by understanding your services and checking what you
              need: a website, business email or social channels. Then we work
              with you to reach people who need what you offer.
            </p>
          </div>
          <dl className="grid content-center gap-7">
            <div className="border-b border-line pb-7">
              <dt className="text-base text-ink-2">Our focus</dt>
              <dd className="mt-2">
                <span className="block font-display text-3xl font-bold text-ink">Your first 7 days</span>
                <span className="mt-2 block text-ink-2">A newly registered ABN and room to build your digital presence.</span>
              </dd>
            </div>
            <div>
              <dt className="text-base text-ink-2">The offer</dt>
              <dd className="mt-2">
                <span className="block font-display text-3xl font-bold text-brand-300">Zero cost to start</span>
                <span className="mt-2 block text-ink-2">A lead generation partnership built around growing your customer base.</span>
              </dd>
            </div>
          </dl>
        </div>
      </section>

      {/* Capabilities bento */}
      <section className="shell py-24 md:py-32">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
              Build a presence that helps you grow.
            </h2>
            <p className="mt-5 text-lg text-ink-2">
              As your business develops, our team can support your brand,
              campaigns, content and website. Start with what your business
              needs now and shape the next steps together.
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
              A partnership that grows with you.
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink-2">
              Getting established takes time and resources. Our purpose is to
              help you build customer relationships from the start, with lead
              generation that begins without an upfront investment.
            </p>
            <p className="mt-4 text-lg leading-relaxed text-ink-2">
              We agree what a qualified lead looks like for your business,
              connect you with opportunities and track which leads become
              customers. That gives us a clear foundation for a long-term
              partnership.
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
                {partnershipBenefits.map((line) => (
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

      {/* Audience and industries */}
      <section className="border-y border-line bg-brand-dark/30 py-24 md:py-28">
        <div className="shell">
          <Reveal className="mx-auto max-w-3xl text-center">
            <h2 className="font-display text-3xl font-bold tracking-tight text-ink md:text-4xl">
              You bring the expertise. We help you find the customers.
            </h2>
            <p className="mt-5 text-lg leading-relaxed text-ink-2">
              From local services to new professional practices, the first
              customer relationships matter. Tell us who you serve and where
              you work so we can understand the right opportunities for you.
            </p>
          </Reveal>
          <div className="mt-16">
            <IndustriesMarquee />
          </div>
        </div>
      </section>

      <div className="pt-16">
        <CtaBand
          title="New ABN. Your next step: customers."
          body="Tell us about your new business and the customers you want to reach. Let’s discuss a lead generation partnership with zero cost to start."
          primaryLabel="Discuss the partnership"
          secondaryHref="/services"
          secondaryLabel="Explore services"
        />
      </div>
    </>
  );
}
