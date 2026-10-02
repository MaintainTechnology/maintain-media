import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { assets, colors, easeOutExpo, fonts } from "../brand";

type Props = {
  readonly tagline: string;
};

// Motion-graphics example, from the prompt:
// "Make a 5-second logo intro on the dark brand background."
// Registered in src/Root.tsx (1920x1080, 30fps, 150 frames).
export const LogoIntro: React.FC<Props> = ({ tagline }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.canvas }}>
      {/* Purple glow, top right, as on the website hero */}
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 88% 8%, ${colors.brand}59, transparent 55%)` }} />

      {/* Wireframe mountains rising from the bottom edge */}
      <Img
        src={assets.mountain}
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          width: "100%",
          height: "62%",
          objectFit: "cover",
          maskImage: "linear-gradient(to top, black 55%, transparent)",
          opacity: interpolate(frame, [0, 1.2 * fps], [0, 0.85], { ...clamp, easing: easeOutExpo }),
          translate: interpolate(frame, [0, 1.6 * fps], ["0px 90px", "0px 0px"], { ...clamp, easing: easeOutExpo }),
        }}
      />

      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: 44,
          opacity: interpolate(frame, [durationInFrames - 0.5 * fps, durationInFrames], [1, 0], clamp),
        }}
      >
        {/* Real logo file, revealed left to right */}
        <Img
          src={assets.logoOnDark}
          style={{
            width: 820,
            clipPath: `inset(0 ${interpolate(frame, [0.2 * fps, 1.2 * fps], [100, 0], { ...clamp, easing: easeOutExpo })}% 0 0)`,
            scale: interpolate(frame, [0.2 * fps, 1.6 * fps], [0.94, 1], {
              ...clamp,
              easing: easeOutExpo,
              output: "perceptual-scale",
            }),
          }}
        />
        <div
          style={{
            fontFamily: fonts.display,
            fontWeight: 700,
            fontSize: 84,
            letterSpacing: "-0.02em",
            color: colors.brand300,
            opacity: interpolate(frame, [1.1 * fps, 1.9 * fps], [0, 1], { ...clamp, easing: easeOutExpo }),
            translate: interpolate(frame, [1.1 * fps, 1.9 * fps], ["0px 36px", "0px 0px"], { ...clamp, easing: easeOutExpo }),
          }}
        >
          {tagline}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
