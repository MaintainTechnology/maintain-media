import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import path from "node:path";

export const alt = "Maintain Media. Marketing built to perform.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  const vela = await readFile(
    path.join(process.cwd(), "src/fonts/VelaSans-Bold.otf"),
  );

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          backgroundColor: "#061518",
          backgroundImage:
            "radial-gradient(640px 420px at 85% 0%, rgba(160,77,255,0.45), transparent 65%)",
          fontFamily: "Vela",
        }}
      >
        <svg width="132" height="84" viewBox="0 0 146 93" fill="none">
          <path
            d="M145.266 50.8169V91.6312C145.266 92.2738 144.749 92.8012 144.096 92.8012H106.102C105.066 92.8012 104.538 91.5449 105.277 90.8065L145.266 50.8169Z"
            fill="#a04dff"
          />
          <path
            d="M145.267 1.16959V50.8258H137.193C135.649 50.8258 134.162 51.4395 133.069 52.5328L93.1464 92.4552C92.9258 92.6758 92.6285 92.8005 92.3217 92.8005H53.6458C52.6101 92.8005 52.0827 91.5442 52.8211 90.8058L143.282 0.344859C144.02 -0.393559 145.277 0.133883 145.277 1.16959H145.267Z"
            fill="#a04dff"
          />
          <path
            d="M92.8005 1.16959V50.8258H84.7258C83.1819 50.8258 81.6955 51.4395 80.6022 52.5328L40.6797 92.4552C40.4592 92.6758 40.1619 92.8005 39.855 92.8005H1.16959C0.133883 92.8005 -0.393558 91.5442 0.344859 90.8058L90.8058 0.344859C91.5442 -0.393559 92.8005 0.133883 92.8005 1.16959Z"
            fill="#a04dff"
          />
        </svg>
        <div
          style={{
            marginTop: 48,
            fontSize: 84,
            color: "#ffffff",
            letterSpacing: "-2px",
          }}
        >
          Maintain Media
        </div>
        <div style={{ marginTop: 16, fontSize: 34, color: "#cdd9db" }}>
          Marketing built to perform
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [{ name: "Vela", data: vela, weight: 700 }],
    },
  );
}
