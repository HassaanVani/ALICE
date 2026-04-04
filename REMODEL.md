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

### What was added (all implemented)

#### 1. Presence Detection ✓
- `vision/presence.py` — MediaPipe face detection on front-facing camera
- Triggers idle → active transition via `PersonalityEngine.set_presence()`
- Distance estimation from face bbox size, "looking at desk" heuristic

#### 2. Object Memory + 3D Spatial Map ✓
- `logic/object_memory.py` — JSON persistence of recognized objects + preferred positions
- `vision/spatial_map.py` — Open3D TSDF volume integration (FK pose + monocular depth)
- `vision/monocular_depth.py` — Depth Anything v2 / MiDaS per-frame depth maps
- Builds and refines over sessions — ALICE remembers where things were

#### 3. Desk Layout Presets ✓
- `logic/desk_presets.py` — 4 built-in presets: studying, drawing, working, clean
- Each defines target positions by YOLO label with priority and zone
- ALICE picks presets based on her own preferences during Act 5
- Custom presets via `register_preset()`

#### 4. Personality Engine ✓
- `logic/personality.py` — `PersonalityEngine` with `EmotionalState`, `ActionOrigin`, `ObjectPreference`
- Inputs: object positions, user actions, override history, idle duration, presence
- Outputs: speed multiplier, hesitation duration, voice gate signal, idle behavior
- All parameters configurable in `alice.yaml` under `personality:`

#### 5. Movement Dynamics ✓
- `hardware/dynamics.py` — `MovementDynamics` wraps `ArmController`
- Personality-driven speed, hesitation, micro-motion, settle, urgent moves
- Idle micro-movements (sinusoidal drift on base joint, orient toward interest)

#### 6. First-Person Voice ✓
- Gemini system prompt rewritten for ALICE's first-person voice
- Voice gate via `PersonalityEngine.should_speak()` — silence is default
- Speech cooldown, topic deduplication, flow-state suppression
- `narration.py` + `narration_prompts.py` updated

#### 7. Additional Systems ✓
- `logic/desk_organizer.py` — FSM for autonomous desk tidying (scan→plan→execute→verify)
- `logic/wake_scan.py` — startup desk sweep with YOLO + depth + memory integration
- `logic/tea_choreography.py` — 3-beat tea interaction (warning → override → "told you")
- `logic/fist_bump.py` — gesture-triggered fist bump response
- `logic/teaching.py` — "show ALICE where things go" guided learning
- `modes/performance.py` — 6-act REMODEL demo arc runner
- `vision/yolo_detector.py` — YOLO v8 for real desk object detection (17 classes)
- `hardware/forward_kinematics.py` — DH-based FK with camera SE(3) pose
- `hardware/gripper.py:ParallelGripper` — proportional gripper with personality-aware gripping

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

### Phase 1: Narrative Foundation ✓ COMPLETE
*Reframe existing systems without major code changes.*

- [x] Rewrite `narration_prompts.py` — all first-person, short, dry
- [x] Update Gemini system prompt in `narration.py` — ALICE's voice
- [x] Restructure modes: merge Auto Tetris into Idle as personality behavior
- [x] Hide Calibrate from demo flow (setup-only)
- [x] Add idle micro-movements to arm controller → `hardware/dynamics.py`
- [x] Add Tetris-as-idle trigger logic (idle timeout → drift to keyboard) → `modes/idle.py`
- [x] Write `logic/personality.py` — opinion strength, voice gate, emotional states
- [x] Update `alice.yaml` with personality parameters

### Phase 2: Intelligence Layer ✓ COMPLETE
*New capabilities that make ALICE feel aware.*

- [x] Camera refactor — dual-camera (arm-mounted + front-facing), OVERHEAD alias → `vision/camera.py`
- [x] Forward kinematics module — joint angles → SE(3) camera pose → `hardware/forward_kinematics.py`
- [x] Monocular depth estimation (Depth Anything v2 / MiDaS) → `vision/monocular_depth.py`
- [x] 3D spatial map pipeline — Open3D TSDF fusion → `vision/spatial_map.py`
- [x] Wake-up scan routine — 6-waypoint desk sweep → `logic/wake_scan.py`
- [x] YOLO swap — ultralytics COCO for desk objects → `vision/yolo_detector.py`
- [x] Presence detection — MediaPipe face on front camera → `vision/presence.py`
- [x] Object memory persistence — JSON across sessions → `logic/object_memory.py`
- [x] Desk layout presets (studying, drawing, working, clean) → `logic/desk_presets.py`
- [x] Personality engine — preferences, resistance, emotional states → `logic/personality.py`
- [x] Movement dynamics wrapper — speed/hesitation/micro-motion → `hardware/dynamics.py`
- [x] Desk organization FSM (scan → plan → execute) → `logic/desk_organizer.py`
- [x] Parallel gripper driver → `hardware/gripper.py:ParallelGripper`

