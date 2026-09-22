/** Actual cross-origin browser form transport, using two loopback origins only. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../../package.json", import.meta.url));
const { chromium } = require("playwright");
const captures = [];
const receiver = createServer(async (request, response) => {
  let body = "";
  for await (const piece of request) body += piece;
  captures.push({ origin: request.headers.origin, referer: request.headers.referer, method: request.method, body });
  response.writeHead(200, { "Content-Type": "text/plain" });
  response.end("Synthetic form received");
});
await new Promise(resolve => receiver.listen(0, "127.0.0.1", resolve));
const destination = `http://127.0.0.1:${receiver.address().port}/download`;
const sender = createServer((request, response) => {
  const policy = request.url === "/strict-origin" ? "strict-origin" : "no-referrer";
  response.writeHead(200, { "Content-Type": "text/html", "Referrer-Policy": policy });
  response.end(`<!doctype html><form method="post" action="${destination}" target="_blank" rel="noopener"><input type="hidden" name="ticket" value="synthetic-token"><button>Download CSV</button></form>`);
});
await new Promise(resolve => sender.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${sender.address().port}`;
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext();
  await context.route("**/*", route => [origin, new URL(destination).origin].includes(new URL(route.request().url()).origin) ? route.continue() : route.abort());
  const page = await context.newPage();
  const observations = [];
  for (const policy of ["no-referrer", "strict-origin"]) {
    await page.goto(`${origin}/${policy}`);
    const [popup] = await Promise.all([context.waitForEvent("page"), page.getByRole("button", { name: "Download CSV" }).click()]);
    await popup.waitForLoadState();
    const capture = captures.at(-1);
    assert.equal(capture.method, "POST");
    assert.equal(capture.body, "ticket=synthetic-token");
    assert.equal(capture.origin, policy === "no-referrer" ? "null" : origin);
    observations.push({ policy, ...capture });
    await popup.close();
  }
  console.log(JSON.stringify({ status: "passed", test: fileURLToPath(import.meta.url), sender_origin: origin, observations }, null, 2));
} finally {
  await browser.close();
  await Promise.all([new Promise(resolve => sender.close(resolve)), new Promise(resolve => receiver.close(resolve))]);
}
