// Lead-to-ROI calculator model, ported unchanged from
// docs/v0.01-site-update/maintain-media-landing.html.
// Monthly amounts in AUD, ex GST. Expected values stay unrounded until display.

export type CalculatorInputs = {
  spend: number; // monthly ad spend
  cpl: number; // expected cost per lead
  close: number; // lead-to-customer rate, %
  value: number; // revenue per new customer
  margin: number; // gross profit margin, %
  fees: number; // other monthly marketing costs
};

// Undefined ratios are null and display as "N/A".
export function calculateModel(v: CalculatorInputs) {
  const leads = v.spend / v.cpl;
  const customers = (leads * v.close) / 100;
  const revenue = customers * v.value;
  const grossProfit = (revenue * v.margin) / 100;
  const totalCost = v.spend + v.fees;
  const profit = grossProfit - totalCost;
  const contribution = (v.value * v.margin) / 100;
  return {
    leads,
    customers,
    revenue,
    grossProfit,
    totalCost,
    profit,
    roi: totalCost > 0 ? (profit / totalCost) * 100 : null,
    roas: v.spend > 0 ? revenue / v.spend : null,
    cac: customers > 0 ? totalCost / customers : null,
    // toPrecision(14) drops float noise, so 0.9 / 0.03 ceils to 30, not 31.
    breakEven:
      totalCost === 0
        ? 0
        : contribution > 0
          ? Math.ceil(Number((totalCost / contribution).toPrecision(14)))
          : null,
    maxCpl:
      totalCost > 0 && v.spend > 0 && v.close > 0 && contribution > 0
        ? (v.spend * (v.close / 100) * contribution) / totalCost
        : null,
  };
}

export type CalculatorModel = ReturnType<typeof calculateModel>;

const moneyFormat = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 });
const preciseMoneyFormat = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const countFormat = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 1 });

// Sub-dollar amounts keep their cents instead of collapsing to "$0".
export const money = (n: number) =>
  Math.abs(n) > 0 && Math.abs(n) < 1 ? preciseMoneyFormat.format(n) : moneyFormat.format(n);
export const preciseMoney = (n: number) => preciseMoneyFormat.format(n);
export const count = (n: number) => (n > 0 && n < 0.1 ? "<0.1" : countFormat.format(n));
export const decimal = (n: number) => countFormat.format(n);
