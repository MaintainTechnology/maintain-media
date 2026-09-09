import type { Metadata } from "next";
import {
  Clock,
  EnvelopeSimple,
  MapPin,
  Phone,
} from "@phosphor-icons/react/dist/ssr";
import { ContactForm } from "@/components/contact-form";
import { Reveal } from "@/components/reveal";
import { contactDetails } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Book a free strategy call with Maintain Media. Tell us about your brand and goals and we will show you the fastest path to growth.",
};

const contactItems = [
  {
    icon: EnvelopeSimple,
    title: "Email",
    value: contactDetails.email,
    href: `mailto:${contactDetails.email}`,
  },
  {
    icon: Phone,
    title: "Phone",
    value: contactDetails.phone,
    href: contactDetails.phoneHref,
  },
  {
    icon: MapPin,
    title: "Office",
    value: contactDetails.location,
  },
  {
    icon: Clock,
    title: "Hours",
    value: contactDetails.hours,
  },
];

export default function ContactPage() {
  return (
    <>
      <section className="relative overflow-hidden border-b border-line">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-32 -top-40 h-[26rem] w-[26rem] rounded-full bg-brand/15 blur-3xl"
        />
        <div className="shell relative py-20 md:py-24">
          <h1 className="max-w-3xl font-display text-5xl font-extrabold tracking-tight md:text-6xl">
            Let&rsquo;s talk about your growth.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-2 md:text-xl">
            Tell us a little about your brand and where you want to go. We will
            come back within one business day with clear next steps. No
            pressure, no jargon.
          </p>
        </div>
      </section>

      <section className="shell grid gap-12 py-16 md:grid-cols-[0.85fr_1.15fr] md:gap-16 md:py-24">
        <Reveal>
          <h2 className="font-display text-2xl font-bold">
            Prefer to reach out directly?
          </h2>
          <ul className="mt-6">
            {contactItems.map((item) => (
              <li
                key={item.title}
                className="flex items-start gap-5 border-b border-line py-6 last:border-b-0"
              >
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-brand/12">
                  <item.icon size={24} weight="duotone" className="text-brand" />
                </span>
                <div>
                  <h3 className="font-semibold text-ink">{item.title}</h3>
                  {item.href ? (
                    <a
                      href={item.href}
                      className="mt-1 block text-ink-2 transition-colors hover:text-brand-300"
                    >
                      {item.value}
                    </a>
                  ) : (
                    <p className="mt-1 text-ink-2">{item.value}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.1}>
          <ContactForm />
        </Reveal>
      </section>
    </>
  );
}
