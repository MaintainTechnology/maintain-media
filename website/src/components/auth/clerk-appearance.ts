import type { ComponentProps } from "react";
import type { ClerkProvider } from "@clerk/nextjs";

/** The same colours, type and shapes used by the Maintain Media website. */
export const clerkAppearance = {
  variables: {
    colorPrimary: "#c79bff",
    colorPrimaryForeground: "#08282d",
    colorBackground: "#0c2a30",
    colorForeground: "#ffffff",
    colorMuted: "#123a42",
    colorMutedForeground: "#cdd9db",
    colorNeutral: "#ffffff",
    colorInput: "#061518",
    colorInputForeground: "#ffffff",
    colorDanger: "#ffb5b5",
    colorBorder: "rgba(255, 255, 255, 0.16)",
    colorRing: "#a04dff",
    fontFamily: 'var(--font-albert), "Albert Sans", sans-serif',
    fontFamilyButtons: 'var(--font-albert), "Albert Sans", sans-serif',
    fontSize: "0.9375rem",
    borderRadius: "0.875rem",
  },
  elements: {
    cardBox: { borderRadius: "20px", boxShadow: "none", width: "100%", maxWidth: "100%", border: "1px solid rgba(255,255,255,.12)" },
    card: { boxShadow: "none", padding: "clamp(1.25rem, 4vw, 2rem)" },
    rootBox: { width: "100%", maxWidth: "100%" },
    formButtonPrimary: { minHeight: "48px", borderRadius: "999px", fontWeight: 700 },
    formFieldInput: { minHeight: "48px", borderRadius: "14px" },
    socialButtonsBlockButton: { minHeight: "48px", borderRadius: "999px" },
    footer: { background: "#0c2a30", backgroundImage: "none" },
    footerActionLink: { color: "#c79bff" },
    userButtonTrigger: { minHeight: "44px", minWidth: "44px", borderRadius: "999px" },
    userButtonAvatarBox: { width: "36px", height: "36px" },
    userButtonPopoverCard: { maxWidth: "calc(100vw - 32px)" },
  },
} satisfies NonNullable<ComponentProps<typeof ClerkProvider>["appearance"]>;
