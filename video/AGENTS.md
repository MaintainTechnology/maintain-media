# Maintain Media video

Remotion project (React to MP4) for Maintain Media's video edits and motion graphics.
The main user is Jullian, a video editor who works by prompting in plain language
("cut this interview to 30 seconds", "make a logo intro for Reels"). Turn requests
into compositions, show them in the Studio, and render when asked. Explain results
in editing terms (clips, cuts, timing), not code.

## Skills

Remotion's official Agent Skills live in `.agents/skills/` (Codex and most agents) and
`.claude/skills/` (Claude Code). Start with `remotion-best-practices`; it routes to the
rest (`remotion-create`, `remotion-markup`, `remotion-captions`, `remotion-render`,
`remotion-studio`, `remotion-docs`, and others). Update them with `npx remotion skills update`;
don't edit skill files by hand.

## Commands

| Task | Command |
| --- | --- |
| Studio (preview, timeline, edits) | `npm run dev`, then open http://localhost:3000 |
| Render a video | `npx remotion render <CompositionId> out/<name>.mp4` |
| Render a still | `npx remotion still <CompositionId> out/<name>.png --frame=<n>` |
| Check code | `npm run lint` |
| Add a Remotion package | `npx remotion add @remotion/<package>` (keeps all Remotion packages on one version) |

## Where things go

| Path | Contents |
| --- | --- |
| `src/compositions/<Name>.tsx` | One video per file: the component and its props type. |
| `src/Root.tsx` | Registers every video as a `<Composition>` inside a `<Folder>` (`Motion-graphics`, `Edits`, or a new one). Keep each registration here with a literal `id` and an inline `defaultProps` object, or the Studio can't save prop edits. |
| `src/components/` | Reusable pieces, such as `LowerThird`. |
| `src/brand.ts` | Brand colours, fonts, easing and asset paths. Import from here; never hard-code brand values. |
| `public/footage/`, `public/audio/` | Raw clips, music, voice-over, sound effects. Not in Git. Load with `staticFile("footage/<file>")`. |
| `public/brand/`, `public/fonts/` | Copies of the brand library (`../media`, `../website`). Don't edit them here. |
| `out/` | Renders. Not in Git. |

Working examples to copy from: `LogoIntro` (motion graphic) and `FootageEdit` (trimmed clip, lower third, fades).

## Brand rules (source: `../DESIGN.md`)

- Dark first: canvas `#061518`, one accent purple `#a04dff` (`#c79bff` for text accents on dark), white headings, `#cdd9db` body text.
- Type: Vela Sans (600-800) for headlines, Albert Sans for everything else, via `fonts` in `src/brand.ts`.
- Logo: `assets.logoOnDark` on dark backgrounds, `assets.logoOnLight` on light ones. Never recolour, stretch or rotate it.
- Motion: ease out with `easeOutExpo` (`cubic-bezier(0.16, 1, 0.3, 1)`). Confident and precise: no bounce or playful overshoot.

## Defaults

- 30 fps. Landscape 1920x1080 unless asked; Reels, TikTok and Shorts are 1080x1920; square posts are 1080x1080.
- Keep important text inside the safe area and size it for video, not the web (see the `remotion-create` skill).
- If a request doesn't give a format or length, use these defaults and say which you used.
- Preview in the Studio before rendering anything long.
