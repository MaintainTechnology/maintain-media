import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import type { CSSProperties } from "react";
import {
  ArrowRight,
  ChartLineUp,
  CheckCircle,
  Globe,
  Target,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";
import { HomeHero } from "@/components/home-hero";
import { LeadCalculator } from "@/components/lead-calculator";
import { MobileCta } from "@/components/mobile-cta";
import { ScrollReveal } from "@/components/scroll-reveal";
import { contactDetails } from "@/lib/site";

// Content: docs/v0.01-site-update/maintain-media-landing.html.
// Styling: the site's own tokens and components (DESIGN.md), not the HTML's.
// ponytail: the HTML's robots "noindex" is deliberately not carried over; this is the home page.
export const metadata: Metadata = {
  // The layout's "%s | Maintain Media" template skips its own segment, so spell it out.
  title: { absolute: "Your next stage of growth | Maintain Media" },
  description:
    "Thanks for getting in touch with Maintain Media. Explore how qualified leads could become customers with our interactive Lead-to-ROI calculator, then talk through your next steps.",
};

const kicker = "mb-4 text-sm font-semibold text-brand-300";
const heading = "font-display text-4xl font-bold tracking-tight md:text-5xl";
const arrowLink =
  "group inline-flex items-center gap-2 font-semibold text-brand-300 transition-colors hover:text-ink";

const intro = [
  { title: "One connected team", body: "Brand, performance, content and web." },
  { title: "A focus on real customers", body: "From the first enquiry to the work you win." },
];

const principles = [
  { title: "Qualified means something specific.", body: "We agree what a good lead looks like for your services, location and capacity." },
  { title: "Your presence and performance connect.", body: "Campaigns, creative and landing pages work towards the same business goal." },
  { title: "Progress means customers won.", body: "Track enquiries and the work they become, so the next decision is grounded in what happens." },
];

const steps = [
  { title: "Understand the opportunity", body: "Get clear on your offer, service area, ideal customer and capacity. Define the enquiries that are worth pursuing." },
  { title: "Reach the right people", body: "Shape the message and channel around your market, with paid social, search and creative built around your offer." },
  { title: "Make enquiring easy", body: "Connect campaigns to a focused form or landing page. Make the next step clear and route enquiries into your follow-up process." },
  { title: "Learn from the work you win", body: "Track lead quality, customer conversions and acquisition costs. Use that feedback to improve the next round." },
];

// Same Phosphor icon per service as the services page.
const services = [
  { icon: Target, title: ["Brand &", "Creative"], body: "A clear position, recognisable identity and campaign creative that gives people a reason to choose you.", tags: "Positioning · Identity · Campaigns" },
  { icon: ChartLineUp, title: ["Digital &", "Performance"], body: "Paid social, paid search and SEO focused on reaching people who need what your business offers.", tags: "Meta Ads · Google Ads · SEO" },
  { icon: UsersThree, title: ["Content &", "Social"], body: "Useful, consistent content that builds recognition and keeps your business part of the conversation.", tags: "Content · Social · Audience" },
  { icon: Globe, title: ["Web &", "Development"], body: "Fast websites and focused landing pages that make it easy for interested people to take the next step.", tags: "Websites · Landing pages · Conversion" },
];

// Stagger index for [data-reveal] list items (see globals.css).
const order = (i: number) => ({ "--i": i }) as CSSProperties;

const nextSteps = [
  { title: "Talk through your business", body: "Tell us about your services, your market and the kind of customers you want more of." },
  { title: "Check the assumptions together", body: "Discuss your calculator inputs, lead quality, sales process and what a worthwhile return would look like." },
  { title: "Agree on a sensible starting point", body: "Explore the right approach, the scope and the costs before deciding how to move forward." },
];

export default function Home() {
  return (
    <>
      <HomeHero />

      <div className="border-y border-line bg-brand-dark/30">
        <div className="shell grid grid-cols-2 gap-6 py-6 md:grid-cols-[1.2fr_1fr_1fr] md:items-center md:gap-10 md:py-7">
          <div className="col-span-2 md:col-span-1">
            <strong className="block font-display text-lg font-bold text-ink">Maintain Media. Built for momentum.</strong>
            <p className="mt-1 text-sm text-mist">A full-service marketing agency in Brisbane, Australia.</p>
          </div>
          {intro.map((item) => (
            <div key={item.title} className="md:border-l md:border-line md:pl-7">
              <strong className="block text-[0.95rem] font-semibold text-ink">{item.title}</strong>
              <p className="mt-1 text-sm text-mist">{item.body}</p>
            </div>
          ))}
        </div>
      </div>

      <LeadCalculator />

      <section id="about" aria-labelledby="about-title" className="scroll-mt-24 border-t border-line">
        <div className="shell grid items-start gap-9 py-16 md:grid-cols-[1.1fr_1fr] md:gap-12 md:py-24 lg:gap-24">
          <div>
            <p className={kicker}>Meet Maintain Media</p>
            <h2 id="about-title" className={`${heading} max-w-xl`}>
              A marketing partner
              <br />
              <span className="text-brand-300">built for momentum.</span>
            </h2>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-2">
              We bring brand, performance, content and web together to help Australian businesses build their customer base.
            </p>
            <p className="mt-4 max-w-xl text-lg leading-relaxed text-ink-2">
              From establishing your online presence to connecting you with qualified enquiries, the work starts with understanding your business and the customers you can serve.
            </p>
            <Link href="/about" className={`${arrowLink} mt-7`}>
              Get to know Maintain Media
              <ArrowRight size={18} weight="bold" className="transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
          <ul data-reveal className="grid gap-6 pt-2">
            {principles.map((item, i) => (
              <li key={item.title} style={order(i)} className="flex items-start gap-4">
                <CheckCircle size={26} weight="duotone" className="mt-0.5 shrink-0 text-brand" />
                <div>
                  <h3 className="mb-2 text-lg font-bold">{item.title}</h3>
                  <p className="text-mist">{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="how-it-works" aria-labelledby="system-title" className="scroll-mt-24 border-y border-line bg-brand-dark/30">
        <div className="shell py-16 md:py-24">
          <p className={kicker}>The system behind the numbers</p>
          <h2 id="system-title" className={heading}>
            A connected path.
            <br />
            <span className="text-brand-300">From first click to next customer.</span>
          </h2>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-2">
            Good lead generation brings the right message, the right people and the right follow-up together.
          </p>
          <ol
            data-reveal
            style={{ "--stagger": "120ms" } as CSSProperties}
            className="mt-12 grid grid-cols-2 gap-x-6 gap-y-9 max-[380px]:grid-cols-1 lg:grid-cols-4 lg:gap-8"
          >
            {steps.map((step, i) => (
              <li key={step.title} style={order(i)}>
                <span aria-hidden className="block pb-6 font-display text-4xl font-bold leading-none text-brand-300/50">
                  {String(i + 1).padStart(2, "0")}
                </span>
                {/* Connected path: each hairline draws in after the last (globals.css .reveal-line). */}
                <span aria-hidden className="reveal-line mb-6 block h-px bg-brand-300/20" />
                <h3 className="mb-3.5 font-display text-xl font-bold tracking-tight">{step.title}</h3>
                <p className="text-ink-2">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="services-title" className="shell py-16 md:py-24">
        <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between md:gap-12">
          <div>
            <p className={kicker}>The capabilities to make it happen</p>
            <h2 id="services-title" className={heading}>
              One team.
              <br />
              <span className="text-brand-300">The whole picture.</span>
            </h2>
          </div>
          <p className="max-w-sm text-lg leading-relaxed text-ink-2">
            Start with what your business needs now. Build the next layer as you grow.
          </p>
        </div>
        <div
          data-reveal
          style={{ "--stagger": "60ms" } as CSSProperties}
          className="mt-10 grid grid-cols-2 gap-3.5 max-[380px]:grid-cols-1 md:gap-4.5 lg:grid-cols-4"
        >
          {services.map((service, i) => (
            <article
              key={service.tags}
              style={order(i)}
              className={`min-w-0 rounded-lg border border-line px-5 py-6 md:px-6 md:py-7 ${i % 2 ? "bg-surface-2" : "bg-surface"}`}
            >
              <service.icon size={34} weight="duotone" className="mb-7 text-brand" />
              <h3 className="mb-4 font-display text-xl font-bold tracking-tight">
                {service.title[0]}
                <br />
                {service.title[1]}
              </h3>
              <p className="text-[0.95rem] text-ink-2">{service.body}</p>
              <p className="mt-6 border-t border-line pt-4 text-[0.8rem] text-brand-300">{service.tags}</p>
            </article>
          ))}
        </div>
        <p className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-mist">
          Your recommended mix depends on your goals, budget and starting point.
          <Link href="/services" className={arrowLink}>
            Explore our services
            <ArrowRight size={16} weight="bold" className="transition-transform group-hover:translate-x-1" />
          </Link>
        </p>
      </section>

      <section aria-labelledby="next-title" className="shell pb-16 md:pb-24">
        <div className="grid gap-9 border-t border-line pt-13 md:grid-cols-[0.85fr_1.15fr] md:gap-12 md:pt-18 lg:gap-20">
          <div>
            <p className={kicker}>You&rsquo;ve raised your hand. What&rsquo;s next?</p>
            <h2 id="next-title" className={heading}>
              Let&rsquo;s make your
              <br />
              <span className="text-brand-300">next move clear.</span>
            </h2>
            <p className="mt-6 leading-relaxed text-ink-2">
              You&rsquo;ve already introduced your business through our form. A conversation helps connect your goals with a practical starting point.
            </p>
          </div>
          <ol data-reveal>
            {nextSteps.map((step, i) => (
              <li
                key={step.title}
                style={order(i)}
                className="mb-6.5 grid grid-cols-[2.3rem_1fr] gap-4.5 border-b border-line pb-6.5 last:mb-0 last:border-b-0 last:pb-0"
              >
                <span aria-hidden className="grid size-8.5 place-items-center rounded-full border border-brand-300/20 bg-brand/10 text-sm text-brand-300">
                  {i + 1}
                </span>
                <div>
                  <h3 className="mb-2 text-[1.05rem] font-bold">{step.title}</h3>
                  <p className="text-mist">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="book" aria-labelledby="cta-title" className="shell pb-20 md:pb-24">
        <div className="relative isolate overflow-hidden rounded-lg border border-line bg-[linear-gradient(155deg,#3a1f6b_0%,#0c2a30_58%,#061518_100%)] px-7 py-9 md:px-16 md:py-16">
          <div aria-hidden className="pointer-events-none absolute -right-24 -top-32 -z-10 h-96 w-96 rounded-full bg-brand/25 blur-3xl" />
          <Image
            src="/brand/mountain-forms.webp"
            alt=""
            width={1920}
            height={944}
            sizes="(min-width: 1200px) 1060px, 92vw"
            className="pointer-events-none absolute -bottom-[10%] -right-1/4 -z-10 w-[92%] opacity-15"
          />
          <p className={kicker}>Our lead generation guarantee</p>
          <h2 id="cta-title" className="max-w-2xl font-display text-[clamp(2.2rem,4vw,3.6rem)] font-bold leading-[1.12] tracking-tight">
            Get 10–20 extra leads.
            <br />
            <span className="text-brand-300">In your first 30 days.</span>
          </h2>
          <p className="mt-4 font-display text-[1.65rem] font-bold leading-snug text-ink md:text-[1.8rem]">Or it&rsquo;s free.</p>
          <p className="mt-4 max-w-xl text-lg text-ink-2">
            Let&rsquo;s talk about your business and how we can help you turn more enquiries into customers.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link href="/contact" className="btn btn-primary">
              Book a growth call
            </Link>
            <a href={contactDetails.phoneHref} className="btn btn-ghost">
              Call {contactDetails.phone}
            </a>
          </div>
          <p className="mt-5 text-sm text-ink-2">Use our contact page to arrange a conversation, or call us directly.</p>
        </div>
      </section>

      <MobileCta until="book" />
      <ScrollReveal />
    </>
  );
}