### Phase 3: Experience Design ✓ COMPLETE
*The demo arc and interaction systems.*

- [x] Performance mode — 6-act arc runner → `modes/performance.py`
- [x] Tea spill choreography (3-beat: warning → override → "told you") → `logic/tea_choreography.py`
- [x] Teaching mode reframe — "show ALICE where things go" → `logic/teaching.py`
- [x] Fist bump interaction → `logic/fist_bump.py`
- [x] Dashboard redesign plan → `dashboard/REDESIGN.md`
- [ ] Dashboard glassmorphism implementation (planned, see `dashboard/REDESIGN.md`)
- [ ] Glass brain visual polish for keynote moment
- [ ] Object memory panel + 3D spatial map Three.js view
- [ ] Activity feed + ALICE voice output display

### Phase 4: Polish & Choreography
*Making it performance-ready.*

- [x] Run full test suite — 537 tests passing
- [x] Update README.md for new project identity
- [ ] End-to-end demo rehearsal and timing
- [ ] Movement personality tuning (speed curves, hesitation feel)
- [ ] Gemini prompt iteration (voice consistency, brevity enforcement)
- [ ] Dashboard animation polish (transitions, keynote moment)
- [ ] Audience interaction UX (mobile-friendly voting interface)
- [ ] Branding: logo, typography, color system
- [ ] Fallback behaviors for hardware issues during live demo

### Phase 5: Extended Features (Post-Demo)
*Nice-to-haves if time allows.*

- [x] Multi-session personality continuity — `logic/object_memory.py` persists across sessions
- [ ] Adaptive Tetris difficulty (she gets better over time)
- [ ] Voice output via speaker (TTS for "fine." hits different out loud)
- [x] Teaching system → "ALICE learns from demonstration" via `logic/teaching.py`
- [ ] Mobile companion app concept (check on ALICE remotely)

---

## Open Questions (Updated)

1. ~~**Object detection model:**~~ **Resolved.** YOLO v8 nano (ultralytics, COCO pretrained) implemented in `vision/yolo_detector.py`. 17 desk-relevant COCO classes filtered via `DESK_OBJECTS` dict. Stock classes cover cup, laptop, phone, book, bottle, keyboard, scissors, and more. Fine-tuning deferred — stock coverage is sufficient for the demo.

2. ~~**3D reconstruction approach:**~~ **Resolved.** Open3D TSDF implemented in `vision/spatial_map.py`. Gaussian splatting remains a Phase 4 upgrade option.

3. **Voice output modality:** Text on dashboard + pyttsx3 TTS available. Decision on speaker output deferred to Phase 4 rehearsals.

4. ~~**Choreography vs. emergence:**~~ **Resolved.** Hybrid approach implemented. Tea choreography (`logic/tea_choreography.py`) is partially scripted, partially driven by personality engine opinion strength. Performance mode (`modes/performance.py`) sequences the 6 acts but individual interactions within acts are emergent.

5. **Audience interaction platform:** WebSocket-based, retained. Audience page at `dashboard/src/pages/Audience.jsx`. Preset voting added alongside block voting. QR code → mobile web remains a Phase 4 UX task.

6. **Branding depth:** ALICE name kept. Logo/typeface deferred to Phase 4.

7. ~~**Arm-mounted camera viewpoint:**~~ **Resolved.** Wake-up scan (`logic/wake_scan.py`) sweeps 6 waypoints to build initial coverage. Ongoing integration during normal operation refines the map. YOLO handles varied angles well.

---

## Success Criteria

The demo works when:

- Someone in the audience pulls out their phone to record the tea spill moment
- The Tetris at the end gets a different reaction than the Tetris at the beginning
- Someone asks "is she actually...?" and doesn't finish the sentence
- The dashboard makes someone say "I want that"
- Nobody describes it as "a robot arm demo" afterward — they say "I met ALICE"
