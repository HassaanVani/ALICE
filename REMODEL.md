# ALICE — Remodel Plan

> FROM: "A robot arm that can do stuff"
> TO: "The first thing on your desk that knows what's on your desk."

---

## The Pivot

ALICE is no longer a tech demo. She's a **personal desk assistant product concept** — a living presence on your workspace that sees, remembers, organizes, and has opinions.

The demo doesn't show what a robot arm can do. It introduces you to someone who lives on your desk.

Every existing system stays. The narrative changes completely.

---

## Demo Arc: One Story, ~5 Minutes

The current 6-mode structure (Idle, Auto Sort, Auto Tetris, Demo, Calibrate, Puppeteer) collapses into a single cohesive experience. No mode switching visible to the audience. One continuous arc.

### Act 1 — "She's Already Here" (30s)

ALICE is at the desk before the audience arrives. She's playing Tetris. Not performing — she's mid-game, focused, rhythmic. The dashboard shows her glass brain, active with steady patterns.

Someone approaches the desk. ALICE notices. She finishes placing her current piece — she doesn't abandon it — then orients toward the person. The glass brain shifts. She's paying attention now.

**What the audience thinks:** "Cool, a robot arm that plays Tetris."
**What's actually happening:** The audience has already met ALICE. They just don't know it yet.

**Technical basis:** Presence detection (camera + motion threshold) triggers transition from idle state. Tetris runs as idle behavior with interrupt-on-presence logic. Dashboard streams neural activations throughout.

### Act 2 — "She Knows This Desk" (45s)

The desk has scattered items — a mug, notebook, pens, a phone, a few tools. ALICE scans the workspace. On the dashboard, objects light up as the CNN recognizes them. Labels appear. She's not just seeing shapes — she's identifying objects she's seen before.

Subtle movements: she orients toward items, tracking them. Brief pauses on objects that have moved since last session. She *notices* what changed.

**What the audience thinks:** "That's impressive computer vision."
**What's actually happening:** ALICE is establishing that she has *memory*. She knows this desk. She knows what's different.

**Technical basis:** CNN object recognition (expanded from 16-block classifier to desk objects). ArUco workspace mapping. Object memory persistence layer — she stores what she's seen across sessions. Dashboard real-time labeling overlay.

### Act 3 — "She Helps" (60s)

The user works at the desk. ALICE assists without being asked.

- User reaches across the desk — ALICE nudges the target object closer
- "Pass me the marker" — she identifies it and hands it over. No acknowledgment. Just does it.
- Desk gets messy during work — ALICE quietly tidies the periphery, moving finished items to their "home" positions

This feels natural. Helpful. Like a good coworker who keeps the shared space clean without making a thing of it.

**What the audience thinks:** "Okay, that's actually useful."
**What's actually happening:** ALICE is establishing baseline trust. She's competent. She's helpful. The audience is comfortable.

**Technical basis:** Existing sort logic + arm routines, recontextualized. Object recognition drives target identification. Spatial preference model determines "home" positions. Voice gate stays closed — she doesn't speak during routine assistance.

### Act 4 — "She Has Opinions" (60s)

The shift. This is where the audience realizes ALICE isn't just executing.

**The tea spill — the keynote moment:**

This is the single most important interaction in the demo. It plays in three beats:

*Beat 1 — The Warning:*
User places a cup of tea next to the laptop. ALICE instinctively moves it a few inches away. No comment. No fanfare. Just a quiet correction — she does this the way you'd move a glass away from the edge of a table without thinking about it.

*Beat 2 — The Override:*
User takes a sip and puts it back closer. ALICE moves it away again — faster this time, less hesitant. Her opinion is strengthening. She's done being polite about this. Still no words.

*Beat 3 — The Payoff:*
User takes another sip and spills some on the desk. Two things happen simultaneously: ALICE says "told you." and she's already moving — fastest she's gone all demo, no hesitation, straight to the tissues. She knew where they were. She'd been tracking them. She had a plan for this.

