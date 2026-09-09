import Link from "next/link";
import Image from "next/image";
import { contactDetails, navLinks, serviceLinks } from "@/lib/site";

export function Footer() {
  return (
    <footer className="border-t border-line bg-brand-dark/40">
      <div className="shell">
        <div className="grid gap-12 py-16 md:grid-cols-[1.5fr_1fr_1fr_1.2fr]">
          <div>
            <Image
              src="/brand/logo-darkbg.svg"
              alt="Maintain Media"
              width={176}
              height={37}
              className="h-8 w-auto"
            />
            <p className="mt-5 max-w-xs text-[0.95rem] leading-relaxed text-mist">
              A full-service marketing agency built for momentum. Brand,
              performance, content and web under one roof.
            </p>
          </div>

          <nav aria-label="Services">
            <h2 className="text-sm font-semibold tracking-wide text-ink">
              Services
            </h2>
            <ul className="mt-5 space-y-3 text-[0.95rem]">
              {serviceLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-mist transition-colors hover:text-brand-300"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Company">
            <h2 className="text-sm font-semibold tracking-wide text-ink">
              Company
            </h2>
            <ul className="mt-5 space-y-3 text-[0.95rem]">
              {navLinks
                .filter((link) => link.href !== "/")
                .map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-mist transition-colors hover:text-brand-300"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
            </ul>
          </nav>

          <div>
            <h2 className="text-sm font-semibold tracking-wide text-ink">
              Get in touch
            </h2>
            <ul className="mt-5 space-y-3 text-[0.95rem]">
              <li>
                <a
                  href={`mailto:${contactDetails.email}`}
                  className="text-mist transition-colors hover:text-brand-300"
                >
                  {contactDetails.email}
                </a>
              </li>
              <li>
                <a
                  href={contactDetails.phoneHref}
                  className="text-mist transition-colors hover:text-brand-300"
                >
                  {contactDetails.phone}
                </a>
              </li>
              <li className="text-mist">{contactDetails.location}</li>
            </ul>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line py-7 text-sm text-mist">
          <span>&copy; 2026 Maintain Media. All rights reserved.</span>
          <span>Built on the Maintain Media design system.</span>
        </div>
      </div>
    </footer>
  );
}
