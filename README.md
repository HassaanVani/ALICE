# A.L.I.C.E.

**Adaptive Learning Interface for Cognitive Exploration**

The first thing on your desk that knows what's on your desk.

ALICE is a personal desk assistant — a robotic arm with computer vision, personality, and opinions. She sees real objects with YOLO, remembers where things belong across sessions, tidies your workspace, plays Tetris when she's bored, and has thoughts about where you put your tea.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           main.py                                    │
│                     Mode dispatch loop                               │
├──────────┬───────────┬───────────┬──────────┬────────────────────────┤
│  brain/  │  vision/  │   logic/  │hardware/ │       servers          │
│  CNN &   │ YOLO, cam │ desk org, │ arm, IK, │  tensor WS,            │
│  hooks   │ ArUco,    │ presets,  │ FK, grip │  puppet WS,            │
│          │ presence, │ memory,   │ per, mag │  audience WS           │
│          │ depth,    │ persona-  │ net, kin │                        │
│          │ spatial   │ lity, tea │ esthetic │                        │
├──────────┴───────────┴───────────┴──────────┴────────────────────────┤
│  dashboard/ (React + Three.js)      Haptix/ (hand tracking)         │
└──────────────────────────────────────────────────────────────────────┘
```

## What ALICE Can Do

- **See real objects** — YOLO detects cups, laptops, phones, books, and 15+ desk object categories in real-time
- **Remember her desk** — object memory persists across sessions; she notices what moved since last time
- **Organize your desk** — desk layout presets (studying, drawing, working, clean) drive autonomous pick-and-place
- **Have opinions** — personality engine tracks preferences, builds opinion strength, adjusts movement speed based on whether she chose the action or was told to do it
- **Play Tetris** — when idle, she drifts to the keyboard and plays. It's not a demo — she just wants to
- **React to people** — MediaPipe presence detection on the front camera; she knows when you arrive
- **Perceive in 3D** — monocular depth estimation + forward kinematics → 3D spatial map of the workspace
- **Perform** — a 6-act live demo arc that introduces her as a desk companion, not a tech demo

## Modes

### Idle
Default. ALICE watches the desk, runs subtle scanning movements, and drifts to Tetris when bored. Personality engine drives the idle behavior progression: watch → micro-motion → Tetris.

### Performance
The new REMODEL demo arc — a single continuous experience:
1. **She's Already Here** — mid-Tetris, notices someone approach
2. **She Knows This Desk** — wake-up scan, object recognition, memory comparison
3. **She Helps** — proactive desk tidying
4. **She Has Opinions** — tea interaction, preference enforcement, "told you"
5. **She Engages** — audience votes on desk layouts, ALICE complies or resists
6. **This Is Her** — dashboard keynote moment, return to idle

```
python main.py --mode performance
```

### Auto Sort
Autonomous block-sorting loop using ArUco markers and numbered blocks. Scrambles, solves, repeats.

### Auto Tetris
ALICE plays Tetris on a real computer by physically pressing keys on a keyboard.

### Demo (Legacy)
The original 5-act demo with block sorting, ghost replay, puppeteer, cyborg coop, and rebellion. Still works.

### Calibrate
Interactive pixel-to-arm-angle calibration via OpenCV.

### Puppeteer
Hand-tracking teleoperation via the Haptix MediaPipe bridge.

## Running

```bash
pip install -r requirements.txt

# Start in simulation (no hardware)
python main.py --simulate

# Performance mode (the new demo)
python main.py --mode performance --simulate

# Start with real hardware
python main.py --mode idle --arm-port /dev/ttyUSB0 --magnet-port /dev/ttyUSB1

# Enable recording
python main.py --mode performance --record
```

Configuration lives in `alice.yaml`. CLI flags and environment variables (prefixed `ALICE_`) override it.

## Services

| Service | Default Port | Purpose |
|---|---|---|
| Tensor Server | `ws://localhost:8765` | CNN activations, camera frames, state sync |
| Puppet Server | `ws://localhost:8766` | Hand pose ingestion, arm control, motion record/playback |
| Audience Server | `ws://localhost:8767` | Crowd voting (blocks + desk presets), reactions |

## Dashboard

```bash
cd dashboard && npm install && npm run dev
```

React + Three.js web UI: glass brain visualization, live camera feed, mode controls, sort/tetris dashboards, personality state.

## Haptix

```bash
cd Haptix && npm install && npm run dev
```

Hand-tracking 3D visualization. MediaPipe Hands → WebSocket → arm control.

## New Systems (REMODEL)

| System | Module | Purpose |
|---|---|---|
| YOLO Detection | `vision/yolo_detector.py` | Real desk object detection (17 COCO classes) |
| Presence Detection | `vision/presence.py` | MediaPipe face detection on front camera |
| Monocular Depth | `vision/monocular_depth.py` | Depth Anything v2 / MiDaS depth estimation |
| 3D Spatial Map | `vision/spatial_map.py` | Open3D TSDF volume integration |
| Object Memory | `logic/object_memory.py` | Cross-session object persistence (JSON) |
| Desk Presets | `logic/desk_presets.py` | Named desk layouts (studying, drawing, etc.) |
| Desk Organizer | `logic/desk_organizer.py` | FSM for autonomous desk tidying |
| Wake-up Scan | `logic/wake_scan.py` | Startup desk sweep with 3D integration |
| Tea Choreography | `logic/tea_choreography.py` | The keynote tea-spill interaction |
| Fist Bump | `logic/fist_bump.py` | Gesture-triggered fist bump response |
| Teaching | `logic/teaching.py` | "Show ALICE where things go" guided learning |
| Performance Mode | `modes/performance.py` | 6-act REMODEL demo arc |
| Personality Engine | `logic/personality.py` | Opinion strength, emotional states, voice gate |
| Movement Dynamics | `hardware/dynamics.py` | Personality-driven speed, hesitation, micro-motion |

## Tech Stack

Python, OpenCV, PyTorch, Ultralytics YOLO, MediaPipe, WebSockets, NumPy, SciPy, Open3D, Stable-Baselines3, React, Three.js, Vite

## Tests

```bash
python -m pytest tests/ -q
# 537 passed
```
