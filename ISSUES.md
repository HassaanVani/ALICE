# ALICE — Known Issues & Technical Debt

## P0 — Critical (data corruption, crashes, hangs)

- [x] **Serial port race condition** — Added `threading.Lock` shared between `ArmController` and `MagnetDriver`. All serial I/O (`_send_command`, `set_compliant`, `toggle`) now acquires the lock. `main.py` passes the same lock to both. (`arm_controller.py`, `magnet_driver.py`, `main.py`)
- [x] **Glass brain material leak** — Rewrote `glass-brain.js` to use `InstancedMesh` (1 material + 1 instanced mesh per layer instead of 4096 individual meshes). Added `dispose()` hook. `scene-manager.js` now calls `sceneData.dispose()` + `scene.clear()` on switch. (`glass-brain.js`, `scene-manager.js`)
- [x] **Shutdown hangs forever** — `ALICE.run()` now stores task references with names. `shutdown()` cancels all tasks, uses `asyncio.wait()` with 5s timeout, force-cancels stragglers. (`main.py`)
- [x] **Arm connection failure doesn't enforce simulation** — When `arm.connect()` fails, `main.py` now recreates arm/magnet/gripper with `simulate=True` and sets `self.simulate = True`. (`main.py`)

## P1 — High (broken features, resource waste, silent failures)

- [ ] **Dashboard opens 3 duplicate WebSocket connections** — `useAliceState`, `useTensorStream`, `useCameraStream` each independently connect to the same `TENSOR_WS_URL`. Should consolidate into a single shared WebSocket provider/context. (`dashboard/src/hooks/`)
- [ ] **Tensor bridge reconnect permanently broken** — `tensor-bridge.js` sets `maxReconnectAttempts = 0` on disconnect (destructive). Unlike puppet-bridge which uses `_autoReconnect` flag, tensor bridge can never reconnect after intentional disconnect. (`Haptix/src/tensor-bridge.js`)
- [ ] **Gripper errors silently swallowed** — `_sort_loop` and `_rebellion_loop` call `gripper.close()`/`gripper.open()` with no error checking. If gripper fails mid-sort, robot continues with no block. (`main.py`)
- [ ] **Blocking Gemini API in narration** — `narration.py` calls Gemini API via `asyncio.to_thread()` with no timeout. If API hangs, narration loop stalls indefinitely. (`narration.py`)
- [ ] **No back-pressure on WebSocket broadcasts** — `server.py` broadcasts tensor frames at full rate with no per-client queuing. Slow dashboard client causes server memory buildup. (`server.py`)

## P2 — Medium (concurrency, error handling, robustness)

- [ ] **Kalman filter not thread-safe** — `TrackedBlock.predict()`/`.correct()` mutate internal state from main loop, but camera threads could trigger updates concurrently. (`vision/tracker.py`)
- [ ] **State manager listeners can crash each other** — If one listener callback throws, other listeners in the chain may not get called. Needs per-listener try/except. (`state.py`)
- [ ] **Camera threads hold locks during daemon shutdown** — Camera threads are `daemon=True` but hold GIL-related locks that can deadlock during process termination. (`vision/camera.py`)
- [ ] **Empty except blocks in server.py and audience_server.py** — `json.JSONDecodeError` caught and silently dropped with no logging. (`server.py`, `audience_server.py`)
- [ ] **Calibration data not validated on load** — `CalibrationManager.load()` deserializes points without checking if pixel coords are within image bounds or arm angles are valid. (`hardware/calibration.py`)
- [ ] **No connection status UI in dashboard** — All three React hooks silently reconnect. User has no idea they're looking at stale data. (`dashboard/src/hooks/`)
- [ ] **cv2 window not closed in exception path** — Calibration mode can leak an OpenCV window if exception occurs before `destroyAllWindows()`. (`main.py`)
- [ ] **File upload in Haptix has no validation** — Accepts any file for custom model upload with no size/type checks. (`Haptix/src/main.js`)

## P3 — Low (dead code, config, code quality)

- [ ] **Dead `move_to_async()` in arm_controller.py** — Never called anywhere.
- [ ] **Dead `onFreeze()`/`onLayerNav()` in gesture-controller.js** — Callback setters never wired.
- [ ] **Unused logger in puppet_ik.py** — `import logging` + `logger` defined but never used.
- [ ] **`MotionPlayer._on_complete` never cleared after firing** — Can retain references to large objects.
- [ ] **Hardcoded workspace bounds** — Drop zones in `sort_logic.py` tied to specific table size.
- [ ] **Block count assumed 16** — Hardcoded across `sort_logic.py`, `sort_env.py`.
- [ ] **Gesture thresholds are magic numbers** — Not adaptive to hand size. (`gesture-controller.js`)
- [ ] **Sleep durations not configurable** — 0.1s, 0.033s, 0.016s scattered through mode loops. (`main.py`)
- [ ] **No keyboard event listener cleanup in Haptix** — Listeners accumulate if app reinits. (`main.js`)
- [ ] **No requestAnimationFrame cleanup** — Keyboard tick loop never cancelled. (`main.js`)
- [ ] **Inconsistent error handling across mode loops** — Some have try/except, some don't.
- [ ] **Config env var parsing lowercases port strings** — Breaks serial port names with uppercase. (`config.py`)
- [ ] **Global RNG not seeded** — `np.random.default_rng()` in `sort_env.py` is non-deterministic.
