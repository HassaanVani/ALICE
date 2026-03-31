# A.L.I.C.E.

**Adaptive Learning Interface for Cognitive Exploration**

The first thing on your desk that knows what's on your desk.

ALICE is a personal desk assistant — a robotic arm with computer vision, personality, and opinions. She sees real objects with YOLO, remembers where things belong across sessions, develops quirks from observing you, plays Tetris when she's bored, and communicates entirely through body language.

Runs fully offline. No cloud APIs required.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           main.py                                    │
│                     Mode dispatch loop                               │
├──────────┬───────────┬───────────┬──────────┬────────────────────────┤
│  brain/  │  vision/  │   logic/  │hardware/ │       servers          │
│  CNN &   │ YOLO, cam │ desk org, │ arm, IK, │  tensor WS (:8765)    │
│  hooks   │ presence, │ persona-  │ FK, grip │  puppet WS (:8766)    │
│          │ depth,    │ lity, tea │ per, mag │  audience WS (:8767)  │
│          │ spatial   │ curiosity,│ dynamics │                        │
│          │ hand det  │ habits,   │ calibr.  │                        │
│          │           │ gaze, llm │          │                        │
├──────────┴───────────┴───────────┴──────────┴────────────────────────┤
│  audio/ (servo sounds)        dashboard/ (React + Three.js)          │
│                               Haptix/ (hand tracking bridge)         │
└──────────────────────────────────────────────────────────────────────┘
```

## What ALICE Can Do

- **See real objects** — YOLO detects cups, laptops, phones, books, and 17 desk object categories
- **Remember her desk** — object memory persists across sessions; she notices what moved
- **Develop quirks** — the habit engine observes your patterns over time and develops emergent behaviors (not scripted)
- **Have opinions** — personality engine tracks preferences, builds opinion strength, adjusts movement based on agreement
- **Express emotion through movement** — body language overlays (droop, perk, bounce, lean) driven by emotional state and voice sentiment
- **Watch you** — gaze tracker smoothly follows your face and glances at interesting objects
- **Explore new things** — curiosity engine spikes when new objects appear, drives examination behaviors
- **Make sounds from her body** — servo micro-oscillations produce chirps, buzzes, hums (no speaker)
- **Think about how to move** — local LLM (llama3.2:3b) modulates movement personality every few seconds
- **Play Tetris** — when idle, she drifts to the keyboard and plays. It's not a demo — she just wants to
- **React to people** — MediaPipe presence detection; she knows when you arrive and watches you
- **Perceive in 3D** — monocular depth + forward kinematics → 3D spatial map of the workspace
- **Understand voice** — Whisper STT + command parsing (fetch, hand over, move near, throw away, organize)
- **Perform** — a 6-act live demo arc that introduces her as a desk companion

## Modes

### Idle
Default. ALICE watches the desk, tracks faces, examines new objects, executes learned habits, and drifts to Tetris when bored. Living behaviors (curiosity, gaze, habits, body language, sound effects) all run here.

### Performance
The REMODEL demo arc — a single continuous 6-act experience:
1. **She's Already Here** — mid-Tetris, notices someone approach
2. **She Knows This Desk** — wake-up scan, object recognition, memory comparison
3. **She Helps** — proactive desk tidying
4. **She Has Opinions** — tea interaction, preference enforcement, "told you"
5. **She Engages** — audience interaction
6. **This Is Her** — dashboard keynote moment, return to idle

### Auto Tetris
ALICE plays Tetris on a real computer by physically pressing keys on a keyboard.

### Calibrate
Interactive pixel-to-arm-angle calibration via OpenCV.

### Puppeteer
Hand-tracking teleoperation via the Haptix MediaPipe bridge.

## Running

```bash
pip install -r requirements.txt

# Start in simulation (no hardware)
python main.py --simulate

# Performance mode
python main.py --mode performance --simulate

# Start with real hardware
python main.py --mode idle --arm-port /dev/ttyUSB0 --magnet-port /dev/ttyUSB1

# Enable voice input (requires whisper + sounddevice)
# Set voice_input.enabled: true in alice.yaml

