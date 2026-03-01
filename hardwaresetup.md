# MyPalletizer 260 M5Stack — Quickstart

Everything you need to go from unboxing to ALICE running on real hardware.

---

## What's in the Box

- MyPalletizer 260 arm
- 12V power adapter
- USB Type-C cable
- Suction pump kit (pump + tubing + suction cup nozzle)
- M5Stack GPIO cable harness
- Mounting screws

You also need:
- A computer with Python 3.10+ and ALICE installed
- A Logitech C922 (or similar USB camera) + overhead mount
- 16 wooden cubes with ArUco markers (see `physical_setup.md`)

---

## Step 1: Power

1. Plug the **12V adapter** into the barrel jack on the back of the arm base
2. Plug the adapter into a wall outlet
3. The M5Stack screen on the base should light up and show a menu — this means the arm has power

> Do NOT connect USB before powering on. Power first, USB second.

---

## Step 2: USB

1. Plug the **USB Type-C cable** into the port on the M5Stack base (bottom-front of the arm)
2. Plug the other end into your computer
3. Find your serial port:

```bash
# macOS
ls /dev/tty.usbserial-*

# Linux
ls /dev/ttyUSB* /dev/ttyACM*

# Windows — open Device Manager → Ports (COM & LPT), look for "USB Serial"
```

You should see one new device (e.g. `/dev/tty.usbserial-14210` on Mac, `/dev/ttyUSB0` on Linux, `COM3` on Windows). Write this down — you'll need it.

> If nothing shows up: try a different USB cable (some are charge-only), try a different USB port, or install the CP210x driver from [Silicon Labs](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers).

---

## Step 3: Suction Pump

1. Attach the **suction cup nozzle** to the end of J4 (the last joint/wrist)
2. Connect the **air tubing** from the nozzle to the pump
3. Connect the pump's **GPIO cable** to the M5Stack base:
   - The pump control wire goes to **pin 5** on the M5Stack GPIO header
   - Match the ground wire to GND
   - Match the power wire to 5V
4. Route the tubing along the arm and secure with zip ties or tape so it doesn't snag during movement

```
Pump wiring (M5Stack GPIO header):
  Pin 5  ← pump control (signal)
  GND    ← ground
  5V     ← power
```

---

## Step 4: Mount the Camera

1. Clamp the overhead camera **directly above** the workspace, pointing straight down
2. Height: 50–70 cm above the table
3. Plug it into your computer via USB
4. Make sure the entire arm reach area is visible in frame

---

## Step 5: Install pymycobot

```bash
cd ALICE
pip install pymycobot
```

---

## Step 6: Verify the Arm Works

Replace the port below with the one you found in Step 2.

```bash
python -c "
from pymycobot import MyPalletizer260
import time

mc = MyPalletizer260('/dev/tty.usbserial-XXXX', 115200)
time.sleep(0.5)

print('Angles:', mc.get_angles())
mc.send_angles([0, 0, 0, 0], 50)
print('Sent home position — arm should move to (0,0,0,0)')
time.sleep(3)

mc.send_angles([30, 20, -20, 0], 50)
print('Sent test position — arm should move')
time.sleep(3)

mc.send_angles([0, 0, 0, 0], 50)
print('Back to home')
"
```

You should see the arm move. If it doesn't:
- Check that the 12V power is connected (arm needs power to move, USB alone isn't enough)
- Check the serial port is correct
- Make sure nothing is blocking the arm's path

---

## Step 7: Verify the Suction Pump Works

```bash
python -c "
from pymycobot import MyPalletizer260
import time

mc = MyPalletizer260('/dev/tty.usbserial-XXXX', 115200)
time.sleep(0.5)

print('Pump ON')
mc.set_basic_output(5, 0)   # active-low: 0 = ON
time.sleep(2)

print('Pump OFF')
mc.set_basic_output(5, 1)   # 1 = OFF
print('Done — you should have heard the pump run for 2 seconds')
"
```

Hold your finger over the suction cup while the pump is on — you should feel suction. If not:
- Check the GPIO wiring (pin 5, GND, 5V)
- Check the tubing connections for leaks
- Try `mc.set_basic_output(2, 0)` — some pump kits use pin 2 instead of 5

---

## Step 8: Configure ALICE

Edit `alice.yaml`:

```yaml
simulate: false

hardware:
  arm:
    port: "/dev/tty.usbserial-XXXX"   # your port from Step 2
    baudrate: 115200
  gripper_type: suction
  suction_pin: 5
```

Or just pass it on the command line:

```bash
python main.py --arm-port /dev/tty.usbserial-XXXX
```

---

## Step 9: Run ALICE

```bash
python main.py --mode idle
```

You should see:

```
[INFO] Connected on /dev/tty.usbserial-XXXX
[INFO] Initialization complete
[INFO] Starting main loop
```

The arm is now live. Switch modes from the dashboard or restart with `--mode auto_sort`.

---

## Step 10: Calibrate

Before ALICE can pick up blocks, you need to calibrate the camera-to-arm mapping.

1. Place a block with an ArUco marker in the workspace
2. Run: `python main.py --mode calibrate`
3. Manually jog the arm so the suction cup is directly over the block
4. Press `c` to capture
5. Move the block, reposition the arm, press `c` again
6. Do this for **at least 4 positions** — use the corners and center of your workspace
7. Press `s` to save, `q` to quit

Now ALICE knows where blocks are in 3D space.

---

## Quick Reference

| What | Command |
|------|---------|
| Home position | `(0, 0, 0, 0)` |
| Pump on | `mc.set_basic_output(5, 0)` |
| Pump off | `mc.set_basic_output(5, 1)` |
| Compliance on (go limp) | `mc.release_all_servos()` |
| Compliance off (stiffen) | `mc.power_on()` |
| Read current angles | `mc.get_angles()` |
| Move to angles | `mc.send_angles([j1, j2, j3, j4], speed)` |
| Speed range | 0–100 (50 is a good default) |

### Joint Limits

| Joint | Min | Max | What it does |
|-------|-----|-----|-------------|
| J1 | -162° | +162° | Base rotation (left/right) |
| J2 | -2° | +90° | Shoulder (up/down) |
| J3 | -92° | +60° | Elbow (up/down) |
| J4 | -180° | +180° | Wrist rotation (twist) |

---

## Troubleshooting

**Arm doesn't move**
→ Is the 12V adapter plugged in? USB alone provides data, not motor power.

**Serial port not found**
→ Install the CP210x USB driver. Try a different cable. Try `ls /dev/tty.*` to see all ports.

**`pymycobot` import error**
→ `pip install pymycobot`

**Pump doesn't turn on**
→ Check GPIO wiring. Try pin 2 instead of pin 5. Make sure GND and 5V are connected.

**Arm moves but suction doesn't pick up blocks**
→ Check tubing for leaks. Make sure the suction cup is making flush contact with the block surface. Blocks need a smooth, flat top.

**`Expected 4 angles, got 5`**
→ Old calibration data from the 5-DOF arm. Delete `calibration_data.json` and `tetris_key_calibration.json`, then recalibrate.

**Arm jerks or overshoots**
→ Lower the speed parameter (try 30 instead of 50). Make sure no tubing is snagging.
