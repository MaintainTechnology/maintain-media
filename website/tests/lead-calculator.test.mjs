import test from "node:test";
import assert from "node:assert/strict";
import { calculateModel, count, money, preciseMoney } from "../src/lib/lead-calculator.ts";

// The landing page's published example: $3,000 spend, $50 CPL, 25%, $1,000, 50% margin.
const example = { spend: 3000, cpl: 50, close: 25, value: 1000, margin: 50, fees: 0 };

test("the worked example reproduces the figures printed in the landing HTML", () => {
  const m = calculateModel(example);
  assert.deepEqual(
    { leads: m.leads, customers: m.customers, revenue: m.revenue, profit: m.profit, roi: m.roi, roas: m.roas, cac: m.cac, breakEven: m.breakEven, maxCpl: m.maxCpl },
    { leads: 60, customers: 15, revenue: 15000, profit: 4500, roi: 150, roas: 5, cac: 200, breakEven: 6, maxCpl: 125 },
  );
});

test("undefined ratios are null, never Infinity or NaN", () => {
  const free = calculateModel({ ...example, spend: 0, fees: 0 });
  assert.deepEqual([free.roi, free.roas, free.cac, free.maxCpl, free.breakEven], [null, null, null, null, 0]);
  assert.equal(calculateModel({ ...example, margin: 0 }).breakEven, null);
});

test("break-even rounds up whole customers without float noise", () => {
  // 0.9 / 0.03 is 30.000000000000004 in IEEE 754; a bare Math.ceil would say 31.
  assert.equal(calculateModel({ spend: 0.9, cpl: 1, close: 100, value: 1, margin: 3, fees: 0 }).breakEven, 30);
  assert.equal(calculateModel({ ...example, fees: 1 }).breakEven, 7);
});

test("formatters match the page's display rules", () => {
  assert.equal(money(15000), "$15,000");
  assert.equal(money(0.5), "$0.50");
  assert.equal(money(-1500), "-$1,500");
  assert.equal(preciseMoney(125), "$125.00");
  assert.equal(count(0.05), "<0.1");
  assert.equal(count(2.25), "2.3");
});
