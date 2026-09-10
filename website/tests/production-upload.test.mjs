import test from "node:test";
import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { prepare, verify, target, deploymentArguments } from "../scripts/prepare-production-upload.mjs";

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(tmpdir(), "abn-upload-test-"));
  t.after(async () => {
    const resolved = await fs.realpath(root);
    assert.equal(path.dirname(resolved), await fs.realpath(tmpdir()));
    assert.ok(path.basename(resolved).startsWith("abn-upload-test-"));
    await fs.rm(resolved, { recursive: true, force: true });
  });
  const source = path.join(root, "website"), destination = path.join(root, "release");
  await fs.mkdir(path.join(source, "src"), { recursive: true });
  await fs.mkdir(path.join(source, "public"));
  for (const name of ["package.json", "package-lock.json", "next.config.ts", "next-env.d.ts", "tsconfig.json",
    "postcss.config.mjs", "eslint.config.mjs", "vercel.json"]) await fs.writeFile(path.join(source, name), "synthetic build input");
  await fs.writeFile(path.join(source, "src/page.tsx"), "export default function Page() { return null; }");
  await fs.writeFile(path.join(source, ".env.local"), "SYNTHETIC_SECRET=must-not-upload");
  await fs.mkdir(path.join(source, "scripts"));
  await fs.writeFile(path.join(source, "scripts/operator.ts"), "not a deployment input");
  return { root, source, destination };
}

test("upload contains only app inputs and exact existing-project linkage", async t => {
  const { source, destination } = await fixture(t);
  const result = await prepare(source, destination);
  assert.equal(result.files.length, 9);
  assert.equal(result.providerMutation, false);
  assert.ok(result.files.every(row => row.path.startsWith("website/") && !row.path.includes(".env") && !row.path.includes("scripts/")));
  const link = JSON.parse(await fs.readFile(path.join(destination, ".vercel/project.json"), "utf8"));
  assert.equal(link.projectId, target.projectId); assert.equal(link.orgId, target.orgId);
  assert.equal((await verify(destination, result.sourceDigest)).status, "verified");
  assert.deepEqual(deploymentArguments(destination), ["deploy", "--prod", "--project", target.projectId,
    "--scope", target.scope, "--regions", "syd1", "--yes", "--cwd", destination]);
  await assert.rejects(() => prepare(source, destination), /EEXIST/);
});

test("extra environment files, modified source and project drift fail verification", async t => {
  const { source, destination } = await fixture(t);
  const result = await prepare(source, destination);
  const extra = path.join(destination, "website/.env.local");
  await fs.writeFile(extra, "SYNTHETIC_SECRET=unexpected");
  await assert.rejects(() => verify(destination), /Unexpected file/);
  await fs.unlink(extra);
  const page = path.join(destination, "website/src/page.tsx");
  await fs.appendFile(page, "changed");
  await assert.rejects(() => verify(destination), /Staged upload changed/);
  await fs.writeFile(path.join(destination, ".vercel/project.json"), JSON.stringify({ ...target, projectId: "different" }));
  await assert.rejects(() => verify(destination, result.sourceDigest), /binding changed/);
});

test("path traversal in an altered manifest is rejected before file reads", async t => {
  const { source, destination } = await fixture(t);
  await prepare(source, destination);
  const filename = path.join(destination, "upload-manifest.json");
  const manifest = JSON.parse(await fs.readFile(filename, "utf8"));
  manifest.files[0].path = "website/../../private-key.json";
  manifest.sourceDigest = createHash("sha256").update(JSON.stringify(manifest.files)).digest("hex");
  await fs.writeFile(filename, JSON.stringify(manifest));
  await assert.rejects(() => verify(destination), /Unsafe upload inventory/);
});

test("private-looking files inside selected source trees are never accepted", async t => {
  const { source, destination } = await fixture(t);
  await fs.writeFile(path.join(source, "src/.env"), "SYNTHETIC_SECRET=blocked");
  await assert.rejects(() => prepare(source, destination), /Private-looking upload path/);
  await assert.rejects(() => prepare(source, path.join(source, "nested")), /outside the website/);
});