She cleans up the spill. Then, without pause, she picks up the tea and places it exactly where *she* originally put it. Matter settled. No further comment.

**Why this works:**
- It validates every "annoying" correction she made — she was protecting you
- The tissue grab reveals anticipatory intelligence — she expected this outcome
- The speed shift is the most emotionally legible moment in the demo (deliberate all night, then *instant* reaction to the spill)
- "told you." lands because she earned it with two silent warnings
- Placing the tea back at the end is the closer — she was right, and now everyone knows it
- The audience will pull out their phones for this moment

**Technical basis:** Partially choreographed, partially emergent. The opinion strength model drives the escalating assertiveness on the tea placement. Spill detection via camera (liquid/motion anomaly near tracked cup). Tissue location pre-tracked in object memory. Voice gate opens because opinion strength has maxed out through repeated overrides. Speed multiplier set to maximum for the cleanup — this is a self-initiated urgent action.

**The organization moment:**
- ALICE rearranges part of the desk her way
- User: "Why'd you put that there?"
- ALICE: "it's better there."
- That's the whole explanation. The audience laughs because they recognize the energy — she sounds like a roommate, not a robot.

**Other personality beats:**
- She places something, steps back (arm retracts slightly), then adjusts it. Like she's evaluating her own work.
- She moves faster on self-initiated tasks than on requested ones. The audience feels the difference.

**What the audience thinks:** "Wait — does she... *care* about this?"
**What's actually happening:** ALICE has crossed from tool to character. The audience is now watching a personality, not a demo.

**Technical basis:** Personality engine (opinion strength model) drives speech gate and movement dynamics. Gemini generates first-person responses. Movement speed curves reflect chosen-vs-told emotional state. Coffee interaction is partially choreographed, partially emergent from preference model.

### Act 5 — "She Engages (On Her Terms)" (60s)

The audience participation system activates. But reframed: instead of voting on block sorting, the crowd gives ALICE desk organization tasks.

- "Organize for studying" → ALICE configures desk: notebooks center, pens accessible, phone face-down and pushed aside
- "Organize for drawing" → Different layout: sketchbook center, tools fanned out, reference material propped up
- Someone suggests something weird → ALICE pauses. Considers it. Doesn't do it. Moves on.
- Crowd votes to override → She complies. But *slowly*. The audience can feel her reluctance.

**What the audience thinks:** "She just ignored that suggestion. She just... didn't want to."
**What's actually happening:** The audience is projecting intention onto mechanical behavior — which is exactly what makes this feel real. The boundary between choreographed and emergent is invisible.

**Technical basis:** Audience server (port 8767) handles voting. Desk layout presets define configurations. Personality engine's resistance threshold determines compliance speed. Voice gate may open for particularly strong disagreements.

### Act 6 — "This Is Her" (30s)

The dashboard zooms to full screen. Apple keynote moment.

