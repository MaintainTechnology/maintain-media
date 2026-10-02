"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import {
  calculateModel,
  count,
  decimal,
  money,
  preciseMoney,
  type CalculatorInputs,
  type CalculatorModel,
} from "@/lib/lead-calculator";

type FieldId = keyof CalculatorInputs;

type Field = {
  id: FieldId;
  label: string;
  unit: "$" | "%";
  min: number;
  max: number;
  hint: string;
  slider?: { max: number; step: number; label: string };
};

const basics: Field[] = [
  { id: "spend", label: "Monthly ad spend", unit: "$", min: 0, max: 1_000_000, hint: "Budget paid to advertising platforms.", slider: { max: 20_000, step: 100, label: "Adjust monthly ad spend" } },
  { id: "cpl", label: "Expected cost per lead", unit: "$", min: 0.01, max: 1_000_000, hint: "Ad spend to generate one enquiry. Use your own data if you have it." },
  { id: "close", label: "Lead-to-customer rate", unit: "%", min: 0, max: 100, hint: "25% means 1 in 4 leads becomes a customer.", slider: { max: 100, step: 1, label: "Adjust lead-to-customer rate" } },
  { id: "value", label: "Revenue per new customer", unit: "$", min: 0, max: 10_000_000, hint: "Average first sale or job value, excluding GST. Not lifetime value." },
];

const costs: Field[] = [
  { id: "margin", label: "Gross profit margin", unit: "%", min: 0, max: 100, hint: "After the direct costs of delivering your product or service." },
  { id: "fees", label: "Other monthly marketing costs", unit: "$", min: 0, max: 1_000_000, hint: "Add agency, creative and software costs. $0 is a placeholder, not a quote." },
];

const fields = [...basics, ...costs];

// The page's illustrative example, not pricing or industry benchmarks.
const example: Record<FieldId, string> = { spend: "3000", cpl: "50", close: "25", value: "1000", margin: "50", fees: "0" };
const exampleSliders: Partial<Record<FieldId, number>> = { spend: 3000, close: 25 };

const formulas = [
  ["Leads", "ad spend ÷ cost per lead."],
  ["Customers", "leads × conversion rate."],
  ["Revenue", "customers × first-sale value."],
  ["Gross profit", "revenue × gross margin."],
  ["Return after modelled costs", "gross profit − ad spend − other marketing costs."],
  ["Marketing ROI", "return after modelled costs ÷ total marketing costs × 100."],
  ["Revenue / ad spend (ROAS)", "revenue ÷ ad spend. This is a revenue ratio, not profit."],
  ["*Cost per customer", "(ad spend + other marketing costs) ÷ customers."],
  ["Break-even customers", "total marketing costs ÷ gross profit per customer, rounded up to a whole customer."],
  ["Maximum break-even cost per lead", "ad spend × conversion rate × gross profit per customer ÷ total marketing costs."],
] as const;

// Mirrors the HTML's validity check: required, finite, inside min/max (step="any").
function parse(field: Field, raw: string) {
  const n = raw.trim() === "" ? NaN : Number(raw);
  return Number.isFinite(n) && n >= field.min && n <= field.max ? n : null;
}

const plural = (n: number, word: string) => `${word}${n === 1 ? "" : "s"}`;

function explain(v: CalculatorInputs, m: CalculatorModel): Record<"breakEven" | "conversion" | "headroom", ReactNode> {
  return {
    breakEven:
      m.totalCost === 0
        ? "You have no modelled marketing costs. With no ad spend, this model generates no paid leads. ROI is N/A until costs are above zero."
        : m.breakEven === null
          ? `With zero gross profit per customer, sales cannot cover your ${money(m.totalCost)} monthly marketing costs in this model.`
          : <>You need <strong>{decimal(m.breakEven)} {plural(m.breakEven, "customer")}</strong> to cover {money(m.totalCost)} in monthly marketing costs, before overheads and tax.{v.close === 0 && " Your current 0% conversion rate produces no customers."}</>,
    conversion: <>Your example assumes <strong>{count(m.customers)} {plural(m.customers, "customer")} from {count(m.leads)} leads</strong>. Lead quality, fast responses and consistent follow-up all influence that result.</>,
    headroom:
      m.maxCpl === null
        ? m.totalCost === 0
          ? "Add an ad budget and your costs to explore break-even. Revenue per customer, margin and conversion rate need to be above zero to generate a positive return."
          : "These assumptions do not produce a positive break-even cost per lead. Review your budget, conversion rate, sale value and margin."
        : <>Your break-even cost per lead is <strong>{preciseMoney(m.maxCpl)}</strong>. Your expected {money(v.cpl)} is {Math.abs(v.cpl - m.maxCpl) < 0.005 ? "at" : v.cpl < m.maxCpl ? "below" : "above"} that level. {m.profit < 0 ? "This scenario does not cover your modelled marketing costs." : "That gives you a useful target to check against actual campaign performance."}</>,
  };
}

