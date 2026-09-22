"use client";

import { useLayoutEffect, useRef } from "react";
import Image from "next/image";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Mark } from "@/components/mark";

gsap.registerPlugin(ScrollTrigger);

const steps = [
  {
    numeral: "01",
    title: "Understand your starting point",
    body: "We learn about your new business, the work you do and the customers you want to reach.",
    points: [
      "Your services and local area",
      "Website, business email and social presence",
      "The customers you can serve now",
    ],
  },
  {
    numeral: "02",
    title: "Connect with qualified leads",
    body: "Together, we agree what makes a good lead and how to get those opportunities to you, with zero cost to start.",
    points: [
      "A clear definition of a qualified lead",
      "A way to receive and follow up enquiries",
      "Support for the gaps in your digital presence",
    ],
  },
  {
    numeral: "03",
    title: "Build customer relationships",
    body: "Follow up the opportunities, win customers and learn what works. We grow the partnership around those results.",
    points: [
      "Leads followed up and customers won",
      "Feedback that improves lead quality",
      "Long-term support as your business grows",
    ],
  },
] as const;

// Signature scroll moment: sticky-stacked process cards. CSS sticky does the
// stacking; GSAP scrubs a scale/fade on each card as the next one covers it.
export function ProcessStack() {
  const rootRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const ctx = gsap.context(() => {
      const cards = gsap.utils.toArray<HTMLElement>(".process-card");
      cards.forEach((card, i) => {
        const next = cards[i + 1];
        if (!next) return;
        gsap.to(card.querySelector(".process-inner"), {
          scale: 0.94,
          opacity: 0.45,
          ease: "none",
          scrollTrigger: {
            trigger: next,
            start: "top bottom",
            end: "top top+=96",
            scrub: true,
          },
        });
      });
    }, rootRef);

    return () => ctx.revert();
  }, []);

  return (
    <section className="shell py-24 md:py-32">
      <div className="max-w-2xl">
        <h2 className="font-display text-4xl font-bold tracking-tight md:text-5xl">
          From a new ABN to your next customer.
        </h2>
        <p className="mt-5 text-lg text-ink-2">
          A clear starting point, useful opportunities and a shared focus on
          turning leads into lasting customer relationships.
        </p>
      </div>

      <div ref={rootRef} className="mt-16">
        {steps.map((step, i) => (
          <div key={step.title} className="process-card sticky top-[96px] pb-10">
            <article
              className={`process-inner relative grid min-h-[26rem] origin-top overflow-hidden rounded-lg border border-line md:grid-cols-2 ${
                i === 0
                  ? "bg-surface"
                  : i === 1
                    ? "bg-[linear-gradient(150deg,#3a1f6b_0%,#0c2a30_70%)]"
                    : "bg-surface-2"
              }`}
            >
              <div className="relative z-10 flex flex-col justify-center p-8 md:p-14">
                <span
                  aria-hidden
                  className="font-display text-6xl font-extrabold text-brand/30"
                >
                  {step.numeral}
                </span>
                <h3 className="mt-3 font-display text-3xl font-bold md:text-4xl">
                  {step.title}
                </h3>
                <p className="mt-4 max-w-md text-lg text-ink-2">{step.body}</p>
                <ul className="mt-7 space-y-3">
                  {step.points.map((point) => (
                    <li key={point} className="flex items-center gap-3 text-ink-2">
                      <span
                        aria-hidden
                        className="h-1.5 w-1.5 rounded-full bg-brand"
                      />
                      {point}
                    </li>
                  ))}
                </ul>
              </div>

              <div aria-hidden className="relative hidden md:block">
                {i === 0 && (
                  <Image
                    src="/brand/mountain-forms.webp"
                    alt=""
                    fill
                    sizes="(min-width: 768px) 40vw, 0px"
                    className="object-cover opacity-80 [mask-image:linear-gradient(to_right,transparent,black_35%)]"
                  />
                )}
                {i === 1 && (
                  <Mark className="absolute -bottom-16 -right-10 h-72 w-auto text-ink/10" />
                )}
                {i === 2 && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <div className="font-display text-5xl font-extrabold text-ink">
                        Leads<span className="block text-brand-300">to customers.</span>
                      </div>
                      <div className="mt-2 text-mist">
                        The progress that matters
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </article>
          </div>
        ))}
      </div>
    </section>
  );
}
