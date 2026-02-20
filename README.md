# A.L.I.C.E.

**Adaptive Learning Interface for Cognitive Exploration**

A modular AI robotics platform that uses computer vision, a 5-axis robotic arm, and audience interaction to sort, play, and perform — live.

ALICE detects numbered blocks on a table using an overhead camera and ArUco markers, runs them through a CNN for recognition, and drives a robotic arm to manipulate them. A React + Three.js dashboard streams neural activations in real time, and a hand-tracking interface (Haptix) lets a human puppeteer the arm with their bare hand.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        main.py                           │
│                    Mode dispatch loop                    │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│  brain/  │ vision/  │  logic/  │hardware/ │   servers    │
│  CNN &   │ cameras, │ sort FSM,│ arm, mag-│ tensor WS,   │
│  hooks   │ ArUco,   │ tetris   │ net, IK, │ puppet WS,   │
│          │ tracker  │ agent,RL │ gripper  │ audience WS  │
├──────────┴──────────┴──────────┴──────────┴──────────────┤
│  dashboard/ (React + Three.js)    Haptix/ (hand tracking)│
└──────────────────────────────────────────────────────────┘
```

## Modes

ALICE has six operating modes. Switch between them at runtime from the dashboard or via WebSocket command.

### Idle

The default startup mode. ALICE streams camera frames and CNN activations to the dashboard but takes no physical action. Use this to verify the video feed, inspect neural activations, or wait for the operator to pick a mode.

```
python main.py                      # starts in idle (default)
python main.py --mode idle
```

### Auto Sort

A fully autonomous loop with no human involvement. ALICE repeatedly:

1. **Scrambles** — picks up each of the 16 numbered blocks and drops them in random positions.
2. **Solves** — detects every block, plans an optimal ordering, and picks-and-places them into the sorted zone in sequence (1 through 16).
3. **Pauses** — waits a few seconds, then starts the next cycle.

The sort FSM tracks move count, duration, and efficiency score (optimal is 16 moves). If an RL agent (`brain/weights/sort_agent.zip`) is available, it's used for target selection; otherwise the FSM falls back to a greedy heuristic.

```
python main.py --mode auto_sort
```

### Auto Tetris

ALICE plays Tetris on a real computer — physically. An overhead screen reader captures the game board from a running tetr.io session, the Tetris agent evaluates all possible placements using height/hole/bumpiness heuristics, and the robotic arm presses keys on a physical keyboard to execute moves (left, right, rotate, drop).

Key positions are loaded from a calibration file (`tetris_key_calibration.json`). The arm literally reaches over and taps the keys.

```
python main.py --mode auto_tetris
```

### Demo

A scripted 5-act live performance designed for an audience. Each act demonstrates a different level of human-AI collaboration:

**Act 1 — Human Benchmark.** The blocks are auto-scrambled, then a human sorts them by hand while ALICE watches and records every move (block ID, positions, timestamps).

**Act 2 — Ghost Replay.** ALICE replays the human's exact sorting strategy move-for-move with the robotic arm — a "ghost" of the human's performance.

**Act 3 — Puppeteer.** The operator switches to Puppeteer mode (see below). A volunteer controls the arm with their hand via Haptix. When done, the operator switches back to Demo mode to continue.

**Act 4 — Cyborg Cooperation.** The blocks are scrambled again. Now a live audience votes (via their phones) on which block the robot should move next. ALICE picks up the crowd's chosen block and places it. Human crowd + robot arm work together.

**Act 5 — Rebellion.** One final scramble. The audience keeps voting, but ALICE computes its own optimal move. When the crowd's vote disagrees with the optimal choice, ALICE overrides them — and the narration system calls it out in real time. The robot "rebels" against its human operators.

After Act 5, the demo resets and can be run again.

```
python main.py --mode demo
```

### Calibrate

An interactive OpenCV window for mapping pixel coordinates to arm joint angles. The operator:

1. Moves the arm to hover over a detected block.
2. Presses **C** to record the calibration point (pixel position + current arm angles).
3. Repeats for several blocks across the workspace.
4. Presses **S** to save the calibration to `calibration_data.json`.
5. Presses **Q** to exit.

This calibration data is used by all other modes to translate "block at pixel (x, y)" into "move arm to angles (base, shoulder, elbow, wrist_pitch, wrist_roll)".

```
python main.py --mode calibrate
```

### Puppeteer

Teleoperation mode. A human controls the robotic arm in real time using hand gestures tracked by the Haptix web app (MediaPipe Hands + WebSocket bridge):

- **Hand position** maps to arm position via inverse kinematics.
- **Pinch gesture** closes the gripper (picks up a block).
- **Open hand** releases the gripper.

The puppet server supports recording and playback of hand sessions, and broadcasts "neural activations" (encoded arm + gripper state) to the dashboard so viewers see the arm's internal state update live.

Kinesthetic teaching is also available in this mode — put the arm in compliant mode, physically guide it, and record the joint trajectory for later replay.

```
python main.py --mode puppeteer
```

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Start in simulation (no hardware required)
python main.py --simulate

# Start with real hardware
python main.py --mode auto_sort --arm-port /dev/ttyUSB0 --magnet-port /dev/ttyUSB1

# Enable session recording
python main.py --mode demo --record

# Replay a recorded session
python main.py --replay recordings/session_001.jsonl.gz
```

Configuration lives in `alice.yaml`. CLI flags and environment variables (prefixed `ALICE_`) override it.

## Services

| Service | Default Port | Purpose |
|---|---|---|
| Tensor Server | `ws://localhost:8765` | CNN activation streaming, camera frames, state sync |
| Puppet Server | `ws://localhost:8766` | Hand pose ingestion, arm control, motion record/playback |
| Audience Server | `ws://localhost:8767` | Crowd voting, reaction broadcasting, phase labels |

## Dashboard

```bash
cd dashboard && npm install && npm run dev
```

React + Three.js web UI with live camera feed, CNN activation visualization, a 3D simulated arm, mode controls, and recording management.

## Haptix

```bash
cd Haptix && npm install && npm run dev
```

Hand-tracking 3D visualization platform. Uses MediaPipe Hands to detect gestures in the browser, bridges to the puppet server for arm control, and renders 16 interactive Three.js scenes (glass brain, robotic arm, DNA helix, molecules, and more).

## Tech Stack

Python, OpenCV, PyTorch, WebSockets, NumPy, SciPy, Stable-Baselines3, MediaPipe, React, Three.js, Vite
