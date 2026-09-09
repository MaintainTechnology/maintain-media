import localFont from "next/font/local";

// Brand type library, self-hosted from media/complete-toolkit (DESIGN.md).
// Albert Sans: primary UI/body/headings. Vela Sans: display headlines only.
export const albertSans = localFont({
  src: [
    {
      path: "../fonts/AlbertSans-VariableFont_wght.ttf",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../fonts/AlbertSans-Italic-VariableFont_wght.ttf",
      style: "italic",
      weight: "100 900",
    },
  ],
  variable: "--font-albert",
  display: "swap",
});

export const velaSans = localFont({
  src: [
    { path: "../fonts/VelaSans-SemiBold.otf", weight: "600" },
    { path: "../fonts/VelaSans-Bold.otf", weight: "700" },
    { path: "../fonts/VelaSans-ExtraBold.otf", weight: "800" },
  ],
  variable: "--font-vela",
  display: "swap",
});
