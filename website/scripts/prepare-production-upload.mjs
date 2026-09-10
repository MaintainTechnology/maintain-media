// Local-only upload preparation. This file never runs a provider command.
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash, randomUUID } from "node:crypto";

export const target = Object.freeze({ projectId: "prj_0jiFRBJLqKpgwyClzI4bl1qn1a12",
  orgId: "team_gYhhisBKAi13MDy31JjETCJK", projectName: "website", scope: "maintain-technology", rootDirectory: "website" });
export const deploymentArguments = destination => ["deploy", "--prod", "--project", target.projectId,
  "--scope", target.scope, "--regions", "syd1", "--yes", "--cwd", path.resolve(destination)];
const top = ["package.json", "package-lock.json", "next.config.ts", "next-env.d.ts", "tsconfig.json",
  "postcss.config.mjs", "eslint.config.mjs", "vercel.json"];
const extensions = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".json",
  ".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".otf"]);
const digest = value => createHash("sha256").update(value).digest("hex");
const within = (root, candidate) => candidate === root || candidate.startsWith(root + path.sep);

async function ordinary(filename) {
  const info = await fs.lstat(filename);
  if (info.isSymbolicLink() || await fs.realpath(filename) !== path.resolve(filename)) throw new Error("Linked upload paths are refused");
  if (info.isFile() && info.nlink !== 1) throw new Error("Hard-linked upload files are refused");
  return info;
}

export async function inventory(source) {
  source = path.resolve(source);
  await ordinary(source);
  const selected = [...top];
  async function walk(relative) {
    const directory = path.join(source, relative);
    if (!(await ordinary(directory)).isDirectory()) throw new Error("Expected source directory");
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || /(?:credential|secret|\.env)/i.test(entry.name)) throw new Error("Private-looking upload path refused");
      const name = path.join(relative, entry.name);
      const info = await ordinary(path.join(source, name));
      if (info.isDirectory()) await walk(name);
      else if (info.isFile() && extensions.has(path.extname(name))) selected.push(name);
      else throw new Error("Unexpected source or public asset type");
    }
  }
  await walk("src"); await walk("public");
  const rows = [];
  let total = 0;
  for (const name of selected.sort()) {
    const filename = path.join(source, name), info = await ordinary(filename);
    if (!info.isFile() || info.size > 50 * 1024 * 1024) throw new Error("Upload file type or size invalid");
    total += info.size;
    if (total > 250 * 1024 * 1024) throw new Error("Upload inventory size limit");
    const bytes = await fs.readFile(filename);
    if (bytes.length !== info.size) throw new Error("Source changed during inventory");
    rows.push({ path: "website/" + name.split(path.sep).join("/"), bytes: bytes.length, sha256: digest(bytes) });
  }
  return { schemaVersion: 1, target, source, files: rows, totalBytes: total,
    sourceDigest: digest(JSON.stringify(rows)), excludesEnvironmentFiles: true, providerMutation: false };
}

export async function prepare(source, destination) {
  source = path.resolve(source); destination = path.resolve(destination);
  if (within(source, destination)) throw new Error("Upload staging must be outside the website");
  const manifest = await inventory(source);
  await fs.mkdir(path.dirname(destination), { recursive: true });
  await ordinary(path.dirname(destination));
  await fs.mkdir(destination); // A new directory only; never overwrite an existing release.
  for (const row of manifest.files) {
    const from = path.join(source, row.path.slice("website/".length));
    const to = path.join(destination, row.path);
    await ordinary(from);
    const data = await fs.readFile(from);
    if (data.length !== row.bytes || digest(data) !== row.sha256) throw new Error("Source changed before upload staging");
    await fs.mkdir(path.dirname(to), { recursive: true });
    await fs.writeFile(to, data, { flag: "wx" });
  }
  await fs.mkdir(path.join(destination, ".vercel"));
  await fs.writeFile(path.join(destination, ".vercel/project.json"), JSON.stringify({ projectId: target.projectId,
    orgId: target.orgId, projectName: target.projectName }, null, 2), { flag: "wx" });
  await fs.writeFile(path.join(destination, ".vercelignore"), "*\n!website\n!website/**\nwebsite/.env*\nwebsite/**/.env*\n", { flag: "wx" });
  await fs.writeFile(path.join(destination, "upload-manifest.json"), JSON.stringify(manifest, null, 2), { flag: "wx" });
  await verify(destination);
  return { ...manifest, destination };
}

