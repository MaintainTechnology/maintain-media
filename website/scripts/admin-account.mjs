// Kept only to give existing local setup shortcuts a clear migration message.
console.error("Local admin passwords have been retired. Create your account at /sign-up using Clerk. An existing Clerk application administrator must set publicMetadata.role to admin to grant ABN Lead Gen access.");
process.exitCode = 1;
