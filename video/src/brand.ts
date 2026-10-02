import { loadFont } from "@remotion/fonts";
import { Easing, staticFile } from "remotion";

// Maintain Media brand tokens for video. Source of truth: ../DESIGN.md.
// Import from here instead of hard-coding brand values in compositions.

export const colors = {
  canvas: "#061518", // video background (near-black teal)
  surface: "#0c2a30", // panels, cards
  surface2: "#123a42", // raised panels
  brand: "#a04dff", // the one carrying accent
  brand300: "#c79bff", // lighter purple for accents on dark
  brandDeep: "#3a1f6b",
  brandDark: "#08282d",
  ink: "#ffffff", // headings on dark
  ink2: "#cdd9db", // body text on dark
  mist: "#93a7aa", // captions and labels
} as const;

export const fonts = {
  display: "Vela Sans", // headlines, weights 600-800
  body: "Albert Sans", // everything else, weights 100-900
} as const;

// Signature brand gradient: purple to deep teal/black.
export const brandGradient = `linear-gradient(180deg, ${colors.brand} 0%, ${colors.brandDeep} 45%, ${colors.brandDark} 100%)`;

// The website's ease-out-expo. Brand motion is confident: ease out, never bounce.
export const easeOutExpo = Easing.bezier(0.16, 1, 0.3, 1);

export const assets = {
  logoOnDark: staticFile("brand/maintain-media-logo-darkbg.svg"),
  logoOnLight: staticFile("brand/maintain-media-logo-lightbg.svg"),
  mountain: staticFile("brand/maintain-media-mountain-forms.webp"),
} as const;

// Renders wait for these, so text never falls back to a system font.
await Promise.all([
  loadFont({ family: fonts.body, url: staticFile("fonts/AlbertSans-VariableFont_wght.ttf"), weight: "100 900" }),
  loadFont({ family: fonts.display, url: staticFile("fonts/VelaSans-SemiBold.otf"), weight: "600" }),
  loadFont({ family: fonts.display, url: staticFile("fonts/VelaSans-Bold.otf"), weight: "700" }),
  loadFont({ family: fonts.display, url: staticFile("fonts/VelaSans-ExtraBold.otf"), weight: "800" }),
]);
