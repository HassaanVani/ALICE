# ALICE — Known Issues & Technical Debt

> **Status: All 25 original issues resolved.** WebSocket API migrated. Dashboard overhauled. Legacy code removed. This file is historical reference. New issues tracked in GitHub Issues.

## Current Known Issues

None.

---

## P0 — Critical (data corruption, crashes, hangs)

- [x] **Serial port race condition** — Added `threading.Lock` shared between `ArmController` and `MagnetDriver`. All serial I/O (`_send_command`, `set_compliant`, `toggle`) now acquires the lock. `main.py` passes the same lock to both. (`arm_controller.py`, `magnet_driver.py`, `main.py`)
- [x] **Glass brain material leak** — Rewrote `glass-brain.js` to use `InstancedMesh` (1 material + 1 instanced mesh per layer instead of 4096 individual meshes). Added `dispose()` hook. `scene-manager.js` now calls `sceneData.dispose()` + `scene.clear()` on switch. (`glass-brain.js`, `scene-manager.js`)
- [x] **Shutdown hangs forever** — `ALICE.run()` now stores task references with names. `shutdown()` cancels all tasks, uses `asyncio.wait()` with 5s timeout, force-cancels stragglers. (`main.py`)
- [x] **Arm connection failure doesn't enforce simulation** — When `arm.connect()` fails, `main.py` now recreates arm/magnet/gripper with `simulate=True` and sets `self.simulate = True`. (`main.py`)

## P1 — High (broken features, resource waste, silent failures)

- [x] **Dashboard opens 3 duplicate WebSocket connections** — Created `AliceSocketProvider` shared React context. All three hooks (`useAliceState`, `useTensorStream`, `useCameraStream`) now share a single WebSocket connection via context. (`dashboard/src/hooks/AliceSocketProvider.jsx`, `App.jsx`)
- [x] **Tensor bridge reconnect permanently broken** — Replaced destructive `maxReconnectAttempts = 0` with `_autoReconnect` flag (matching puppet-bridge pattern). Added exponential backoff and guard in reconnect timer. (`Haptix/src/tensor-bridge.js`)
- [x] **Gripper errors silently swallowed** — Wrapped all `gripper.close()`/`gripper.open()` calls in `_sort_loop` and `_rebellion_loop` with try/except + logging. (`main.py`)
- [x] **Blocking Gemini API in narration** — Added `asyncio.wait_for()` with 10s timeout around the `generate_content` call. Falls back to rule-based narration on timeout. (`narration.py`)
- [x] **No back-pressure on WebSocket broadcasts** — Added per-client bounded `asyncio.Queue` (max 8 frames). Slow clients get oldest frames dropped instead of causing server memory buildup. (`server.py`)

## P2 — Medium (concurrency, error handling, robustness)

- [x] **Kalman filter not thread-safe** — Added `threading.Lock` to `BlockTracker`. All predict/correct/prune operations in `update()` are now serialized under the lock. (`vision/tracker.py`)
- [x] **State manager listeners can crash each other** — Already had per-listener try/except in `_notify()`. Verified and confirmed working. (`state.py`)
- [x] **Camera threads hold locks during daemon shutdown** — Replaced `daemon=True` with `daemon=False` + `threading.Event` for clean cooperative shutdown. `stop()` sets the event and joins with timeout. (`vision/camera.py`)
- [x] **Empty except blocks in server.py and audience_server.py** — Added `logger.debug()` logging for `json.JSONDecodeError` in both files. (`server.py`, `audience_server.py`)
- [x] **Calibration data not validated on load** — Added `_validate_point()` that checks pixel coords are within image bounds and arm angles are in [0, 180]. Invalid points are dropped with a warning. (`hardware/calibration.py`)
- [x] **No connection status UI in dashboard** — Shared WebSocket provider exposes single `connected` state. Added a "Disconnected — data may be stale" banner to the dashboard when connection drops. (`App.jsx`, `AliceSocketProvider.jsx`)
- [x] **cv2 window not closed in exception path** — Wrapped calibration mode loop in try/finally so `cv2.destroyAllWindows()` always runs. (`main.py`)
- [x] **File upload in Haptix has no validation** — Added file type check (`.glb`, `.gltf`, `.obj`, `.fbx`, `.stl`) and 50 MB size limit with user-facing error messages. (`Haptix/src/main.js`)

## P3 — Low (dead code, config, code quality)

- [x] **Dead `move_to_async()` in arm_controller.py** — Removed. (`hardware/arm_controller.py`)
- [x] **Dead `onFreeze()`/`onLayerNav()` in gesture-controller.js** — Removed unwired callback setters. (`Haptix/src/gesture-controller.js`)
- [x] **Unused logger in puppet_ik.py** — Logger IS used at line 306; consolidated inline `logging.getLogger("TeachingRecorder")` call to use the module-level logger. (`hardware/puppet_ik.py`)
- [x] **`MotionPlayer._on_complete` never cleared after firing** — Now sets `self._on_complete = None` after invoking the callback to release references. (`hardware/puppet_ik.py`)
- [x] **Hardcoded workspace bounds** — `ChimpSortFSM` now accepts `sorted_zone` and `drop_zone` as constructor parameters (with existing defaults). Slot width is computed dynamically from zone width and block count. (`logic/sort_logic.py`)
- [x] **Block count assumed 16** — Extracted `NUM_BLOCKS` module constant. `ChimpSortFSM` accepts `num_blocks` parameter. All range checks, sorted checks, and slot computations use it. `ChimpSortEnv` already used `NUM_BLOCKS` constant. (`logic/sort_logic.py`, `logic/sort_env.py`)
- [x] **Gesture thresholds are magic numbers** — Constructor now accepts an optional `thresholds` config object to override all distance thresholds (pinchClose, cursorThreshold, fullPinch, reloadDist, holdTime, zoomCooldown, panThreshold). (`Haptix/src/gesture-controller.js`)
- [x] **Sleep durations not configurable** — Added `timing` section to `alice.yaml` and `TimingConfig` dataclass (`idle_loop_s`, `sort_loop_s`, `camera_poll_s`). All mode loop sleeps in `main.py` now use config values. (`config.py`, `alice.yaml`, `main.py`)
- [x] **No keyboard event listener cleanup in Haptix** — Stored bound handler references. Added `destroy()` method that removes keydown/keyup listeners. (`Haptix/src/main.js`)
- [x] **No requestAnimationFrame cleanup** — Stored `_rafId`. `destroy()` calls `cancelAnimationFrame()`. (`Haptix/src/main.js`)
- [x] **Inconsistent error handling across mode loops** — The `_mode_loop()` dispatch already catches all exceptions per-iteration with logging and continues. Individual mode methods' errors are caught uniformly. (`main.py`)
- [x] **Config env var parsing lowercases port strings** — Added `_string_only` set for port and mode env vars. These skip boolean/int coercion entirely, preserving original casing. (`config.py`)
- [x] **Global RNG not seeded** — `ChimpSortEnv.__init__()` now accepts an optional `seed` parameter passed to `np.random.default_rng()`. `reset(seed=...)` continues to work as before. (`logic/sort_env.py`)
