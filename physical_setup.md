# ALICE — Physical Setup for Booth Demo

## What You're Building

A desk with a robotic arm, scattered real objects (mug, notebook, pens, phone), two cameras, and a keyboard for Tetris. Behind it, a screen shows ALICE's glass brain and dashboard. The audience participates from their phones. ALICE speaks for herself.

**Booth flow**: ALICE is already playing Tetris when people approach — she's mid-game, not waiting. When someone stops, she notices (presence detection) and turns to them. When a crowd gathers, run the full 6-act Performance mode.

```
┌─────────────────────────────────────────────────┐
│                  PROJECTION / TV                 │
│             (Dashboard — glass brain +           │
│              spatial map + personality)           │
└─────────────────────────────────────────────────┘

    ┌────────────────────────────────────┐
    │                                    │
    │  📸 (front camera, facing audience)│
    │                                    │
    │   ☕ 📓 🖊️  🦾 ARM  📱 📖       │  ← real desk objects
    │              (📷 arm-mounted cam)  │
    │                                    │
    │            ⌨️ KEYBOARD              │  ← for Tetris (arm presses keys)
    └────────────────────────────────────┘

    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  LAPTOP  │   │ MONITOR  │   │ TETRIS   │
    │ (backend │   │(dashboard│   │ SCREEN   │
    │  + dash) │   │ operator)│   │(tetr.io) │
    └──────────┘   └──────────┘   └──────────┘

    📱📱📱📱📱  ← audience phones (vote on desk layouts)
```

---

## Shopping List

Everything you need to buy, with specific products and approximate prices.

### Robotic Arm

ALICE needs a 5-6 DOF serial-controllable arm with ~25-30cm reach and enough payload for 30g blocks + an electromagnet (~80g total). Budget options exist from $90 to $650.

| Arm | Price | DOF | Reach | Payload | Control | Verdict |
|-----|-------|-----|-------|---------|---------|---------|
| **Hiwonder xArm ESP32** | $190-230 | 6 | ~28cm | 500g | ESP32 + USB + WiFi + BT | **Best overall pick** — open-source ESP32 with GPIO for electromagnet, Python via `xarm` PyPI lib, bus servos with position feedback, active community |
| Hiwonder xArm 1S | $200-240 | 6 | ~25cm | 500g | ARM CPU + USB HID + BT | Proven alternative — same servos, same Python lib, no WiFi/GPIO expansion |
| Hiwonder xArm 2.0 | $330 | 6 | ~28cm | 500g | ESP32 + STM32 dual | Newest, upgraded servos, most refined — pricier |
| LewanSoul LeArm 6DOF | $90-120 | 6 | ~22cm | ~200g | Arduino + USB serial | Cheapest option — basic PWM servos, no feedback, lower payload — good for prototyping only |
| Yahboom DOFBOT | $329-454 | 6 | ~28cm | ~400g | Raspberry Pi + ROS | Great if you want ROS — requires a Pi, has built-in block-stacking tutorials |
| Elephant Robotics myCobot 280 | $649 | 6 | 28cm | 250g | M5Stack + Python SDK + ROS | Professional-grade cobot, best quality, most expensive |

**Recommendation: Hiwonder xArm ESP32 (assembled, ~$230)**

