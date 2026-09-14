"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { List, X } from "@phosphor-icons/react";
import { navLinks } from "@/lib/site";
import { ClerkLoading, Show, UserButton } from "@clerk/nextjs";

const accountLink = "min-h-11 items-center whitespace-nowrap text-sm font-semibold text-ink-2 transition-colors hover:text-brand-300";

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-canvas/85 backdrop-blur-md">
      <div className="shell flex h-[72px] items-center justify-between gap-6">
        <Link href="/" className="shrink-0" aria-label="Maintain Media home">
          <Image
            src="/brand/logo-darkbg.svg"
            alt="Maintain Media"
            width={165}
            height={35}
            priority
            className="h-[30px] w-auto"
          />
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-6 lg:flex">
          {navLinks.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`text-[0.95rem] font-medium transition-colors ${
                  active
                    ? "text-brand-300"
                    : "text-ink-2 hover:text-ink"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <ClerkLoading>
            <div aria-hidden="true" className="hidden items-center gap-4 lg:flex">
              <span className="h-3.5 w-12 rounded-full bg-surface-2" />
              <span className="h-12 w-28 rounded-full bg-surface-2" />
            </div>
          </ClerkLoading>
          <Show when="signed-out">
            <div className="hidden items-center gap-4 lg:flex">
              <Link href="/sign-in" className={`inline-flex ${accountLink}`}>Sign in</Link>
              <Link href="/sign-up" className="btn btn-ghost">Sign up</Link>
            </div>
          </Show>
          <Show when="signed-in">
            <div className="flex items-center gap-4">
              <Link href="/abn-lead-gen/dashboard" className={`hidden lg:inline-flex ${accountLink}`}>Lead workspace</Link>
              <UserButton fallback={<span aria-hidden="true" className="mx-1 block size-9 rounded-full bg-surface-2" />} />
            </div>
          </Show>
          <Link href="/contact" className="btn btn-primary hidden xl:inline-flex">Start a project</Link>
          <button
            type="button"
            className="rounded-md p-2 text-ink lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={26} /> : <List size={26} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.nav
            id="mobile-nav"
            aria-label="Mobile"
            className="overflow-hidden border-t border-line bg-canvas lg:hidden"
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduce ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="shell flex flex-col gap-1 py-4">
              {navLinks.map((link) => {
                const active = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={`rounded-md px-3 py-3 text-lg font-medium ${
                      active ? "text-brand-300" : "text-ink-2 hover:text-ink"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
              <Show when="signed-out"><div className="mt-3 grid grid-cols-2 gap-3 border-t border-line pt-4"><Link href="/sign-in" className="btn btn-ghost">Sign in</Link><Link href="/sign-up" className="btn btn-primary">Sign up</Link></div></Show>
              <Show when="signed-in">
                <div className="mt-3 border-t border-line pt-3">
                  <Link href="/abn-lead-gen/dashboard" className="block rounded-md px-3 py-3 text-lg font-medium text-brand-300">Lead workspace</Link>
                </div>
              </Show>
              <Link
                href="/contact"
                className="btn btn-primary mt-3 w-full"
              >
                Start a project
              </Link>
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
