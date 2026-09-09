import Link from "next/link";
import { Mark } from "@/components/mark";

export default function NotFound() {
  return (
    <section className="relative flex min-h-[70dvh] flex-col items-center justify-center overflow-hidden text-center">
      <Mark className="pointer-events-none absolute -bottom-16 left-1/2 h-64 w-auto -translate-x-1/2 text-brand/10" />
      <p className="font-display text-7xl font-extrabold text-brand">404</p>
      <h1 className="mt-4 font-display text-3xl font-bold md:text-4xl">
        This page does not exist.
      </h1>
      <p className="mt-4 max-w-md text-ink-2">
        The page you are after has moved or never existed. Head back home and
        take it from the top.
      </p>
      <Link href="/" className="btn btn-primary mt-8">
        Back to home
      </Link>
    </section>
  );
}
