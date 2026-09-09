// Industries strip. CSS-driven loop, pauses on hover, static under reduced motion.
const industries = [
  "Retail & eCommerce",
  "Professional Services",
  "Hospitality",
  "Health & Wellness",
  "Property",
  "B2B & SaaS",
];

export function IndustriesMarquee() {
  const row = (hidden: boolean) => (
    <ul
      aria-hidden={hidden || undefined}
      className="flex shrink-0 items-center gap-4 pr-4"
    >
      {industries.map((name) => (
        <li
          key={name}
          className="whitespace-nowrap rounded-full border border-line px-5 py-2.5 text-[0.9rem] font-medium text-mist"
        >
          {name}
        </li>
      ))}
    </ul>
  );

  return (
    <div
      className="marquee relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]"
      role="group"
      aria-label="Industries we work across"
    >
      <div className="marquee-track flex w-max">
        {row(false)}
        {row(true)}
      </div>
    </div>
  );
}
