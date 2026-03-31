# ALICE Project Diagnosis

**Last updated:** 2026-03-31

## Metrics

| Metric | Value |
|--------|-------|
| Python source files | 72 |
| Test files | 58 |
| Tests passing | 765 |
| Total Python LOC | ~23,500 |
| Syntax errors | 0 |
| Deprecation warnings | 0 |
| Open issues | 0 |

## Phase Status

| Phase | Status |
|-------|--------|
| Phase 1: Narrative & Personality | Complete |
| Phase 2: Intelligence (YOLO, depth, memory) | Complete |
| Phase 3: Experience Design (6-act arc, tea, fist bumps) | Complete |
| Phase 4: Living Behaviors & Polish | **Complete** |
| Phase 5: Dashboard Overhaul & Refinement | **In Progress** |

## Architecture

```
brain/       6 files   CNN inference, hooks, training
vision/     10 files   YOLO, camera, presence, depth, spatial, hand, tracker, screen
logic/      20 files   personality, body language, gaze, curiosity, habits, proactive,
                       llm interpreter, object interaction/memory, desk organizer,
                       presets, tea choreography, fist bump, teaching, tetris, fallbacks
hardware/   13 files   arm controller, FK/IK, gripper, dynamics, calibration, keyboard
audio/       1 file    servo sound effects
modes/       5 files   idle, performance, auto_tetris, calibrate, puppeteer
servers      3 files   tensor (8765), puppet (8766), audience (8767)
dashboard/  10 files   React + Three.js (hero screen, glass brain, 3D arm, sidebar panels)
```

## Recent Work (2026-03-30 — 2026-03-31)

- **Living behaviors**: Gaze tracking, curiosity engine, learned habits, body language overlays, servo sound effects, proactive engagement orchestrator. 101 new tests.
- **LLM movement interpreter**: Local llama3.2:3b modulates movement personality (speed, hesitation, posture, scan range) every 4 seconds. 31 new tests.
- **Legacy cleanup**: Removed block sorting (ChimpSortFSM), old demo mode, ArUco detector, RL models, 13 orphan Haptix scenes. -4,610 lines.
- **Dashboard overhaul**: Apple keynote aesthetic. Hero screen with glassmorphic ALICE text and zoom-through animation. Consumer-facing 3-column layout. Removed 12 dead components. -2,711 lines of dead UI.
- **Voice sentiment**: Keyword-based praise/scold detection feeds body language posture reactions.
- **Emotion listener system**: PersonalityEngine notifies body language on emotional state changes.

## What's Production-Ready

- Arm control (MyPalletizer) with simulation fallback
- YOLO v8 object detection (17 COCO classes)
- Monocular depth estimation + 3D spatial map
- Object memory (cross-session persistence)
- Personality engine (opinions, emotions, voice gate)
- Living behaviors (gaze, curiosity, habits, body language, servo sounds)
- LLM movement interpreter (local Ollama, graceful no-op when unavailable)
- Voice input (Whisper STT + command parsing + sentiment detection)
- Narration (Ollama local LLM, first-person voice)
- Object interaction (fetch, hand over, nudge, throw away, move near, auto cleanup)
- Teleoperation (MediaPipe Hands → inverse kinematics)
- All 5 behavior modes (Idle, Performance, Auto Tetris, Calibrate, Puppeteer)
- 3 WebSocket servers with modern API
- Dashboard (React + Three.js, hero screen, live state)
- Recording/playback (session capture + replay)
- Full offline operation (Ollama + cached YOLO/Whisper weights)

## What Remains

- Hardware choreography tuning (movement timings on physical MyPalletizer)
- Dashboard spatial map panel (3D point cloud visualization)
- TTS audio playback refinement
- Mobile companion interface
- Full performance mode rehearsal on hardware