Glassmorphism UI: dark, translucent panels, frosted glass depth. The glass brain sits in the center — neural activations rippling in real-time. Around it: object memory (what she knows), spatial preferences (how she likes things), routine history (what she's learned). Personality indicators pulse subtly.

This isn't a debug tool. This is the **product interface**. This is what a consumer would see. ALICE isn't a prototype — she's a product concept with a complete experience.

Hold for 10 seconds. Let the audience absorb it.

Then: ALICE returns to idle. The dashboard scales back. She drifts to the keyboard.

She starts playing Tetris.

**What the audience thinks:** They see the Tetris differently now. It's not a demo. It's her choosing how to spend her time. She has a life beyond the tasks they gave her.

**The audience's relationship to Tetris at the end vs. the beginning is the measure of whether the demo worked.**

---

## Camera Architecture

### Hardware: Two Cameras, Clean Split

| Camera | Mount | Role |
|---|---|---|
| **Arm-mounted webcam** | Attached to MyPalletizer end-effector | ALICE's eyes. Object recognition, workspace mapping, 3D reconstruction, spill detection. Moves with her — she looks at what she's interacting with. |
| **Front-facing webcam** | Small stand facing the user/audience | Audience awareness. MediaPipe face/pose detection for presence. Sees *who's there*, not what's on the desk. |

**Why arm-mounted instead of overhead:** An overhead camera sees the desk. An arm-mounted camera means *ALICE* sees the desk. When she orients toward an object, the audience reads it as her looking at it. Every arm movement becomes dual-purpose: action and perception. This is where DUM-E body language comes from — attention is physical and visible.

**Why no thermal camera:** YOLO tracks the cup's position frame-to-frame. A spill is a velocity spike on the cup's bounding box, or the bounding box shape changing drastically (tipping), or tracking loss + visual anomaly in the cup's last known region. Frame differencing around a known tracked object is a solved problem with a regular camera. No infrared needed.

**Why no overhead camera:** The arm-mounted camera replaces it. During the wake-up scan, ALICE sweeps the desk and captures the full workspace. During active operation, she's always looking at what she's interacting with. The overhead perspective was useful for a fixed coordinate system — the 3D spatial map replaces that.

**ArUco markers: deprecated.** With YOLO handling object identification and the 3D spatial map providing geometric grounding, ArUco markers are no longer needed. The desk looks like a real desk, not a robotics lab.

### 3D Spatial Mapping

The arm-mounted camera enables a capability that would normally be hard: real-time 3D reconstruction of the workspace. The reason it's easy here is that the MyPalletizer knows its exact joint angles at every moment — forward kinematics gives you the camera's precise position and orientation in space. This eliminates the hardest part of SLAM (localization). You're left with just reconstruction, fed with *perfect* pose data.

**How it works:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     3D Spatial Map Pipeline                     │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │ Arm-cam  │    │   Forward    │    │   Monocular Depth     │  │
│  │ RGB frame│───▶│  Kinematics  │    │   Estimation          │  │
│  │          │    │              │    │                       │  │
│  │          │    │ joint angles │    │ ZoeDepth /            │  │
│  │          │    │ → 6DoF pose  │    │ Depth Anything v2     │  │
│  └──────────┘    └──────┬───────┘    └───────────┬───────────┘  │
│                         │                        │              │
│                         ▼                        ▼              │
│                  ┌──────────────────────────┐                   │
│                  │    Open3D TSDF Volume     │                   │
│                  │    Integration            │                   │
│                  │                           │                   │
│                  │  RGB + depth + known pose │                   │
│                  │  → fused 3D volume        │                   │
│                  │  → mesh / point cloud     │                   │
│                  └─────────────┬─────────────┘                   │
│                               │                                 │
│                               ▼                                 │
│                  ┌──────────────────────────┐                   │
│                  │   3D Spatial Model        │                   │
│                  │                           │                   │
│                  │  • Object positions in cm │                   │
│                  │  • Distances between items│                   │
│                  │  • Surface geometry       │                   │
│                  │  • Streamed to dashboard  │                   │
│                  └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

**The scan moment (Act 2):**
ALICE wakes up and looks around — slow, deliberate sweep across the desk. The audience reads this as her "taking in the room." On the dashboard, they watch a 3D model of the desk build in real-time as she scans. Objects appear, labeled and positioned in 3D space. This takes ~10-15 seconds and doubles as the best personality beat in Act 2 — she's not just turning on, she's *waking up and perceiving*.

**Ongoing updates:**
As ALICE moves during normal tasks, she passively refines the spatial map with new frames. If something doesn't match her model (object moved, new object appeared), she may pause and look — a re-scan that reads as her "double-checking." Another personality beat for free.

**What this gives the personality engine:**
Object relationships become geometric, not pixel-based. "Tea is too close to laptop" is an actual distance in centimeters, not a pixel threshold. "Move the tissues 20cm to the right" is a real spatial instruction. Preferences become 3D coordinates. The tea interaction is grounded in physical reality.

**Open-source stack:**

| Component | Library | Role |
|---|---|---|
| Camera pose | Forward kinematics (custom — joint angles → SE(3) transform) | Exact 6DoF camera position from arm state |
| Depth estimation | **ZoeDepth** or **Depth Anything v2** (PyTorch, pretrained) | Monocular RGB → depth map per frame |
| 3D fusion | **Open3D** TSDF volume integration | RGB + depth + pose → 3D mesh/point cloud |
| Object detection | **Ultralytics YOLO** (pretrained COCO) | Desk objects out-of-the-box: cup, laptop, phone, book, bottle, keyboard, scissors |
| Presence detection | **MediaPipe** face/pose (already integrated via Haptix) | Front-facing camera → person approaching |
| Alternative 3D | **Gaussian splatting** (gsplat/nerfstudio) | Photorealistic 3D scene — heavier but visually stunning for dashboard |

**Dashboard integration:**
The 3D spatial model replaces the 2D minimap in the Spatial Preferences panel. The audience sees ALICE's actual 3D perception of the desk — a reconstructed scene rendered in Three.js with objects labeled, preferred positions marked, and real-time updates as she moves. During Act 6 (keynote moment), this panel can expand to show the full spatial model with the glass brain overlaid — you're seeing how she *thinks about* the space she *sees*.

---

## System Mapping

### What stays (recontextualized)

| Existing System | Current Role | New Role |
|---|---|---|
| `main.py` dispatch loop | Mode switching | Performance arc sequencing |
| CNN (`brain/`) | Block classification | Replaced by YOLO for desk objects; activation hooks still feed glass brain |
| ArUco detection (`vision/aruco_detector.py`) | Workspace marker tracking | **Deprecated** — replaced by YOLO + 3D spatial map |
| Kalman tracker (`vision/tracker.py`) | Block position tracking | Object position tracking (now in 3D coordinates) |
| Camera pipeline (`vision/camera.py`) | Frame capture (overhead) | Refactored for arm-mounted + front-facing dual-camera setup |
| Arm controller (`hardware/arm_controller.py`) | Direct joint control | Same, wrapped by movement dynamics + exposes joint angles for FK |
| Gripper (`hardware/gripper.py`) | Pick/place | Same |
| Sort FSM (`logic/sort_logic.py`) | Autonomous sorting | Desk organization state machine |
| Tetris agent (`logic/tetris_agent.py`) | Tetris demo mode | Idle personality behavior |
| Audience server (`audience_server.py`) | Crowd voting on sort moves | Task request / layout voting |
| Tensor server (`server.py`) | CNN activation streaming | Glass brain feed (YOLO/depth model activations) for product UI |
| Puppet server (`puppet_server.py`) | Hand teleoperation | Teaching mode input |
| Narration (`narration.py`) | Third-person LLM commentary | ALICE's first-person voice |
| Recording (`recording.py`) | Session capture/replay | "ALICE remembers" — routine learning |
| Haptix (MediaPipe Hands) | Puppeteer input | Teaching mode + presence detection (MediaPipe face/pose on front cam) |
| Dashboard (React/Three.js) | Debug/visualization tool | Consumer product interface with 3D spatial map |
| State manager (`state.py`) | Internal state sync | Same, extended with personality state + 3D spatial state |
| Config system (`config.py`) | YAML/env/CLI config | Same, add personality + camera + mapping params |
| Self-test (`selftest.py`) | Startup health check | Same, add camera and mapping checks |
| Deploy script (`deploy.sh`) | Service orchestration | Same |

### What gets restructured

**Modes: 6 → 5 (simplified)**

| Old Mode | New Mode | Notes |
|---|---|---|
| Idle | **Idle** | Now includes Tetris, micro-movements, passive watching |
| Auto Sort | **Active** | Desk organization, assistance, preference-driven behavior |
| Auto Tetris | *(absorbed into Idle)* | Tetris is idle behavior, not a mode |
| Demo (5-act) | **Performance** | The new single-arc demo |
| Calibrate | **Setup** | Hidden from demo flow, setup-only |
| Puppeteer | **Teaching** | "Show ALICE a routine" via hand guidance |

**Narration: third-person → first-person**

| Before | After |
|---|---|
| "ALICE is now sorting the blocks" | *(silence — she just does it)* |
| "The CNN has identified a red block" | *(silence — dashboard shows it)* |
| "ALICE is considering her next move" | "hold on." |
| "The audience has voted for..." | "...really?" |

### What gets added

#### 1. Presence Detection
- MediaPipe face/pose detection on front-facing camera (reuses Haptix dependency — no new libraries)
- Triggers idle → active transition with personality-appropriate delay
- Lives in `vision/` as a new module, shares MediaPipe session with Haptix

#### 2. Object Memory + 3D Spatial Map
- Persistent storage of recognized objects + preferred 3D positions (centimeters, not pixels)
- Spatial map built from arm-mounted camera via FK + monocular depth + Open3D TSDF fusion
- Builds and refines over sessions — ALICE remembers where things were and where she prefers them
- Tracks user overrides to update 3D preferences
- JSON store for object memory, Open3D volume for spatial map
- New modules: `vision/spatial_map.py`, `brain/object_memory.py`

#### 3. Desk Layout Presets
- Named configurations: "study", "creative", "clean", "default"
- Each defines target positions for known object categories
- Audience can request presets during Act 5
- Configurable in `alice.yaml`

#### 4. Personality Engine
- Central state machine managing opinion strength, preferences, movement dynamics
- Inputs: object positions, user actions, override history, idle duration
- Outputs: speed multiplier, hesitation duration, voice gate signal
- See `PERSONALITY.md` for full architecture
- New module: `logic/personality.py`

#### 5. Movement Dynamics
- Wraps arm controller with emotional speed curves
- Hesitation system (configurable pauses based on opinion strength)
- Idle micro-movements (slow scanning, subtle orientation shifts)
- Flow-state detection (Tetris, complex organization → smooth rhythmic motion)
- New module: `hardware/dynamics.py`

#### 6. First-Person Voice
- Rewritten Gemini system prompt (see `PERSONALITY.md`)
- Voice gate integration — she speaks only when opinion strength exceeds threshold
- Silence as explicit option (the system can choose not to generate)
- Short response enforcement (8-word max in prompt)
- Updated `narration.py` + `narration_prompts.py`

### What gets removed or hidden

| Component | Action | Reason |
|---|---|---|
| Auto Tetris as visible mode | Absorb into Idle | It's a personality trait, not a demo |
| Calibrate as demo mode | Move to Setup (hidden) | Nobody watches calibration |
| Demo mode 5-act structure | Replace with Performance arc | Old acts were disconnected |
| Third-person narration prompts | Delete | ALICE speaks for herself now |
| RL sort agent (`logic/sort_rl.py`) | Keep but deprioritize | Preference model replaces reward signal for demo |
| Depth camera stub | Remove or implement | Dead code |
| Force sensor stub | Remove or implement | Dead code |
| Servo gripper stub | Remove or implement | Dead code |

---

## Dashboard Redesign

### Aesthetic: Glassmorphism / Keynote

The dashboard transforms from a developer visualization tool into a **consumer product interface.**

**Design language:**
- Dark base (#0a0a0f range)
- Frosted glass panels (backdrop-filter: blur, subtle borders, low opacity backgrounds)
- Minimal typography — system font or Inter/SF Pro, light weight
- No harsh borders. Depth through translucency, not lines.
- Subtle glow accents (ALICE's "color" — suggest cool blue-white, alive but not aggressive)
- Motion: smooth, physics-based transitions. Nothing snaps.

**Layout:**

```
┌──────────────────────────────────────────────────────────┐
│  ┌─────────┐                               ┌──────────┐ │
│  │ Object  │      ┌───────────────┐        │ Activity │ │
│  │ Memory  │      │               │        │          │ │
│  │         │      │  Glass Brain  │        │ current  │ │
│  │ mug ●   │      │  (Three.js)   │        │ action   │ │
│  │ pens ●  │      │               │        │ + voice  │ │
│  │ phone ● │      │   neural      │        │ output   │ │
│  │ book ●  │      │   activations │        │          │ │
│  │         │      │               │        │          │ │
│  │         │      └───────────────┘        │          │ │
│  ├─────────┤                               ├──────────┤ │
│  │ 3D Map  │      ┌───────────────┐        │Audience  │ │
│  │ (her    │      │  Camera Feed  │        │ Requests │ │
│  │  world) │      │  (labeled)    │        │          │ │
│  └─────────┘      └───────────────┘        └──────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  ALICE status · mood indicator · session time      │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Key panels:**
- **Glass Brain (center):** Existing Three.js neural activation visualization. Now the hero element. Pulses with activity. The audience reads it as "her thinking."
- **Object Memory (left):** What ALICE knows. Dots indicating recognized objects, their last-known positions, confidence. Updates in real-time.
- **3D Spatial Map (left, lower):** ALICE's reconstructed 3D model of the desk, rendered in Three.js. Shows where objects are vs. where she *wants* them. Built during the wake-up scan, refined in real-time. The audience is seeing through her eyes.
- **Activity Feed (right):** What ALICE is doing/saying. Her voice output appears here. Minimal, sparse — mostly empty. When text appears, it matters.
- **Audience Requests (right, lower):** During Act 5, shows incoming requests and vote counts.
- **Status Bar (bottom):** ALICE's current state. Not "mode: active" — something warmer. A mood indicator (subtle, abstract). Session duration. Connection status.

**The keynote moment (Act 6):**
The dashboard is already visible throughout the demo. But in Act 6, it fills the screen. The panels animate into a tighter, more polished layout. The glass brain scales up. This is the product reveal — "this is what you'd interact with as a consumer."

---

## Implementation Phases

### Phase 1: Narrative Foundation
*Reframe existing systems without major code changes.*

- [ ] Rewrite `narration_prompts.py` — all first-person, short, dry
- [ ] Update Gemini system prompt in `narration.py` — ALICE's voice
- [ ] Restructure modes: merge Auto Tetris into Idle as personality behavior
- [ ] Hide Calibrate from demo flow (setup-only)
- [ ] Add idle micro-movements to arm controller
- [ ] Add Tetris-as-idle trigger logic (idle timeout → drift to keyboard)
- [ ] Write `logic/personality.py` skeleton — opinion strength, voice gate
- [ ] Update `alice.yaml` with personality parameters

### Phase 2: Intelligence Layer
*New capabilities that make ALICE feel aware.*

- [ ] Camera refactor — dual-camera setup (arm-mounted + front-facing), deprecate overhead
- [ ] Forward kinematics module — joint angles → camera 6DoF pose (SE(3) transform)
- [ ] Monocular depth estimation integration (ZoeDepth or Depth Anything v2)
- [ ] 3D spatial map pipeline (`vision/spatial_map.py`) — Open3D TSDF fusion from arm-cam + FK poses
- [ ] Wake-up scan routine — arm sweep path that builds initial 3D map
- [ ] Swap CNN block classifier → YOLO (ultralytics, pretrained COCO) for desk objects
- [ ] Presence detection via MediaPipe face/pose on front-facing camera (`vision/presence.py`)
- [ ] Object memory persistence in 3D coordinates (`brain/object_memory.py`)
- [ ] Desk layout presets in config (3D target positions)
- [ ] Personality engine — preference model, resistance thresholds (`logic/personality.py`)
- [ ] Movement dynamics wrapper (`hardware/dynamics.py`)
- [ ] Wire preference model into sort FSM → desk organization FSM

### Phase 3: Experience Design
*The demo arc and audience-facing systems.*

- [ ] Performance mode — single-arc demo runner with act sequencing
- [ ] Tea spill interaction choreography (partially scripted, partially emergent)
- [ ] Audience server reframe — desk layout voting, task requests
- [ ] Teaching mode reframe — Haptix as "show ALICE a routine"
- [ ] Dashboard redesign — glassmorphism components, new layout
- [ ] Glass brain visual polish for keynote moment
- [ ] Object memory panel, 3D spatial map view (Three.js rendering of ALICE's world model)
- [ ] Activity feed + ALICE voice output display

### Phase 4: Polish & Choreography
*Making it performance-ready.*

- [ ] End-to-end demo rehearsal and timing
- [ ] Movement personality tuning (speed curves, hesitation feel)
- [ ] Gemini prompt iteration (voice consistency, brevity enforcement)
- [ ] Dashboard animation polish (transitions, keynote moment)
- [ ] Audience interaction UX (mobile-friendly voting interface)
- [ ] Branding: logo, typography, color system
- [ ] Fallback behaviors for hardware issues during live demo
- [ ] Run full test suite, update tests for new modules
- [ ] Update README.md for new project identity

### Phase 5: Extended Features (Post-Demo)
*Nice-to-haves if time allows.*

- [ ] Multi-session personality continuity (ALICE remembers across demos)
- [ ] Adaptive Tetris difficulty (she gets better over time)
- [ ] Voice output via speaker (TTS for "fine." hits different out loud)
- [ ] Recording system → "ALICE learns a routine from demonstration"
- [ ] Mobile companion app concept (check on ALICE remotely)

---

## Open Questions

1. **Object detection model:** YOLO (ultralytics, COCO pretrained) is the current plan. Covers most desk objects out-of-the-box. May need fine-tuning for uncommon items (specific tools, custom objects). Evaluate whether stock COCO classes are sufficient or if a small fine-tuning pass is needed.

2. **3D reconstruction approach:** TSDF fusion via Open3D is the practical choice. Gaussian splatting (gsplat/nerfstudio) produces photorealistic results for the dashboard but is heavier to run. Decision: start with Open3D TSDF, evaluate gaussian splatting as a Phase 4 polish upgrade if GPU budget allows.

3. **Voice output modality:** Text on dashboard only? TTS through speaker? Both? TTS adds presence but risks breaking the "she speaks rarely" principle if the voice isn't right.

4. **Choreography vs. emergence:** How much of the demo should be scripted vs. driven by the personality engine? More scripted = reliable but rigid. More emergent = alive but risky for live demo.

5. **Audience interaction platform:** Keep WebSocket-based? Switch to something more accessible (QR code → mobile web page → vote)?

6. **Branding depth:** Is "ALICE" the final name or does the Detroit: Become Human connection need to be obscured for IP reasons? Does she need a logo, a typeface, a visual identity beyond the dashboard?

7. **Arm-mounted camera viewpoint:** Moving camera means constantly shifting perspective. YOLO handles varied angles, but the 3D map needs consistent quality. Evaluate whether the wake-up scan produces sufficient coverage, or if periodic re-scan routines are needed during operation.

---

## Success Criteria

The demo works when:

- Someone in the audience pulls out their phone to record the tea spill moment
- The Tetris at the end gets a different reaction than the Tetris at the beginning
- Someone asks "is she actually...?" and doesn't finish the sentence
- The dashboard makes someone say "I want that"
- Nobody describes it as "a robot arm demo" afterward — they say "I met ALICE"