const kicker = "mb-4 text-sm font-semibold text-brand-300";

export function LeadCalculator() {
  const [values, setValues] = useState(example);
  const [sliders, setSliders] = useState(exampleSliders);
  const [announced, setAnnounced] = useState("");

  const parsed = Object.fromEntries(fields.map((f) => [f.id, parse(f, values[f.id])])) as Record<FieldId, number | null>;
  const firstInvalid = fields.find((f) => parsed[f.id] === null);
  const v = firstInvalid ? null : (parsed as CalculatorInputs);
  const m = v && calculateModel(v);
  const copy = v && m ? explain(v, m) : null;

  const validation = firstInvalid
    ? `${firstInvalid.label}: enter a number from ${firstInvalid.min.toLocaleString("en-AU")} to ${firstInvalid.max.toLocaleString("en-AU")}.`
    : "";
  const live = m
    ? `Estimate updated: ${money(m.revenue)} revenue, ${count(m.leads)} leads, ${count(m.customers)} customers. Return after modelled costs ${money(m.profit)}. Marketing ROI ${m.roi === null ? "not applicable" : `${decimal(m.roi)} percent`}.`
    : `Estimate unavailable. ${validation}`;

  // Debounce valid announcements so screen readers hear the settled result, not every keystroke.
  const valid = m !== null;
  useEffect(() => {
    if (!valid) return;
    const timer = setTimeout(() => setAnnounced(live), 350);
    return () => clearTimeout(timer);
  }, [live, valid]);

  function change(field: Field, raw: string) {
    setValues((prev) => ({ ...prev, [field.id]: raw }));
    const n = Number(raw);
    if (field.slider && raw.trim() !== "" && Number.isFinite(n)) setSliders((prev) => ({ ...prev, [field.id]: n }));
  }

  function reset() {
    setValues(example);
    setSliders(exampleSliders);
  }

  const hint = (f: Field) =>
    f.id !== "close" || parsed.close === null
      ? f.hint
      : parsed.close === 0
        ? "This assumes no leads become customers."
        : `${count(parsed.close)} of every 100 leads become customers.`;

  const dash = "—";
  const metrics = [
    ["Leads generated", m ? count(m.leads) : dash],
    ["New customers", m ? count(m.customers) : dash],
    ["Revenue / ad spend", !m ? dash : m.roas === null ? "N/A" : `${decimal(Math.round(m.roas * 10) / 10)}×`],
    ["Cost per customer*", !m ? dash : m.cac === null ? "N/A" : money(m.cac)],
  ] as const;
  const tone = m && m.profit < 0 ? "text-danger" : "text-brand-300";

  const renderField = (f: Field, tall: boolean) => (
    <div key={f.id} className="min-w-0">
      <label htmlFor={f.id} className="mb-2 block text-sm font-semibold text-ink">
        {f.label}
      </label>
      <div className="flex h-13.5 items-center overflow-hidden rounded-md border border-line bg-canvas/60 transition-colors focus-within:border-brand">
        {f.unit === "$" && <span aria-hidden="true" className="px-3 text-mist">$</span>}
        <input
          id={f.id}
          type="number"
          inputMode="decimal"
          min={f.min}
          max={f.max}
          step="any"
          required
          value={values[f.id]}
          onChange={(e) => change(f, e.target.value)}
          aria-invalid={parsed[f.id] === null}
          aria-describedby={`${f.id}-hint`}
          className={`w-full min-w-0 bg-transparent py-2.5 text-lg font-semibold tabular-nums text-ink outline-none [appearance:textfield] aria-invalid:text-danger [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none ${f.unit === "$" ? "pr-3.5" : "pl-4"}`}
        />
        {f.unit === "%" && <span aria-hidden="true" className="px-3 text-mist">%</span>}
      </div>
      {f.slider && (
        <input
          type="range"
          min={0}
          max={f.slider.max}
          step={f.slider.step}
          value={Math.min(Math.max(sliders[f.id] ?? 0, 0), f.slider.max)}
          onChange={(e) => change(f, e.target.value)}
          aria-label={f.slider.label}
          aria-controls={f.id}
          className="mt-2 block h-6 w-full cursor-pointer accent-brand-300"
        />
      )}
      <p id={`${f.id}-hint`} className={`mt-2 text-[0.8rem] leading-normal text-mist ${tall ? "min-h-9.5 max-[380px]:min-h-0" : ""}`}>
        {hint(f)}
      </p>
    </div>
  );

  return (
    <>
      <section id="calculator" aria-labelledby="calculator-title" className="shell scroll-mt-24 py-16 md:pb-24 md:pt-20">
        <div className="mb-9 flex flex-col gap-5 md:flex-row md:items-end md:justify-between md:gap-12">
          <div>
            <p className={kicker}>Put some numbers behind the opportunity</p>
            <h2 id="calculator-title" className="max-w-2xl font-display text-4xl font-bold tracking-tight md:text-5xl">
              What could more leads
              <br />
              <span className="text-brand-300">mean for your business?</span>
            </h2>
          </div>
          <p className="max-w-sm text-lg leading-relaxed text-ink-2">
            Start with an example. Make it yours. Adjust the numbers to see how leads, sales and costs work together.
          </p>
        </div>

        <noscript>
          <p className="mb-5 rounded-md border border-danger p-4 text-danger">
            Enable JavaScript to use the interactive calculator. The figures shown below are an illustrative example. You can still contact Maintain Media using any booking button.
          </p>
        </noscript>

        <div className="overflow-hidden rounded-lg border border-brand-300/20">
          <div className="flex flex-col gap-1 border-b border-line bg-surface px-6 py-4 min-[381px]:flex-row min-[381px]:items-center min-[381px]:justify-between min-[381px]:gap-4 md:px-7">
            <h3 className="text-base font-semibold">Lead-to-ROI calculator</h3>
            <span className="text-sm text-mist">Monthly estimate · AUD</span>
          </div>

          <div className="grid md:grid-cols-[1.07fr_1fr]">
            <form noValidate onSubmit={(e) => e.preventDefault()} className="bg-brand-dark p-6 md:p-8">
              <div className="mb-6 flex items-center justify-between gap-4">
                <h3 className="font-display text-xl font-bold tracking-tight">Your business. Your numbers.</h3>
                <button
                  type="button"
                  onClick={reset}
                  className="py-2 pl-4 text-sm text-brand-300 underline underline-offset-4 transition-colors hover:text-ink"
                >
                  Reset example
                </button>
              </div>

              <div className="grid grid-cols-2 gap-x-5 gap-y-6 max-[380px]:grid-cols-1">
                {basics.map((f) => renderField(f, true))}
              </div>

              <details open className="disclosure mt-6 border-t border-line pt-4">
                <summary className="min-h-8 cursor-pointer text-sm font-semibold text-brand-300">
                  Refine your return: margin &amp; costs
                </summary>
                <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-6 max-[380px]:grid-cols-1">
                  {costs.map((f) => renderField(f, false))}
                </div>
              </details>

              <p role="status" className="mt-4 text-sm text-danger empty:hidden">
                {validation}
              </p>
              <p className="mt-5 text-xs leading-relaxed text-mist">
                All inputs are examples, not industry benchmarks or a forecast. Your entries stay in this page and are not sent to us.
              </p>
            </form>

            <div
              role="region"
              aria-labelledby="results-title"
              className="relative min-w-0 overflow-hidden border-t border-brand-300/20 bg-surface-2 p-6 md:border-l md:border-t-0 md:p-8"
            >
              <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-brand/15 blur-3xl" />
              <div className="relative">
                <p id="results-title" className="mb-1 text-sm font-semibold text-brand-300">
                  Your potential in a month
                </p>
                <p className="font-display text-[3.5rem] font-bold leading-[1.22] tracking-tight tabular-nums text-ink [overflow-wrap:anywhere] md:text-[clamp(2.6rem,4.5vw,4rem)]">
                  {m ? money(m.revenue) : dash}
                </p>
                <p className="mt-1 text-sm text-ink-2">Estimated new-customer revenue</p>

                <dl className="mt-6 grid grid-cols-2 gap-5 border-y border-brand-300/20 py-5">
                  {metrics.map(([label, value]) => (
                    <div key={label} className="flex flex-col-reverse">
                      <dt className="mt-1.5 text-xs text-mist">{label}</dt>
                      <dd className="font-display text-3xl leading-tight tabular-nums text-ink [overflow-wrap:anywhere]">{value}</dd>
                    </div>
                  ))}
                </dl>

                <div className="mt-6 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-5">
                  <div>
                    <p className={`font-display text-[2rem] leading-tight [overflow-wrap:anywhere] ${tone}`}>{m ? money(m.profit) : dash}</p>
                    <p className="mt-1 text-xs">Return after modelled costs</p>
                  </div>
                  <div className="text-right">
                    <p className={`font-display text-[1.7rem] leading-tight ${tone}`}>
                      {!m ? dash : m.roi === null ? "N/A" : `${decimal(m.roi)}%`}
                    </p>
                    <p className="mt-1 text-xs">Marketing ROI</p>
                  </div>
                </div>

                <p className="mt-4 text-xs leading-relaxed text-ink-2">
                  {v
                    ? `At ${count(v.margin)}% gross margin, less ${money(v.spend)} ad spend and ${money(v.fees)} other marketing costs. Before overheads and tax.`
                    : "Complete the highlighted input to calculate your estimate."}
                </p>

                {/* New tab keeps the visitor's numbers on screen while they book. */}
                <Link href="/contact" target="_blank" rel="noopener" className="btn btn-primary mt-6 w-full">
                  Let&rsquo;s talk through my numbers
                  <span className="sr-only"> (opens contact page in a new tab)</span>
                </Link>
                <p className="mt-3 text-center text-xs text-mist">
                  <span className="font-semibold text-brand-300">Our guarantee:</span> Get 10–20 extra leads in your first 30 days, or it&rsquo;s free.
                </p>
                <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
                  {!m || announced === live ? live : ""}
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-line bg-brand-dark/40 px-6 py-4 text-xs leading-relaxed text-mist md:flex md:gap-4 md:px-7">
            <strong className="mb-1 block font-semibold text-ink-2 md:mb-0 md:whitespace-nowrap">About these calculator estimates.</strong>
            <span>
              The figures above are illustrative, including lead volume, revenue and ROI. They depend on the assumptions you enter and do not set the terms of our lead generation guarantee. This model assumes the resulting sales occur in the same month. Actual returns and timing will vary.
            </span>
          </div>
        </div>

        <details className="disclosure mt-5 text-sm text-mist">
          <summary className="cursor-pointer py-2 text-ink-2">How we calculate your estimate</summary>
          <div className="grid gap-x-7 gap-y-3 py-4 md:grid-cols-2">
            {formulas.map(([term, rule]) => (
              <p key={term}>
                <strong className="font-semibold text-ink">{term}</strong> = {rule}
              </p>
            ))}
          </div>
          <p>
            Monthly figures exclude GST. Sales counts may be fractional expected values and are displayed to one decimal where needed; calculations use unrounded values. Break-even excludes overheads and tax. No repeat sales, lifetime value or organic leads are assumed. Undefined ratios display &ldquo;N/A&rdquo;.
          </p>
        </details>
      </section>

      <section aria-labelledby="meaning-title" className="shell pb-16 md:pb-24">
        <div className="grid gap-8 rounded-lg bg-surface p-7 md:grid-cols-[1fr_1.1fr] md:gap-16 md:p-12">
          <div>
            <p className={kicker}>From numbers to decisions</p>
            <h2 id="meaning-title" className="max-w-sm font-display text-3xl font-bold tracking-tight">
              Revenue is one part
              <br />
              of the picture.
            </h2>
            <p className="mt-5 leading-relaxed text-ink-2">
              The useful question is whether the work you win can cover the cost of winning it, and still leave room for your business to grow.
            </p>
          </div>
          <div className="grid gap-6">
            {([
              ["Know what you need to win", copy?.breakEven],
              ["Give every enquiry a fair chance", copy?.conversion],
              ["Find the room to grow", copy?.headroom],
            ] as const).map(([title, body]) => (
              <div key={title} className="border-l-2 border-brand-300/30 pl-5">
                <h3 className="mb-1.5 text-base font-bold">{title}</h3>
                <p className="text-[0.94rem] text-ink-2 [&_strong]:font-semibold [&_strong]:text-ink">
                  {body ?? "Your explanation will update when all inputs are valid."}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