export async function verify(destination, expectedDigest) {
  destination = path.resolve(destination);
  await ordinary(destination);
  for (const name of ["upload-manifest.json", ".vercel/project.json"]) {
    const info = await ordinary(path.join(destination, name));
    if (!info.isFile() || info.size > 1024 * 1024) throw new Error("Upload metadata invalid");
  }
  const manifest = JSON.parse(await fs.readFile(path.join(destination, "upload-manifest.json"), "utf8"));
  const link = JSON.parse(await fs.readFile(path.join(destination, ".vercel/project.json"), "utf8"));
  if (link.projectId !== target.projectId || link.orgId !== target.orgId || link.projectName !== target.projectName
      || JSON.stringify(manifest.target) !== JSON.stringify(target)) throw new Error("Existing Vercel project binding changed");
  if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.files) || manifest.files.length > 10000
      || manifest.sourceDigest !== digest(JSON.stringify(manifest.files))
      || expectedDigest && manifest.sourceDigest !== expectedDigest) throw new Error("Upload manifest changed");
  const paths = new Set();
  for (const row of manifest.files) {
    const parts = typeof row.path === "string" ? row.path.split("/") : [];
    if (parts[0] !== "website" || parts.some(part => !part || part.startsWith(".") || part.includes("\\")
        || part.includes(":") || /credential|secret/i.test(part)) || paths.has(row.path)
        || !(top.includes(parts.slice(1).join("/")) || ["src", "public"].includes(parts[1]) && extensions.has(path.extname(row.path)))
        || !Number.isSafeInteger(row.bytes) || row.bytes < 0 || row.bytes > 50 * 1024 * 1024
        || !/^[a-f0-9]{64}$/.test(row.sha256)) throw new Error("Unsafe upload inventory row");
    paths.add(row.path);
  }
  const expected = new Set([".vercel/project.json", ".vercelignore", "upload-manifest.json", ...manifest.files.map(row => row.path)]);
  async function walk(relative = "") {
    const directory = path.join(destination, relative);
    await ordinary(directory);
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const name = path.join(relative, entry.name), full = path.join(destination, name);
      const info = await ordinary(full);
      if (info.isDirectory()) await walk(name);
      else if (!expected.delete(name.split(path.sep).join("/"))) throw new Error("Unexpected file in upload staging");
    }
  }
  await walk();
  if (expected.size) throw new Error("Missing upload files");
  for (const row of manifest.files) {
    const data = await fs.readFile(path.join(destination, row.path));
    if (data.length !== row.bytes || digest(data) !== row.sha256) throw new Error("Staged upload changed");
  }
  return { status: "verified", projectId: target.projectId, scope: target.scope,
    fileCount: manifest.files.length, sourceDigest: manifest.sourceDigest, destination,
    deploymentArguments: deploymentArguments(destination), providerMutation: false };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const source = fileURLToPath(new URL("../", import.meta.url));
    let result;
    if (process.argv[2] === "--verify" && [4, 5].includes(process.argv.length)) result = await verify(process.argv[3], process.argv[4]);
    else if (process.argv[2] === "--prepare" && process.argv.length === 3) {
      if (!process.env.LOCALAPPDATA) throw new Error("Local staging directory unavailable");
      const requestedBase = path.join(process.env.LOCALAPPDATA, "MaintainMedia/vercel-releases");
      await fs.mkdir(requestedBase, { recursive: true });
      if ((await fs.lstat(requestedBase)).isSymbolicLink()) throw new Error("Linked release directory refused");
      // Windows packaged apps can redirect LOCALAPPDATA without a symlink.
      // Use the actual directory for every subsequent containment/link check.
      const releaseBase = await fs.realpath(requestedBase);
      await ordinary(releaseBase);
      const destination = path.join(releaseBase, randomUUID());
      result = await prepare(source, destination);
      result = { status: "prepared", destination, projectId: target.projectId, scope: target.scope,
        fileCount: result.files.length, sourceDigest: result.sourceDigest,
        deploymentArguments: deploymentArguments(destination), providerMutation: false };
    } else {
      const current = await inventory(source);
      result = { status: "review_only", projectId: target.projectId, scope: target.scope,
        fileCount: current.files.length, sourceDigest: current.sourceDigest, providerMutation: false };
    }
    console.log(JSON.stringify(result, null, 2));
  } catch {
    console.error("Website upload preparation could not be verified; no provider command was executed.");
    process.exitCode = 1;
  }
}
