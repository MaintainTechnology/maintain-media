import type { Metadata } from "next";
import Image from "next/image";
import {
  ChartLineUp,
  CheckCircle,
  Globe,
  Target,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";
import { CtaBand } from "@/components/cta-band";
import { Reveal } from "@/components/reveal";
import { Mark } from "@/components/mark";

export const metadata: Metadata = {
  title: "Services",
  description:
    "Brand and creative, digital and performance, content and social, web and development. Full-funnel marketing services from Maintain Media in Brisbane.",
};

function Deliverables({ items }: { items: string[] }) {
  return (
    <ul className="mt-8 grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-3">
          <CheckCircle
            size={22}
            weight="duotone"
            className="mt-0.5 shrink-0 text-brand"
          />
          <span className="text-ink-2">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export default function ServicesPage() {
  return (
    <>
      {/* Page hero */}
      <section className="relative overflow-hidden border-b border-line">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-32 -top-40 h-[26rem] w-[26rem] rounded-full bg-brand/15 blur-3xl"
        />
        <div className="shell relative py-20 md:py-28">
          <h1 className="max-w-3xl font-display text-5xl font-extrabold tracking-tight md:text-6xl">
            Full-funnel marketing, delivered by one team.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-2 md:text-xl">
            Four connected capabilities that take you from unknown to
            unmissable. Brand, performance, content and web, all pulling in the
            same direction.
          </p>
        </div>
      </section>

      {/* 1. Brand & Creative */}
      <section id="brand" className="shell scroll-mt-24 py-20 md:py-28">
        <div className="grid items-center gap-14 md:grid-cols-2">
          <Reveal>
            <Target size={36} weight="duotone" className="text-brand" />
            <h2 className="mt-5 font-display text-4xl font-bold tracking-tight md:text-5xl">
              Brands people remember.
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink-2">
              We build brands with a point of view: clear positioning, a
              distinctive identity and campaign creative that cuts through the
              noise. From naming and logos to full brand systems and launch
              campaigns.
            </p>
            <Deliverables
              items={[
                "Brand strategy and positioning",
                "Visual identity and logo design",
                "Messaging and tone of voice",
                "Campaign concepts and creative",
              ]}
            />
          </Reveal>
          <Reveal delay={0.1}>
            <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-line bg-[linear-gradient(165deg,#a04dff_0%,#3a1f6b_48%,#08282d_100%)]">
              <Mark className="absolute bottom-8 left-8 h-24 w-auto text-ink" />
              <div className="absolute right-8 top-8 text-right font-display text-xl font-bold text-ink/90">
                Maintain Media
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* 2. Digital & Performance */}
      <section
        id="performance"
        className="scroll-mt-24 border-y border-line bg-brand-dark/30"
      >
        <div className="shell grid items-center gap-14 py-20 md:grid-cols-2 md:py-28">
          <Reveal className="md:order-2">
            <ChartLineUp size={36} weight="duotone" className="text-brand" />
            <h2 className="mt-5 font-display text-4xl font-bold tracking-tight md:text-5xl">
              Every dollar, accountable.
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink-2">
              Paid search, paid social and SEO built around one thing: return.
              We structure, test and optimise campaigns relentlessly, and
              report on leads, sales and ROAS, not vanity numbers.
            </p>
            <Deliverables
              items={[
                "Google and Meta paid advertising",
                "Search engine optimisation",
                "Conversion rate optimisation",
                "Analytics, tracking and reporting",
              ]}
            />
          </Reveal>
          <Reveal delay={0.1} className="md:order-1">
            <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-lg border border-line bg-surface">
              <div
                aria-hidden
                className="absolute -left-20 -top-24 h-64 w-64 rounded-full bg-brand/15 blur-3xl"
              />
              <div className="relative text-center">
                <div className="font-display text-7xl font-extrabold text-ink md:text-8xl">
                  3.4<span className="text-brand">x</span>
                </div>
                <div className="mt-3 text-lg text-mist">
                  average return on ad spend
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* 3. Content & Social */}
      <section id="content" className="shell scroll-mt-24 py-20 md:py-28">
        <div className="grid gap-12 md:grid-cols-[1.1fr_0.9fr] md:gap-16">
          <Reveal>
            <UsersThree size={36} weight="duotone" className="text-brand" />
            <h2 className="mt-5 font-display text-4xl font-bold tracking-tight md:text-5xl">
              Always on, always relevant.
            </h2>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-2">
              Content and social that build real audiences. We plan, produce
              and publish, from thumb-stopping social to search-driven articles
              and email, keeping your brand top of feed and top of mind.
            </p>
          </Reveal>
          <Reveal delay={0.1} className="self-end">
            <ul className="grid gap-3">
              {[
                "Content strategy and calendars",
                "Social media management",
                "Copywriting and editorial",
                "Email marketing and automation",
              ].map((item) => (
                <li
                  key={item}
                  className="rounded-md border border-line bg-surface px-5 py-4 text-ink-2"
                >
                  {item}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </section>

      {/* 4. Web & Development */}
      <section
        id="web"
        className="scroll-mt-24 border-y border-line bg-brand-dark/30"
      >
        <div className="shell grid items-center gap-14 py-20 md:grid-cols-2 md:py-28">
          <Reveal>
            <Globe size={36} weight="duotone" className="text-brand" />
            <h2 className="mt-5 font-display text-4xl font-bold tracking-tight md:text-5xl">
              Websites that convert.
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink-2">
              Fast, beautiful, conversion-focused websites and landing pages.
              We design and build on modern platforms, wire up your analytics
              and make sure every page earns its place in the funnel.
            </p>
            <Deliverables
              items={[
                "Website design and development",
                "Landing pages and funnels",
                "eCommerce and CMS builds",
                "Speed, SEO and accessibility",
              ]}
            />
          </Reveal>
          <Reveal delay={0.1}>
            <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-line bg-surface-2">
              <Image
                src="/brand/mountain-forms.webp"
                alt=""
                fill
                sizes="(min-width: 768px) 45vw, 90vw"
                className="object-cover opacity-60"
              />
              <div
                aria-hidden
                className="absolute inset-x-8 bottom-8 top-12 rounded-md border border-line bg-canvas/90 p-5 backdrop-blur-sm md:inset-x-10 md:bottom-10 md:top-14"
              >
                <div className="flex items-center justify-between">
                  <div className="flex gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-brand/60" />
                    <span className="h-2.5 w-2.5 rounded-full bg-line" />
                    <span className="h-2.5 w-2.5 rounded-full bg-line" />
                  </div>
                  <div className="flex gap-3 text-[10px] font-medium text-mist">
                    <span>Services</span>
                    <span>About</span>
                    <span>Contact</span>
                  </div>
                </div>
                <div className="mt-6">
                  <Mark className="h-5 w-auto text-brand" />
                  <div className="mt-3 font-display text-lg font-bold leading-snug text-ink md:text-xl">
                    Marketing built to perform.
                  </div>
                  <div className="mt-1.5 text-[11px] text-mist">
                    Brand, performance, content and web. One team.
                  </div>
                  <div className="mt-4 inline-flex rounded-full bg-brand-600 px-4 py-1.5 text-[11px] font-bold text-ink">
                    Start a project
                  </div>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Process recap */}
      <section className="shell py-20 md:py-28">
        <div className="max-w-2xl">
          <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
            One process, four capabilities.
          </h2>
          <p className="mt-5 text-lg text-ink-2">
            Whichever service you start with, you get the same tight,
            transparent way of working.
          </p>
        </div>
        <ol className="mt-14 grid gap-10 md:grid-cols-3">
          {[
            {
              step: "01",
              title: "Discover",
              body: "A free strategy session to map goals, audience and the fastest path to growth.",
            },
            {
              step: "02",
              title: "Build",
              body: "Strategy, creative and campaigns designed and launched fast, with clear ownership.",
            },
            {
              step: "03",
              title: "Grow",
              body: "Weekly optimisation and honest reporting tied to the numbers that matter.",
            },
          ].map((item, i) => (
            <Reveal key={item.step} delay={i * 0.08}>
              <li className="border-t-2 border-brand/50 pt-6">
                <span className="font-display text-sm font-bold text-brand-300">
                  {item.step}
                </span>
                <h3 className="mt-2 font-display text-2xl font-bold">
                  {item.title}
                </h3>
                <p className="mt-3 text-ink-2">{item.body}</p>
              </li>
            </Reveal>
          ))}
        </ol>
      </section>

      <CtaBand
        title="Not sure where to start?"
        body="Tell us your goals and we will recommend the right mix. Book a free strategy call. No pressure, no jargon."
        secondaryHref="/about"
        secondaryLabel="Meet the team"
      />
    </>
  );
}
