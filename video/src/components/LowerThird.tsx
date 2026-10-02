import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { colors, easeOutExpo, fonts } from "../brand";

type Props = {
  readonly name: string;
  readonly role: string;
};

// Brand lower third: wipes in from the left, fades out over the last 0.4s of
// its parent <Sequence>, so the Sequence's durationInFrames sets how long it stays.
export const LowerThird: React.FC<Props> = ({ name, role }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

  return (
    <div
      style={{
        position: "absolute",
        left: 140,
        bottom: 140,
        clipPath: `inset(0 ${interpolate(frame, [0, 0.7 * fps], [100, 0], { ...clamp, easing: easeOutExpo })}% 0 0)`,
        opacity: interpolate(frame, [durationInFrames - 0.4 * fps, durationInFrames], [1, 0], clamp),
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 28,
          padding: "28px 44px 28px 28px",
          borderRadius: 14,
          backgroundColor: `${colors.canvas}d9`,
        }}
      >
        <div style={{ width: 8, borderRadius: 4, backgroundColor: colors.brand }} />
        <div>
          <div style={{ fontFamily: fonts.display, fontWeight: 700, fontSize: 72, lineHeight: 1.1, color: colors.ink }}>
            {name}
          </div>
          <div style={{ fontFamily: fonts.body, fontWeight: 500, fontSize: 44, marginTop: 8, color: colors.ink2 }}>
            {role}
          </div>
        </div>
      </div>
    </div>
  );
};
