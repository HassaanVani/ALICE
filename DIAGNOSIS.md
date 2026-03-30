# ALICE Project Diagnosis & Status Report

**Generated:** 2026-03-30
**Branch:** `main` (latest: `ecf5c0a`)
**Last commit:** feat: voice commands, spatial moves, and trash zone

---

## Project Overview

**A.L.I.C.E. (Adaptive Learning Interface for Cognitive Exploration)** — a desk-mounted robot arm companion with personality, spatial memory, and opinions. Built on a MyPalletizer arm with dual cameras, YOLO v8 vision, and an LLM-driven first-person voice.

**Tagline:** *"The first thing on your desk that knows what's on your desk."*

---

## Codebase Metrics

| Metric | Value |
|--------|-------|
| Total Python files | 127 |
| Total Python LOC | 21,249 |
| Test files | 55 |
| Tests passing | 673 |
| Syntax errors | 0 |
| Open PRs | 0 |
| CI | GitHub Actions (Python 3.11 + 3.12) |

---

## Architecture

```
main.py (Dispatcher — mode loop + lifecycle)
├── brain/       7 files  — CNN model, inference, activation hooks
├── vision/     11 files  — YOLO, dual cameras, depth, spatial map, presence
├── hardware/   14 files  — arm controller, gripper, FK, dynamics, calibration
├── logic/      19 files  — personality, object memory, desk presets, organizer, interactions
├── modes/      10 files  — idle, performance, auto_sort, auto_tetris, calibrate, puppeteer
├── server.py            — Tensor WebSocket server (port 8765)
├── puppet_server.py     — Hand teleoperation server (port 8766)
├── audience_server.py   — Crowd voting server (port 8767)
├── narration.py         — LLM voice (Ollama / Gemini / rule-based)
├── voice_input.py       — Whisper STT + command parsing
├── state.py             — Central state manager
├── dashboard/           — React + Three.js frontend (glass brain, spatial map, activity feed)
└── Haptix/              — Hand tracking subsystem
```

**All packages have `__init__.py`** (brain, vision, hardware, logic, modes, tests). Dashboard is JS/React only.

---

## Development Phase

| Phase | Status | Highlights |
|-------|--------|------------|
| Phase 1: Narrative | COMPLETE | First-person voice, personality engine, movement dynamics |
| Phase 2: Intelligence | COMPLETE | YOLO v8, depth estimation, 3D spatial mapping, object memory, desk presets |
| Phase 3: Experience Design | COMPLETE | 6-act performance arc, tea choreography, teaching mode |
| Phase 4: Polish & Choreography | **IN PROGRESS** | Movement tuning, dashboard glassmorphism, demo rehearsal |
| Phase 5: Extended Features | PLANNED | TTS speaker output, voice interaction loop, mobile companion app |

**Current position: Early Phase 4.** Core systems are feature-complete. The most recent work (today) added voice commands, spatial moves ("move X near Y"), trash zone, and object interaction (fetch/hand_over/nudge/put_away).

---

## Recent Commit Velocity (last 5 commits, all today/yesterday)

| Commit | Feature | Tests Added |
|--------|---------|-------------|
| `ecf5c0a` | Voice commands, spatial moves, trash zone | +47 (673 total) |
| `418a023` | Object interaction: fetch, hand_over, nudge, put_away | +14 (626 total) |
| `238a673` | WebSocket migration to modern API | 0 (612 total) |
| `a4b8c5c` | Ollama local LLM backend | +20 (612 total) |
| `1a3210f` | ALICE-initiated fist bumps with personality | +11 (592 total) |

**Test growth:** 592 → 673 in last 5 commits (+81 tests)

---

## Code Health

### Strengths
- **Zero syntax errors** across all 127 Python files
- **Robust test suite** — 673 tests, 55 test files, growing with every feature
- **Clean package structure** — all modules properly packaged
- **Graceful degradation** — optional deps (MediaPipe, Open3D, Whisper) wrapped in try/except
- **No deprecation warnings** — websockets migration completed
- **CI green** — GitHub Actions matrix across Python 3.11 and 3.12
- **Config-driven** — YAML + CLI + ENV variable override chain

### Resolved Issues (from ISSUES.md)
All 25 tracked issues resolved:
- P0: Serial port race condition, glass brain memory leak, shutdown hangs
- P1: Arm connection fallback, WebSocket duplicates, reconnect logic
- P2: Gripper errors, Gemini blocking, back-pressure, Kalman thread-safety
- P3: Camera shutdown, config parsing, 12+ code quality items

### Remaining Items
- **Dashboard redesign** — glassmorphism UI documented in `dashboard/REDESIGN.md` but not yet implemented (Phase 4)
- **TTS speaker output** — planned for Phase 5
- **Mobile companion app** — planned for Phase 5
- **Performance mode rehearsal** — 6-act arc implemented but needs real-hardware tuning

---

## Dependencies

**Core (17 packages):** opencv-python, numpy, pyserial, torch, torchvision, websockets, gymnasium, pyyaml, scipy, stable-baselines3, pyttsx3, google-generativeai, mss, ultralytics, pytest, pytest-asyncio

**Optional (4 packages):** mediapipe, open3d, openai-whisper, sounddevice

All pinned with minimum versions. No known vulnerability flags.

---

## Key Systems Status

| System | Status | Notes |
|--------|--------|-------|
| Arm Controller | READY | Serial + simulation fallback |
| YOLO v8 Detection | READY | 17 COCO classes, YOLO sim for CI |
| Dual Camera | READY | Arm-mounted + front-facing |
| Monocular Depth | READY | Depth Anything v2 / MiDaS |
| 3D Spatial Map | READY | Open3D TSDF (optional dep) |
| Object Memory | READY | JSON persistence across sessions |
| Personality Engine | READY | Opinion strength, mood, emotional states |
| Movement Dynamics | READY | Speed curves, hesitation, micro-motions |
| Desk Organizer FSM | READY | scan → plan → execute → verify |
| Performance Mode | READY | 6-act demo arc |
| Tea Choreography | READY | 3-beat interaction |
| Fist Bump | READY | Reactive + proactive with personality |
| Object Interaction | READY | fetch, hand_over, nudge, put_away, move_near, throw_away |
| Voice Input | READY | Whisper STT + command parser |
| Narration (LLM) | READY | Ollama (default) / Gemini / rule-based |
| Tensor Server | READY | WebSocket, modern API |
| Puppet Server | READY | Hand teleoperation |
| Audience Server | READY | Crowd voting |
| Dashboard | NEEDS UPDATE | Functional but pre-redesign |

---

## Summary

ALICE is a mature, well-architected robotics project in **early Phase 4 (Polish)**. All core intelligence, perception, interaction, and personality systems are implemented and tested. The codebase is clean (0 syntax errors, 673 passing tests, all known issues resolved). The main remaining work is dashboard visual polish, real-hardware choreography tuning, and Phase 5 extended features (TTS output, mobile app). Development velocity is high — 5 feature commits with 81 new tests in the last 24 hours.
