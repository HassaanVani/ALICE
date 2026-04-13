---
name: project_arm_angles
description: MyPalletizer 260 calibrated arm positions discovered during hardware testing
type: project
---

Hardware-tested arm angles for ALICE (MyPalletizer 260 M5Stack):

- **Default (looking at user):** [-33, -2, -72, 43]
- **Sleep (resting):** [-14, 38, -31, 36]
- **Joint limits:** J1 -162..162, J2 -2..90, J3 -92..60, J4 -180..180
- **Connection:** USB serial `/dev/tty.usbserial-58690044391` at 115200, or WiFi socket 192.168.1.87:9000
- **Class:** `MyPalletizer260` (serial) / `MyPalletizerSocket` (WiFi)
- **Mounting:** Edge-mount on book platform, counterweighted with water bottle + 2 Wii remotes
- **Webcam:** HD Pro Webcam C920 mounted on arm (OpenCV device 0), FaceTime HD as front cam (device 1)

**Why:** J2=0 hangs the arm straight down. The arm mounts to a desk edge and reaches upward/outward. All positive J2 moves toward the desk surface, not away from it.

**How to apply:** Use these as the base angles for face tracking, idle position, and sleep. All choreography (fist bump, dance) should start and return to DEFAULT_ANGLES.
