import { randomBytes, scrypt } from "node:crypto";
import { mkdir, open, readFile, rename, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const website = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const local = path.join(website, ".local");
const configPath = path.join(local, "admin-auth.json");
const accessPath = path.join(local, "admin-access.txt");

function argumentsOf(values) {
  const command = values[0] && !values[0].startsWith("--") ? values.shift() : "create";
  if (!["create", "reset", "disable", "enable", "list"].includes(command)) {
    throw new Error("Use create, reset, disable, enable, or list.");
  }
  const options = {};
  while (values.length) {
    const key = values.shift();
    const value = values.shift();
    if (!["--username", "--name"].includes(key) || !value || value.startsWith("--") || options[key]) {
      throw new Error("Usage: node scripts/admin-account.mjs create --username admin --name \"Maintain Media Admin\"");
    }
    options[key] = value;
  }
  const username = (options["--username"] ?? "admin").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9_.@-]{2,127}$/.test(username)) throw new Error("Username must contain 3–128 letters, digits, dots, @, underscores or hyphens.");
  const displayName = (options["--name"] ?? username).trim();
  if (!displayName || displayName.length > 100) throw new Error("Display name must contain 1–100 characters.");
  return { command, username, displayName };
}

async function passwordHash(password) {
  const salt = randomBytes(16);
  const hash = await new Promise((resolve, reject) => {
    scrypt(password, salt, 64, { N: 32768, r: 8, p: 3, maxmem: 64 * 1024 * 1024 }, (error, key) => {
      if (error) reject(error);
      else resolve(key);
    });
  });
  return `scrypt$32768$8$3$${salt.toString("hex")}$${hash.toString("hex")}`;
}

async function saveJson(filename, value) {
  const temp = `${filename}.${randomBytes(6).toString("hex")}.tmp`;
  try {
    await writeFile(temp, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600, flag: "wx" });
    await rename(temp, filename);
  } finally {
    await unlink(temp).catch((error) => { if (error.code !== "ENOENT") throw error; });
  }
}

async function main() {
  if (process.env.ABN_ADMIN_ACCOUNTS_JSON !== undefined || process.env.ABN_ADMIN_SESSION_SECRET !== undefined) {
    throw new Error("This server uses environment-managed accounts. Update that registry instead of creating a local account.");
  }
  const { command, username, displayName } = argumentsOf(process.argv.slice(2));
  await mkdir(local, { recursive: true, mode: 0o700 });
  const lockPath = path.join(local, "admin-auth.lock");
  const lock = await open(lockPath, "wx", 0o600).catch(() => {
    throw new Error("Another account update is running. Retry after it finishes.");
  });
  try {
    let config;
    try {
      config = JSON.parse(await readFile(configPath, "utf8"));
      if (typeof config.sessionSecret !== "string" || config.sessionSecret.length < 32 || !Array.isArray(config.accounts)) {
        throw new Error("The existing local account configuration is invalid; it was left unchanged.");
      }
    } catch (error) {
      if (error.code !== "ENOENT") throw new Error("The local account configuration could not be read safely; it was left unchanged.");
      config = { version: 1, sessionSecret: randomBytes(48).toString("base64url"), accounts: [] };
    }
    if (command === "list") {
      console.log(JSON.stringify(config.accounts.map(({ username, displayName, enabled, role }) => ({ username, displayName, enabled, role })), null, 2));
      return;
    }
    const account = config.accounts.find((item) => item.username === username);
    if (command === "create" && account) throw new Error("That username already exists. Use reset to replace its password.");
    if (command !== "create" && !account) throw new Error("That username does not exist. Use create first.");
    if (command === "disable" || command === "enable") {
      account.enabled = command === "enable";
      await saveJson(configPath, config);
      console.log(`Admin account ${command}d. Account names and status can be checked with the list command.`);
      return;
    }
    const password = process.env.ABN_ADMIN_NEW_PASSWORD ?? randomBytes(24).toString("base64url");
    if (password.length < 16 || password.length > 1024) throw new Error("A supplied password must contain 16–1024 characters.");
    const hash = await passwordHash(password);
    if (account) {
      account.passwordHash = hash;
      // A password reset does not silently re-enable a disabled account or change its role.
      if (process.argv.includes("--name")) account.displayName = displayName;
    } else {
      config.accounts.push({ username, displayName, passwordHash: hash, role: "admin", enabled: true });
    }
    await saveJson(configPath, config);
    await saveJson(accessPath, {
      username, password, displayName: account?.displayName ?? displayName,
      createdAt: new Date().toISOString(), dashboardPath: "/abn-lead-gen/dashboard",
      note: "Private local credentials for the most recently provisioned account. Do not publish or commit this file.",
    });
    console.log("Admin account saved. Open website/.local/admin-access.txt on this computer for its username and password. Credentials were not printed.");
  } finally {
    await lock.close();
    await unlink(lockPath);
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : "The account could not be updated.");
  process.exitCode = 1;
});