# Enable living behaviors
# Set living_behaviors.enabled: true in alice.yaml

# Enable LLM movement interpreter (requires Ollama + llama3.2:3b)
# Set llm_interpreter.enabled: true in alice.yaml
```

Configuration lives in `alice.yaml`. CLI flags and `ALICE_*` environment variables override it.

## Services

| Service | Default Port | Purpose |
|---|---|---|
| Tensor Server | `ws://localhost:8765` | CNN activations, camera frames, state sync, commands |
| Puppet Server | `ws://localhost:8766` | Hand pose ingestion, arm control, motion record/playback |
| Audience Server | `ws://localhost:8767` | State broadcasting, desk preset voting |

## Dashboard

```bash
cd dashboard && npm install && npm run dev
```

Apple keynote-style interface. Opens with "ALICE" in large glassmorphic text — click to zoom through into the dashboard. Three-column layout: camera + arm model | glass brain neural activity | sidebar with personality, living behaviors, object memory, LLM modifiers, system status.

Built with React 18, Three.js, Vite. No external UI libraries.

## Systems

| System | Module | What it does |
|---|---|---|
| **Personality** | `logic/personality.py` | Opinion strength, emotional states, voice gate, speed modifiers |
| **Body Language** | `logic/body_language.py` | Posture overlays (droop/perk/bounce/lean) from emotion + voice sentiment |
| **Gaze Tracker** | `logic/gaze_tracker.py` | Smooth face + object following via exponential interpolation |
| **Curiosity** | `logic/curiosity.py` | Novelty detection, examination behaviors, cross-session persistence |
| **Habits** | `logic/habits.py` | Pattern detection → emergent quirks (placement, sequence, relational) |
| **Sound Effects** | `audio/sound_effects.py` | Servo micro-oscillations (chirps, buzzes, hums from her body) |
| **LLM Interpreter** | `logic/llm_interpreter.py` | Local llama3.2:3b modulates speed, hesitation, posture, scan range |
| **Proactive** | `logic/proactive.py` | Orchestrates living behaviors during idle (examine, look, habits) |
| **Object Memory** | `logic/object_memory.py` | Cross-session object persistence (JSON) |
| **Object Interaction** | `logic/object_interaction.py` | Fetch, hand over, nudge, throw away, move near, auto cleanup |
| **Desk Organizer** | `logic/desk_organizer.py` | FSM for autonomous desk tidying (scan → plan → execute → verify) |
| **Tea Choreography** | `logic/tea_choreography.py` | The keynote tea-spill interaction ("told you.") |
| **Fist Bump** | `logic/fist_bump.py` | Gesture detection + reciprocation + personality-driven response |
| **YOLO Detection** | `vision/yolo_detector.py` | 17 COCO desk object classes, simulation fallback |
| **Presence** | `vision/presence.py` | MediaPipe face detection, distance estimation, face position |
| **Depth** | `vision/monocular_depth.py` | Depth Anything v2 / MiDaS monocular depth |
| **Spatial Map** | `vision/spatial_map.py` | Open3D TSDF volume 3D reconstruction |
| **Voice Input** | `voice_input.py` | Whisper STT + regex/LLM command parsing + sentiment detection |
| **Narration** | `narration.py` | Ollama/Gemini LLM voice (rare, gated by personality) |
| **Movement Dynamics** | `hardware/dynamics.py` | Speed curves, hesitation, easing, body language + LLM overlay |

## Hardware

- MyPalletizer 260 (4-axis arm)
- Parallel gripper (light)
- Arm-mounted webcam (ALICE's eyes)
- Front-facing webcam (presence detection)
- USB serial connection

All hardware has simulation fallback. Full CI runs without any physical devices.

## Offline

ALICE runs fully offline when using Ollama for narration and the LLM interpreter. No cloud APIs, no network required. YOLO weights and Whisper models are cached locally after first download.

## Tech Stack

Python, OpenCV, PyTorch, Ultralytics YOLO, MediaPipe, WebSockets, NumPy, SciPy, Open3D, pyttsx3, Ollama, React, Three.js, Vite

## Tests

```bash
python -m pytest tests/ -q
# 765 passed
```
