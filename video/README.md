# Maintain Media video

Edit videos and make motion graphics by describing what you want to an AI agent,
Claude Code or Codex. Built on [Remotion](https://www.remotion.dev/docs): every video
is code, so the agent can build and change it, and you can fine-tune it in the Studio.

## First-time setup

1. Install [Node.js](https://nodejs.org) (LTS) and Claude Code or Codex.
2. In a terminal, from the repository folder:

   ```bash
   cd video
   npm install
   ```

## Each session

Open two terminals, both in the `video` folder:

1. `npm run dev` opens the Remotion Studio at http://localhost:3000 for preview, timeline and edits.
2. `claude` or `codex` starts your agent. Describe what you want.

Always start the agent inside `video/`, so it picks up this project's Remotion skills and instructions.

## Prompts to try

- "Make a 5-second logo intro for Instagram Reels."
- "Put footage/interview.mp4 on a timeline, cut the first 3 seconds, and add a lower third: Sam Lee, Head of Growth."
- "Add captions to footage/interview.mp4."
- "Make a 9:16 version of LogoIntro."
- "Render FootageEdit."

To use a specific skill, name it: `/remotion-captions` in Claude Code, `$remotion-captions`
in Codex (type `/skills` in Codex to browse them).

## Footage, audio and renders

| Folder | What goes there | In Git? |
| --- | --- | --- |
| `public/footage/` | Raw clips | No. Keep originals on the shared drive. |
| `public/audio/` | Music, voice-over, sound effects | No |
| `out/` | Finished renders | No |

## Rendering yourself

```bash
npx remotion render LogoIntro out/logo-intro.mp4
```

## Keeping up to date

- Remotion: `npm run upgrade`
- Agent skills: `npx remotion skills update`

## Licence

Remotion is free for teams of up to 3 people. Larger companies need a
[company licence](https://www.remotion.pro/license).