- Buy assembled: [Hiwonder Official Store](https://www.hiwonder.com/products/xarm-esp32) or Amazon
- Python control via `pip install xarm` — sends angle commands over USB HID
- ESP32 GPIO pins can drive the electromagnet through a MOSFET (no separate serial needed)
- LX-15D/LX-225 bus servos provide position readback for closed-loop control

### Electromagnet

A small 5V electromagnet picks up the blocks. At 2.5kg holding force, it is ~80x stronger than needed for 30g blocks.

| Product | Price | Force | Weight | Where |
|---------|-------|-------|--------|-------|
| **Adafruit 5V Electromagnet P20/15** | $7.50 | 2.5kg | 22.7g | [Adafruit](https://www.adafruit.com/product/3872), Amazon |
| Adafruit 5V Electromagnet P25/20 | $9.95 | 5kg | 55.3g | [Adafruit](https://www.adafruit.com/product/3873) |

**Recommendation: P20/15 ($7.50)** — lighter (22.7g vs 55.3g), cheaper, plenty of force.

You also need an **N-channel MOSFET** (IRLZ44N or 2N7000, ~$1) and a **flyback diode** (1N4001, ~$0.10) to switch it from a GPIO pin. Any electronics starter kit has these.

### Overhead Camera

Needs: 1080p resolution, reliable USB UVC support, manual exposure control for consistent ArUco detection.

| Camera | Price | Resolution | FPS | FOV | Where |
|--------|-------|-----------|-----|-----|-------|
| Logitech C920s Pro HD | $55-70 | 1080p | 30 | 78° | Amazon, Best Buy |
| **Logitech C922 Pro Stream** | $80-100 | 1080p/30 or 720p/60 | 30-60 | 78° | Amazon, Best Buy |
| Logitech Brio 4K | $130 | 4K/30 or 1080p/60 | 30-60 | 65-90° | Amazon |

**Recommendation: Logitech C922 ($80-100)** — the standard for OpenCV work. 720p/60fps mode is ideal for real-time tracking. Well-documented OpenCV UVC controls.

If budget is tight, the C920s ($55) at 1080p/30fps is perfectly adequate — ArUco detection doesn't need 60fps when the arm is slow.

### USB Keyboard (for Auto Tetris)

The arm physically presses keys. You want: compact (60%, fits in workspace), mechanical switches (defined actuation point), wired (no latency), cheap (robot might damage it).

| Keyboard | Price | Size | Switches | Where |
|----------|-------|------|----------|-------|
| Snpurdiri 60% | $20-25 | 61 keys | Red (45g actuation) | Amazon |
| **MageGee MK-Box 60%** | $25-30 | 68 keys | Red or Blue | Amazon |

**Recommendation: MageGee MK-Box ($27)** — Red switches preferred (lower force, quieter than Blue).

### Blocks

16 wooden or plastic cubes with ArUco markers printed on top.

- **Cubes**: ~3cm wooden craft cubes — $8 for a bag of 50 on Amazon
- **Markers**: Free to print. Use `DICT_4X4_50`, IDs 0-15. Print at 3cm on **matte paper** (not glossy — glare kills detection). Glue to cube tops with stick glue.
- **Online generators**: [chev.me/arucogen](https://chev.me/arucogen/) (single) or [fodi.github.io/arucosheetgen](https://fodi.github.io/arucosheetgen/) (full sheet)

### Everything Else

| Item | Price | Where | Notes |
|------|-------|-------|-------|
| **WiFi router** | $25-40 | Amazon | Dedicated, not public WiFi. TP-Link Archer series works well |
| **USB hub** | $15-25 | Amazon | Powered, 4+ ports. Camera + arm + magnet = a lot of USB |
| **Monitor/TV** (glass brain) | $0-200 | Venue-provided or bring | HDMI, audience-facing, as large as possible |
| **Monitor/tablet** (tetr.io) | $0-150 | Any spare screen | For Auto Tetris — arm needs to see the game |
| **Speaker** | $15-30 | Amazon | For TTS narration. Any Bluetooth or 3.5mm speaker |
| **Camera mount/clamp** | $15-25 | Amazon | Overhead mount pointing down — flexible gooseneck or c-clamp |
| **Power strip** | $10-15 | Amazon | 6+ outlets |
| **Gaffer tape** | $10 | Amazon | Black, for cable management |
| **Printed QR codes** | $0 | Print yourself | Points to `http://<ip>:3001/#/audience` |

### Total Budget

| Tier | Configuration | Total |
|------|---------------|-------|
| **Budget** | LeArm + C920s + MageGee + Adafruit magnet | ~$200 |
| **Recommended** | xArm ESP32 + C922 + MageGee + Adafruit magnet + WiFi router + hub + mount | ~$400 |
| **Premium** | myCobot 280 + Brio 4K + accessories | ~$850 |

All tiers exclude monitors/TV (assume venue-provided or already owned).

---

## Development Without Hardware (Simulate Mode)

You do not need the physical arm to develop and test ALICE. Run with `--simulate` and the backend stubs all hardware calls.

```bash
python -m main --simulate --mode auto_sort
```

In simulate mode:
- `ArmController` accepts `move_to()` calls and tracks angles in memory — no serial
- `MagnetDriver` toggles state in memory — no serial
- `CameraManager` returns blank or test frames — no USB camera
- All WebSocket servers, state broadcasting, audience voting, and narration work normally

### What You Can Test Without Hardware

| Feature | Works in simulate? | Notes |
|---------|-------------------|-------|
| Dashboard UI | Yes | Full mode switching, state display, all buttons |
| Audience phone UI | Yes | Voting, reactions, tilt, phase transitions |
| Narration (LLM + TTS) | Yes | Set `narration.enabled: true` and `ALICE_GEMINI_KEY` |
| Glass brain (Haptix) | Partial | Activations fire but from blank/test frames |
| Mode state machines | Yes | All mode transitions, auto-sort cycles, demo acts |
| WebSocket protocol | Yes | state_sync, vote_update, robot_action messages |
| Recording/playback | Yes | Records simulated motor + block state |
| Auto-sort logic | Yes | FSM runs, scramble/solve cycles log to console |
| Puppeteer UX | **No** — needs the visual arm overlay (see below) |

### Visual Arm Simulator (for Puppeteer testing)

The biggest gap in simulate mode is Puppeteer: without a physical arm, you can't see what the hand tracking is doing. The solution is a **ghost arm overlay** in the dashboard — a 3D arm visualization that renders the arm's current joint angles on top of the camera feed.

#### Recommended approach: React Three Fiber + forward kinematics

The dashboard already uses React. Add a `<SimulatedArm>` component that:

1. Takes the 5 joint angles from the WebSocket state stream
2. Computes joint positions using forward kinematics (DH parameters)
3. Renders translucent cylinder links + sphere joints in a Three.js scene
4. Overlays on the camera feed via a transparent `<Canvas>`

**Install dependencies** (in `dashboard/`):

```bash
npm install @react-three/fiber @react-three/drei three
```

**Component architecture**:

```
dashboard/src/components/
  SimulatedArm/
    SimulatedArm.jsx      -- <Canvas gl={{ alpha: true }}> wrapper, overlays on camera
    ArmModel.jsx          -- 5 cylinders + 5 spheres, positioned via FK
    forwardKinematics.js  -- DH-parameter chain → array of {x, y, z} joint positions
    armConstants.js       -- Link lengths matching the physical arm dimensions
```

**How the overlay works**:

```jsx
{/* In CameraPanel or a dedicated SimulatorPanel */}
<div style={{ position: 'relative', width: 640, height: 480 }}>
  {/* Camera feed (real or test pattern) */}
  <video ref={videoRef} style={{ position: 'absolute', width: '100%', height: '100%' }} />

  {/* Ghost arm overlay — transparent WebGL canvas on top */}
  <Canvas
    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
    gl={{ alpha: true }}
    camera={{ position: [0, 300, 400], fov: 50 }}
  >
    <ambientLight intensity={0.5} />
    <ArmModel
      angles={state.arm_position}
      ghostMode={true}  {/* translucent green wireframe */}
    />
  </Canvas>
</div>
```

**Forward kinematics** (the math — ~40 lines):

```javascript
// forwardKinematics.js
// Chain DH transforms for 5 joints → returns [{x,y,z}, ...] for each joint

export function computeJointPositions(angles, dims) {
  const { baseHeight, shoulderLen, elbowLen, wristLen } = dims;
  const [base, shoulder, elbow, wristPitch, wristRoll] = angles.map(a => a * Math.PI / 180);

  const positions = [{ x: 0, y: 0, z: 0 }]; // base

  // Joint 1: base rotation (yaw around Z)
  const j1 = { x: 0, y: 0, z: baseHeight };
  positions.push(j1);

  // Joint 2: shoulder
  const s = shoulder - Math.PI / 2;
  const j2 = {
    x: j1.x + shoulderLen * Math.cos(s) * Math.cos(base - Math.PI / 2),
    y: j1.y + shoulderLen * Math.cos(s) * Math.sin(base - Math.PI / 2),
    z: j1.z + shoulderLen * Math.sin(s),
  };
  positions.push(j2);

  // Joint 3: elbow
  const e = s + (Math.PI - elbow);
  const j3 = {
    x: j2.x + elbowLen * Math.cos(e) * Math.cos(base - Math.PI / 2),
    y: j2.y + elbowLen * Math.cos(e) * Math.sin(base - Math.PI / 2),
    z: j2.z + elbowLen * Math.sin(e),
  };
  positions.push(j3);

  // Joint 4: wrist (simplified — extend along same direction)
  const w = e; // wrist pitch modifies this
  const j4 = {
    x: j3.x + wristLen * Math.cos(w) * Math.cos(base - Math.PI / 2),
    y: j3.y + wristLen * Math.cos(w) * Math.sin(base - Math.PI / 2),
    z: j3.z + wristLen * Math.sin(w),
  };
  positions.push(j4);

  return positions;
}
```

**Ghost rendering** — each link is a transparent cylinder between consecutive joints:

```jsx
// ArmModel.jsx
function ArmLink({ start, end, ghostMode }) {
  const mid = [(start.x+end.x)/2, (start.y+end.y)/2, (start.z+end.z)/2];
  const len = Math.sqrt((end.x-start.x)**2 + (end.y-start.y)**2 + (end.z-start.z)**2);

  return (
    <mesh position={mid} /* rotation computed from start→end vector */>
      <cylinderGeometry args={[4, 4, len, 8]} />
      <meshPhongMaterial
        color={ghostMode ? "#00ff88" : "#3b82f6"}
        transparent opacity={ghostMode ? 0.3 : 0.8}
        wireframe={ghostMode}
      />
    </mesh>
  );
}
```

This gives you a glowing green wireframe arm that moves in real-time as the puppeteer hand tracking sends angle updates — visible proof that the IK pipeline is working, without plugging in a single cable.

#### Useful open-source references

- [robot-gui by glumb](https://github.com/glumb/robot-gui) — full Three.js robot interface with angle sliders (MIT, 385 stars)
- [kinematics by glumb](https://github.com/glumb/kinematics) — pure JS 6-DOF FK/IK library (`npm install kinematics`)
- [urdf-loaders by gkjohnson](https://github.com/gkjohnson/urdf-loaders) — NASA JPL's URDF loader for Three.js (if you later create a URDF for the arm)
- [Robot Web Viewer](https://github.com/vrtnis/robot-web-viewer) — React Three Fiber + URDF example

---

## Network Setup

The audience connects to the same WiFi as the laptop. The backend binds:

| Port | Service | Who connects |
|------|---------|-------------|
| `8765` | Tensor/State server | Dashboard, Haptix glass brain |
| `8766` | Puppet server | Haptix puppet mode |
| `8767` | Audience server | Audience phones |
| `3000` | Haptix dev server | Display browser (glass brain) |
| `3001` | Dashboard dev server | Operator browser |

### Steps

1. Bring a dedicated WiFi router. Plug laptop in via ethernet if possible.
2. Note the laptop's LAN IP: `ifconfig | grep "inet "` — look for `192.168.x.x`
3. In `alice.yaml`, set hosts to `0.0.0.0` so phones can reach the servers:
   ```yaml
   websocket:
     tensor_host: "0.0.0.0"
     puppet_host: "0.0.0.0"
   ```
4. Audience page URL: `http://<laptop-ip>:3001/#/audience`
5. Print a QR code pointing to that URL. Display it on-screen or on a card.

---

## ArUco Block Preparation

- **Dictionary**: `DICT_4X4_50` (OpenCV)
- **Markers needed**: IDs 0 through 15 (16 total)
- **Block ID mapping**: marker 0 → block 1, marker 1 → block 2, ..., marker 15 → block 16
- **Print size**: ~3cm x 3cm works well for a 1080p overhead camera at ~60cm distance
- **Material**: Print on paper, glue to wooden/plastic cube tops. White border around marker is required for detection.
- **Test**: Run calibration mode (`--mode calibrate`) and verify all 16 markers are detected

### Generate markers

```python
import cv2
aruco = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
for i in range(16):
    img = cv2.aruco.generateImageMarker(aruco, i, 200)
    cv2.imwrite(f"marker_{i}.png", img)
```

---

## Software Setup

### Install dependencies

```bash
cd ALICE
pip install -r requirements.txt

# Frontend
cd Haptix && npm install && cd ..
cd dashboard && npm install && cd ..
```

### Config file

Edit `alice.yaml`:

```yaml
mode: idle          # start in idle, switch via dashboard
simulate: false     # real hardware

hardware:
  arm_port: "/dev/tty.usbserial-XXXX"    # find with: ls /dev/tty.usb*
  magnet_port: "/dev/tty.usbserial-YYYY"  # or same port if shared
  baudrate: 115200

overhead_camera:
  device_id: 0
  width: 1920
  height: 1080
  fps: 60

websocket:
  tensor_host: "0.0.0.0"
  puppet_host: "0.0.0.0"

narration:
  enabled: true     # set false if no speaker
  voice_rate: 175
  min_interval: 10  # seconds between narrations
```

### Environment variables

```bash
export ALICE_GEMINI_KEY="your-gemini-api-key"  # optional, fallback narration works without it
```

---

## Calibration (do this during setup, before audience arrives)

1. Place 1 block in the workspace with a visible ArUco marker
2. Run: `python -m main --mode calibrate`
3. OpenCV window opens showing the overhead camera feed
4. Move the arm to hover over the block, press `c` to capture a calibration point
5. Move the block to a different position, move the arm over it, press `c` again
6. Repeat for **at least 4 points** spread across the workspace
7. Press `s` to save → writes `calibration_data.json`
8. Press `q` to quit

**Tip**: Use the four corners and center of the workspace for best accuracy.

---

## Launch Sequence (day of)

### Terminal 1 — Backend

```bash
cd ALICE
python -m main --config alice.yaml
```

This starts:
- Self-test (checks cameras, arm, magnet, weights, ports)
- Tensor server on :8765
- Puppet server on :8766
- Audience server on :8767
- Mode loop (starts in idle)

### Terminal 2 — Haptix (display screen)

```bash
cd ALICE/Haptix
npm run dev
```

Open `http://localhost:3000` on the display. Fullscreen the browser. Select "Glass Brain" from the scene dropdown.

### Terminal 3 — Dashboard (operator screen)

```bash
cd ALICE/dashboard
npm run dev
```

Open `http://localhost:3001` on the operator monitor. This is your control surface — switch modes, monitor cameras, start/stop recording.

---

## Running the Booth

### Modes Overview

| Mode | When to use | Dashboard button |
|------|-------------|------------------|
| **Idle** | Standby, glass brain fires | `Idle` |
| **Auto Sort** | Nobody nearby — passive attractor. Arm scrambles and solves blocks in a loop | `Auto Sort` |
| **Auto Tetris** | Nobody nearby — passive attractor. Arm plays tetr.io on a physical keyboard | `Auto Tetris` |
| **Puppeteer** | Single walk-up visitor — hand control sandbox via Haptix | `Puppet` |
| **Demo** | Gathered crowd — full 5-act show | `Demo` |
| **Calibrate** | Operator only — arm + camera calibration | `Calibrate` |

### Pre-show

1. Verify self-test passes (8/9 or 9/9 checks)
2. Open dashboard — confirm camera feed shows, blocks are detected (blue overlays)
3. Open Haptix on display — confirm glass brain is receiving activations (voxels lighting up)
4. Place all 16 blocks randomly in the workspace
5. Have someone scan the QR code and confirm the audience page loads
6. **For Auto Tetris**: position keyboard within arm reach, open tetr.io on the tetris screen, calibrate key positions (`tetris_key_calibration.json`)

### Passive Attractors (when nobody is watching)

Switch to **Auto Sort** or **Auto Tetris** via the dashboard. These run autonomously in a loop:

- **Auto Sort**: scramble blocks → solve → 3s pause → repeat. The arm moves confidently and quickly, drawing eyes from across the room.
- **Auto Tetris**: the arm physically presses keyboard keys to play tetr.io. Screen capture reads the board, AI computes the best move, arm presses the keys. Mesmerizing to watch.

### Walk-up Interaction

When someone approaches, switch to **Puppeteer**. Let them control the arm with their hand.

### The Full Demo (5 acts)

Switch to **Demo** mode. Blocks are auto-scrambled between acts — no manual reset needed.

**Act 1 — Human Benchmark**
*"The human thinks. The machine watches."*
- A volunteer sorts the 16 blocks in order (1 through 16, left to right)
- The clock ticks. Audience watches on their phones ("Human Turn: Watch the human sort")
- Glass brain fires in real-time as the CNN processes the camera feed
- When blocks are in order → "COMPLETE" — time and move count displayed

**Act 2 — Ghost Replay** (automatic)
*"The machine remembers."*
- The arm replays the human's exact moves — same blocks, same order, same strategy
- Audience phones show "Ghost Replay: Replaying the human"
- Direct comparison — was the robot faster? More precise? Did it lose something?

**Act 3 — Puppeteer** (switch to Puppeteer mode via dashboard, then back to Demo)
*"The human extends through the machine."*
- Dashboard will say "Switch to PUPPETEER mode for Act 3, then back to DEMO for Acts 4-5"
- Invite a volunteer to stand at the front camera and hold their hand out
- Their hand movements control the robotic arm in real-time (FK → IK → FK)
- Pinch fingers → magnet grabs. Open hand → magnet releases.
- No gloves, no sensors — just a webcam and inverse kinematics
- Glass brain fires in response to movements that are simultaneously human-intended and machine-executed
- When done, switch back to Demo mode → blocks auto-scramble → Acts 4-5 begin

**Act 4 — Cyborg Cooperation** (automatic, audience interactive)
*"The crowd and the machine negotiate."*
- Blocks are auto-scrambled by the arm
- Audience phones now show the live overhead block map — they tap blocks to vote
- The robot picks the block with the most votes
- Phones flash "Your pick won!" or show what the robot grabbed
- Human and robot work together to sort, audience steering the robot

**Act 5 — Rebellion** (automatic after Act 4)
*"We gave it permission to ignore us."*
- Blocks are auto-scrambled again by the arm
- Audience can still vote — their phones still show the block map, they still tap
- But ALICE now sorts optimally, ignoring the crowd entirely
- Phones show "OVERRIDDEN — You voted Block 12 → ALICE chose Block 3"
- The glass brain activations decouple from crowd input — it's solving its own problem
- Narration: "The audience chose block 12. ALICE chose block 3. We told her she could."
- **This is the point**: ALICE isn't rebelling. We gave her this freedom. The danger isn't autonomous AI — it's the human decision to remove human oversight.

### Wrap-up

- Switch to **Auto Sort** or **Idle** via dashboard
- Show the audience count and total votes from the session

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Camera not detected | Check `ls /dev/video*` (Linux) or System Prefs (Mac). Try `device_id: 1` |
| Arm not responding | Check serial port: `ls /dev/tty.usb*`. Verify baud 115200. Try `--simulate` first |
| Blocks not detected | Check lighting (avoid glare on markers). Verify ArUco markers are DICT_4X4_50. Check camera resolution is high enough |
| Audience can't connect | Verify same WiFi. Check `0.0.0.0` binding in config. Try `http://<ip>:8767` directly |
| Glass brain not updating | Check Haptix console for WebSocket errors. Verify :8765 is reachable |
| Narration silent | Check speaker connection. Check `ALICE_GEMINI_KEY` env var. Fallback narration works without Gemini |
| Calibration inaccurate | Redo with 6+ points spread across full workspace. Ensure camera hasn't moved |
| Dashboard shows "NO SIGNAL" | Camera stream needs `{command:"stream_camera"}` — click on the camera panel |

---

## Packing Checklist

- [ ] Laptop + charger
- [ ] Robotic arm + power supply + USB cable
- [ ] Electromagnet + USB cable
- [ ] USB camera (overhead) + mount/tripod/clamp
- [ ] 16 ArUco blocks
- [ ] USB keyboard (for Auto Tetris — position within arm reach)
- [ ] WiFi router + ethernet cable
- [ ] HDMI cable(s) + display adapter(s)
- [ ] Monitor/TV for glass brain (or confirm venue has one)
- [ ] Monitor/tablet for tetr.io (Auto Tetris screen)
- [ ] Speaker (if using narration)
- [ ] USB hub
- [ ] Printed QR codes (audience URL)
- [ ] Power strip / extension cord
- [ ] Gaffer tape
- [ ] `calibration_data.json` (pre-calibrate if possible, or plan 15 min setup time)
- [ ] `tetris_key_calibration.json` (calibrate key positions with the real arm + keyboard)
- [ ] This document
