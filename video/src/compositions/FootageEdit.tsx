import { Video } from "@remotion/media";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { LowerThird } from "../components/LowerThird";

type Props = {
  readonly name: string;
  readonly role: string;
};

// Video-editing example, from the prompt:
// "Trim the clip to 6 seconds, add a lower third, fade in and out."
// Registered in src/Root.tsx (1920x1080, 30fps, 180 frames).
// For real footage, put the file in public/footage/ and use src={staticFile("footage/<file>.mp4")}.
export const FootageEdit: React.FC<Props> = ({ name, role }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "black",
        opacity: interpolate(frame, [0, 0.4 * fps, durationInFrames - 0.4 * fps, durationInFrames], [0, 1, 1, 0], clamp),
      }}
    >
      {/* Skips the first 2s of the source, then plays 6s. Audio fades with the picture. */}
      <Video
        name="Sample clip"
        src="https://remotion.media/video.mp4"
        trimBefore={60}
        durationInFrames={180}
        premountFor={fps}
        volume={(f) => interpolate(f, [0, 12, 168, 180], [0, 1, 1, 0], clamp)}
      />
      <Sequence name="Lower third" from={30} durationInFrames={120} premountFor={fps}>
        <LowerThird name={name} role={role} />
      </Sequence>
    </AbsoluteFill>
  );
};
