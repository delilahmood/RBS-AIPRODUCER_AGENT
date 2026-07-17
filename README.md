# RBS AIProducer

**An end-to-end AI Showrunner for vertical short dramas.**

RBS AIProducer takes a single story idea and carries it through an entire production
pipeline — from concept to finished video — orchestrating a chain of specialized AI
agents, each handling one stage of the creative process the way a real production team
would.

---

## The Pipeline

1. **Showrunner** — writes a punchy synopsis, hook, and cliffhanger, with a producer-style
   viability analysis (completion rate, target audience, virality triggers).
2. **Casting** — designs the characters (personality, visual identity, secrets, arcs).
3. **Scriptwriter** — writes the full multi-episode script, respecting narrative style
   (first person, third person / voiceover, dialogue-driven) and genre.
4. **Character Visualizer & Model Sheet** — generates consistent character portraits and
   turnaround reference sheets.
5. **Location Scout & Location Design** — extracts and visualizes every setting used in
   the story.
6. **Shot Breakdown** — turns the script into an actual shot list: camera framing,
   movement, duration, characters and location per shot — like a real 1st AD.
7. **Storyboard Art** — generates cinematic storyboard frames per shot, with full shot-size
   and camera-angle variety.
8. **Shot Director** — analyzes each storyboard and generates an optimized video-generation
   prompt, then renders the final video clip via reference-to-video AI models.

Every stage keeps a full version history, lets the user pick between multiple proposals,
and never runs an expensive step without explicit confirmation.

---

## Built for QwenCloud AI Hackathon — Track 2: AI Showrunner

RBS AIProducer runs entirely on Alibaba Cloud's model ecosystem:
- **Qwen3-Max** for all narrative/reasoning agents
- **Wan2.2 / Qwen-Image** for character, location, and storyboard art generation
- **Wan2.7 R2V** and **HappyHorse R2V** for final video generation, using the storyboard,
  character, and location references directly — not text-to-video guesswork

---

## Status

This is a hackathon MVP: the full pipeline is functional end-to-end, from idea to video.
The workflow itself is fully operational — but reaching the professional-grade visual and
video quality the format deserves still requires deeper prompt testing, a stronger library
of proven prompt examples, and continued mastery of Wan and HappyHorse's prompting
conventions. This refinement work is actively underway as the product evolves.

Some steps are still being refined (prompt quality, narrative-style edge cases, multi-form
character handling) — see [Known Limitations](#known-limitations) below.

---

## Known Limitations

- **Prompt maturity** — the visual and video generation prompts (Storyboard Art, Shot
  Director) are functional but still being tuned against real production examples to reach
  consistent, professional-grade cinematic output across every shot type.
- **Narrative-style edge cases** — storytelling modes (first person, third person /
  voiceover, dialogue-driven) are supported, but some genre/structure combinations still
  need refinement to behave exactly as intended.
- **Multi-form characters** — characters with two distinct physical appearances (curses,
  transformations, disguises) are currently handled as two linked character sheets rather
  than a single unified data model — functional, but not yet a fully integrated feature.
- **Manual review recommended** — as with any generative pipeline, outputs (especially
  video) benefit from a human pass before being considered final.

---

## What's Next

- **Studio module** — already scaffolded in the codebase but not yet wired into the live
  pipeline. It will enable hybrid, human-in-the-loop refinement of the generated short
  drama — fine-tuning AI output within a dedicated workspace rather than regenerating
  from scratch.
- **Prompt generator*** — A special agent to make prompts according to models and use cases.
- **Format flexibility** — the platform already supports choosing between **vertical (9:16)**
  and **horizontal (16:9)** output depending on the project type (Short Drama vs. Short
  Movie), a first step toward broader format support as the product grows.

---

## Tech Stack

FastAPI · SQLAlchemy · Jinja2 · Vanilla JS · SQLite · DashScope SDK

---

## License

MIT

