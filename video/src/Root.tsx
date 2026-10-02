import { Composition, Folder } from "remotion";
import { FootageEdit } from "./compositions/FootageEdit";
import { LogoIntro } from "./compositions/LogoIntro";

// Register every video here. Keep each <Composition> in this file with a literal id
// and an inline defaultProps object, so Studio can save prop edits back to the code.
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="Motion-graphics">
        <Composition
          id="LogoIntro"
          component={LogoIntro}
          durationInFrames={150}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{ tagline: "Built for momentum." }}
        />
      </Folder>
      <Folder name="Edits">
        <Composition
          id="FootageEdit"
          component={FootageEdit}
          durationInFrames={180}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{ name: "Your Name", role: "Role, Maintain Media" }}
        />
      </Folder>
    </>
  );
};
