import type { Metadata, Viewport } from "next";
import { albertSans, velaSans } from "./fonts";
import "./globals.css";
import { SiteShell } from "@/components/site-shell";
import { siteName, siteUrl } from "@/lib/site";

const designContract = `<!--
THESIS: A growth engine you can see working. Refuses the light SaaS-template
agency page of cream grounds, eyebrow labels and identical icon cards.
OWN-WORLD: Near-black teal canvas #061518, one carrying purple #a04dff, white
Vela Sans display over Albert Sans body, hairline dividers, purple-tinted
glows, the wireframe mountain landscape as hero atmosphere, pill buttons.
STORY: A brand owner lands, feels a sharp dark tech-forward team, reads proof
in numbers and process, and starts a project.
FIRST VIEWPORT: Full-height dark hero; headline and two CTAs upper left,
wireframe mountains rising from the bottom edge, purple glow top right.
FORM: Established world from DESIGN.md; content and IA inherited from the
initial HTML site. No concept roll: established system.
FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, and DESIGN.md.
-->`;

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Maintain Media | Marketing built to perform",
    template: `%s | ${siteName}`,
  },
  description:
    "Maintain Media is a full-service Brisbane marketing agency. Brand, performance, content and web, run as one team and measured by the numbers that matter.",
  openGraph: {
    type: "website",
    siteName,
    locale: "en_AU",
    url: siteUrl,
  },
  twitter: {
    card: "summary_large_image",
  },
};

export const viewport: Viewport = {
  themeColor: "#061518",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en-AU"
      className={`${albertSans.variable} ${velaSans.variable} antialiased`}
    >
      <body className="flex min-h-dvh flex-col">
        <div
          aria-hidden
          className="hidden"
          dangerouslySetInnerHTML={{ __html: designContract }}
        />
        <SiteShell>{children}</SiteShell>
      </body>
    </html>
  );
}
