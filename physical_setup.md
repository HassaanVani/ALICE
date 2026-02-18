# ALICE — Physical Setup for Showcase Day

## What You're Building

A table with a robotic arm, 16 numbered blocks, and an overhead camera. Behind it, a screen shows a rotating glass brain with neurons firing in real-time. The audience participates from their phones. A narrator commentates.

```
┌─────────────────────────────────────────────────┐
│                  PROJECTION / TV                 │
│            (Haptix — glass brain view)           │
└─────────────────────────────────────────────────┘

         ┌─────────────────────────┐
         │     OVERHEAD CAMERA     │  ← mounted above, pointing down
         └───────────┬─────────────┘
                     │
    ┌────────────────▼────────────────┐
    │                                 │
    │   [blocks]    🦾 ARM  [blocks]  │  ← workspace table
    │                                 │
    │   DROP ZONE       SORTED ZONE   │
    │                                 │
    └─────────────────────────────────┘

    ┌──────────┐          ┌──────────┐
    │  LAPTOP  │          │ MONITOR  │
    │ (backend │          │(dashboard│
    │  + dash) │          │ operator)│
    └──────────┘          └──────────┘

    📱📱📱📱📱  ← audience phones on same WiFi
```

---

## Hardware List

### Required

| Item | Spec | Notes |
|------|------|-------|
| **Robotic arm** | 5-axis, serial over USB (115200 baud) | Protocol: CSV angles `"90,90,90,90,90\n"` → expects `"OK"` |
| **Electromagnet** | Serial `"MAG:1\n"` / `"MAG:0\n"` | Can share serial with arm or separate port |
| **Overhead camera** | USB, 1920x1080 @ 60fps recommended | Device index 0. Must see full workspace from above |
| **16 ArUco blocks** | ArUco 4x4_50 dictionary, markers 0–15 | Print markers, glue to block tops. Each maps to block ID 1–16 |
| **Laptop/PC** | Python 3.10+, GPU optional (CPU inference works) | Runs backend + all 3 WebSocket servers |
| **Display/TV** | HDMI, large enough for audience to see | Shows Haptix glass brain (browser fullscreen) |
| **WiFi router** | Dedicated, not public WiFi | Audience phones + laptop on same LAN |

### Optional (but recommended)

| Item | Spec | Notes |
|------|------|-------|
| **Second monitor** | For operator dashboard | Shows camera feed, block overlay, arm status, mode controls |
| **Front camera** | USB, 1280x720 @ 30fps | Device index 1. Not critical for demo but wired in |
| **Speaker** | 3.5mm or Bluetooth | For pyttsx3 narration (set `narration.enabled: true`) |
| **Phone stand / QR code** | Printed, visible | So audience knows how to join |
| **USB hub** | Powered, 4+ ports | Camera(s) + arm + magnet can be a lot of USB |
| **Gaffer tape** | Black | Cable management, camera mounting |

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

## Running the Demo

### Pre-show

1. Verify self-test passes (8/9 or 9/9 checks)
2. Open dashboard — confirm camera feed shows, blocks are detected (blue overlays)
3. Open Haptix on display — confirm glass brain is receiving activations (voxels lighting up)
4. Place all 16 blocks randomly in the workspace
5. Have someone scan the QR code and confirm the audience page loads

### The show (3 acts)

**Act 1 — Human Benchmark** (switch to Sort mode via dashboard)
- A volunteer sorts the 16 blocks in order (1 through 16, left to right)
- The clock ticks. Audience watches on their phones ("Human Turn: Watch the human sort")
- Glass brain fires in real-time as the CNN processes the camera feed
- When blocks are in order → "COMPLETE" — time and move count displayed

**Act 2 — Ghost Replay** (automatic)
- The arm replays the human's exact moves
- Audience phones show "Ghost Replay: Replaying the human"
- Direct comparison — was the robot faster? More efficient?

**Act 3 — Cyborg Cooperation** (automatic, audience interactive)
- Blocks are scrambled again (you do this by hand)
- Audience phones now show the block map — they tap blocks to vote
- The robot picks the block with the most votes
- Phones flash "Your pick won!" or show what the robot grabbed
- Human and robot work together to sort, audience steering the robot

**Encore — Tetris** (switch via dashboard)
- Robot packs blocks into a grid
- Audience tilts phones to influence placement
- Score climbs, lines clear, glass brain keeps firing

### Wrap-up

- Switch to idle mode via dashboard
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
- [ ] WiFi router + ethernet cable
- [ ] HDMI cable + display adapter
- [ ] Monitor/TV (or confirm venue has one)
- [ ] Speaker (if using narration)
- [ ] USB hub
- [ ] Printed QR codes (audience URL)
- [ ] Power strip / extension cord
- [ ] Gaffer tape
- [ ] `calibration_data.json` (pre-calibrate if possible, or plan 15 min setup time)
- [ ] This document
