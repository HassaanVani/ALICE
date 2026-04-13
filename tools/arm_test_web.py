"""ALICE Arm Test — Web UI for joint control, webcam, and choreography.

Usage:
    python tools/arm_test_web.py                         # auto-detect USB
    python tools/arm_test_web.py --port /dev/tty.usb...  # specific port
    python tools/arm_test_web.py --wifi 192.168.1.87     # WiFi socket

Opens http://localhost:5050 in your browser.
"""

import json
import glob
import time
import threading
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)

# Global arm connection
mc = None
connection_info = {"type": None, "port": None, "status": "disconnected"}
cam = None        # primary camera (front-facing, stable)
cam2 = None       # secondary camera (arm-mounted)

# Face tracking state
face_tracking = False
face_tracking_thread = None
face_tracking_lock = threading.Lock()

# Hand tracking state
hand_tracking = False
hand_tracking_thread = None

# Tracking sensitivity (adjustable from UI)
tracking_v_sensitivity = 1.0  # vertical multiplier

# Wander mode
wandering = False
wander_thread = None

# Default "looking at user" angles — discovered from hardware testing
DEFAULT_ANGLES = [-33, -2, -72, 43]
SLEEP_ANGLES = [-14, 38, -31, 36]

# ── Connection ───────────────────────────────────────────────────

def list_serial_ports():
    return sorted(glob.glob("/dev/tty.usb*") + glob.glob("/dev/cu.usb*"))


def connect_serial(port):
    global mc, connection_info
    try:
        from pymycobot.mypalletizer260 import MyPalletizer260
        mc = MyPalletizer260(port, 115200)
        time.sleep(2)
        a = mc.get_angles()
        connection_info = {"type": "serial", "port": port, "status": "connected",
                          "angles": a if a != -1 else None}
        return True
    except Exception as e:
        connection_info = {"type": "serial", "port": port, "status": f"error: {e}"}
        mc = None
        return False


def connect_wifi(ip, port=9000):
    global mc, connection_info
    try:
        from pymycobot.mypalletizersocket import MyPalletizerSocket
        mc = MyPalletizerSocket(ip, port)
        time.sleep(1)
        a = mc.get_angles()
        connection_info = {"type": "wifi", "port": f"{ip}:{port}", "status": "connected",
                          "angles": a if a != -1 else None}
        return True
    except Exception as e:
        connection_info = {"type": "wifi", "port": f"{ip}:{port}", "status": f"error: {e}"}
        mc = None
        return False


def disconnect():
    global mc, connection_info
    if mc:
        try:
            mc.close()
        except:
            pass
    mc = None
    connection_info = {"type": None, "port": None, "status": "disconnected"}


# ── Webcam (single reader thread, shared frame) ─────────────────

_cam_frame = None
_cam_frame_lock = threading.Lock()
_cam_running = False
_cam_thread = None

_cam2_frame = None
_cam2_frame_lock = threading.Lock()
_cam2_running = False
_cam2_thread = None


_cam_device_id = None
_cam2_device_id = None

def start_webcam(device_id=0):
    global cam, _cam_running, _cam_thread, _cam_device_id
    import cv2

    # Don't allow same device as secondary
    if _cam2_device_id is not None and device_id == _cam2_device_id:
        return False

    stop_webcam()
    time.sleep(0.3)

    cam = cv2.VideoCapture(device_id)
    if not cam.isOpened():
        cam = None
        return False
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    _cam_device_id = device_id
    _cam_running = True
    _cam_thread = threading.Thread(target=_cam_reader_loop, daemon=True)
    _cam_thread.start()
    return True


def _cam_reader_loop():
    """Single thread reads from camera, stores frame for all consumers."""
    global _cam_frame, _cam_running
    while _cam_running and cam is not None:
        try:
            ret, frame = cam.read()
            if ret:
                with _cam_frame_lock:
                    _cam_frame = frame
        except Exception:
            break
        time.sleep(0.025)  # ~40fps read rate


def get_cam_frame():
    """Thread-safe: get the latest camera frame."""
    with _cam_frame_lock:
        return _cam_frame


def stop_webcam():
    global cam, _cam_running, _cam_thread, _cam_frame, _cam_device_id
    stop_face_tracking()
    stop_hand_tracking()
    _cam_running = False
    if _cam_thread:
        _cam_thread.join(timeout=2)
        _cam_thread = None
    if cam is not None:
        try:
            cam.release()
        except Exception:
            pass
        cam = None
    _cam_frame = None
    _cam_device_id = None


def start_webcam2(device_id=1):
    global cam2, _cam2_running, _cam2_thread, _cam2_device_id
    import cv2

    # Don't allow same device as primary
    if _cam_device_id is not None and device_id == _cam_device_id:
        return False

    stop_webcam2()
    time.sleep(0.3)
    cam2 = cv2.VideoCapture(device_id)
    if not cam2.isOpened():
        cam2 = None
        return False
    cam2.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam2.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    _cam2_device_id = device_id
    _cam2_running = True
    _cam2_thread = threading.Thread(target=_cam2_reader_loop, daemon=True)
    _cam2_thread.start()
    return True


def _cam2_reader_loop():
    global _cam2_frame, _cam2_running
    while _cam2_running and cam2 is not None:
        try:
            ret, frame = cam2.read()
            if ret:
                with _cam2_frame_lock:
                    _cam2_frame = frame
        except Exception:
            break
        time.sleep(0.025)


def get_cam2_frame():
    with _cam2_frame_lock:
        return _cam2_frame


def stop_webcam2():
    global cam2, _cam2_running, _cam2_thread, _cam2_frame, _cam2_device_id
    _cam2_running = False
    if _cam2_thread:
        _cam2_thread.join(timeout=2)
        _cam2_thread = None
    if cam2 is not None:
        try:
            cam2.release()
        except Exception:
            pass
        cam2 = None
    _cam2_frame = None
    _cam2_device_id = None


# ── Face Tracking ────────────────────────────────────────────────

def _face_tracking_loop():
    """Dual-camera face tracking.

    Primary (front camera, stable): coarse position — where is the user?
    Secondary (arm camera): refinement — is the face centered in ALICE's view?

    Primary drives. Secondary adjusts. If only one is running, it's used alone.
    """
    import cv2
    import mediapipe as mp

    BaseOptions = mp.tasks.BaseOptions
    FaceDetector = mp.tasks.vision.FaceDetector
    FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=_get_face_model_path()),
        running_mode=VisionRunningMode.IMAGE,
        min_detection_confidence=0.5,
    )
    detector = FaceDetector.create_from_options(options)

    COARSE_SMOOTH = 0.20
    FINE_SMOOTH = 0.08
    DEAD_ZONE = 0.02
    J1_RANGE = 60.0
    J2_RANGE = 15.0
    J3_RANGE = 20.0
    J4_RANGE = 25.0
    REFINE_J1 = 8.0
    REFINE_J4 = 5.0

    current_j1 = float(DEFAULT_ANGLES[0])
    current_j2 = float(DEFAULT_ANGLES[1])
    current_j3 = float(DEFAULT_ANGLES[2])
    current_j4 = float(DEFAULT_ANGLES[3])
    last_send = 0
    guard = ResistanceGuard()

    # Fist bump detection — uses arm camera (or front if no arm cam)
    hand_detector = None
    fist_frames = 0
    FIST_CONFIRM_FRAMES = 3  # fast detection — 3 frames (~100ms)
    bump_cooldown = 0.0

    def detect_face(frame):
        if frame is None:
            return None, None
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = detector.detect(mp_img)
        if not results.detections:
            return None, None
        det = results.detections[0]
        bbox = det.bounding_box
        cx = (bbox.origin_x + bbox.width / 2) / w - 0.5
        cy = (bbox.origin_y + bbox.height / 2) / h - 0.5
        return cx, cy

    global face_tracking
    while face_tracking:
        if mc is None:
            time.sleep(0.1)
            continue
        if not _cam_running and not _cam2_running:
            time.sleep(0.1)
            continue

        now = time.time()
        v_sens = tracking_v_sensitivity

        # Detect on both cameras
        coarse_x, coarse_y = detect_face(get_cam_frame() if _cam_running else None)
        fine_x, fine_y = detect_face(get_cam2_frame() if _cam2_running else None)

        has_coarse = coarse_x is not None
        has_fine = fine_x is not None

        if has_coarse:
            # Primary drives all joints
            target_j1 = DEFAULT_ANGLES[0] - coarse_x * J1_RANGE
            target_j2 = DEFAULT_ANGLES[1] - coarse_y * J2_RANGE * v_sens
            target_j3 = DEFAULT_ANGLES[2] + coarse_y * J3_RANGE * v_sens
            target_j4 = DEFAULT_ANGLES[3] + coarse_y * J4_RANGE * v_sens

            # Secondary refines J1 and J4 to center face in arm cam
            if has_fine:
                target_j1 -= fine_x * REFINE_J1
                target_j4 += fine_y * REFINE_J4

            target_j1 = max(-162, min(162, target_j1))
            target_j2 = max(-2, min(90, target_j2))
            target_j3 = max(-92, min(60, target_j3))
            target_j4 = max(-180, min(180, target_j4))

            smooth = COARSE_SMOOTH
            current_j1 += smooth * (target_j1 - current_j1)
            current_j2 += smooth * (target_j2 - current_j2)
            current_j3 += smooth * (target_j3 - current_j3)
            current_j4 += smooth * (target_j4 - current_j4)

        elif has_fine:
            # Secondary only — half range, extra smooth to reduce jitter
            target_j1 = DEFAULT_ANGLES[0] - fine_x * J1_RANGE * 0.4
            target_j2 = DEFAULT_ANGLES[1] - fine_y * J2_RANGE * v_sens * 0.4
            target_j3 = DEFAULT_ANGLES[2] + fine_y * J3_RANGE * v_sens * 0.4
            target_j4 = DEFAULT_ANGLES[3] + fine_y * J4_RANGE * v_sens * 0.4

            target_j1 = max(-162, min(162, target_j1))
            target_j2 = max(-2, min(90, target_j2))
            target_j3 = max(-92, min(60, target_j3))
            target_j4 = max(-180, min(180, target_j4))

            current_j1 += FINE_SMOOTH * (target_j1 - current_j1)
            current_j2 += FINE_SMOOTH * (target_j2 - current_j2)
            current_j3 += FINE_SMOOTH * (target_j3 - current_j3)
            current_j4 += FINE_SMOOTH * (target_j4 - current_j4)
        else:
            time.sleep(0.05)
            continue

        # ── Fist bump detection (both cameras) ──
        if now - bump_cooldown > 4.0:  # 4s cooldown between bumps
            # Check both cameras for a fist — lightweight check every few frames
            if hand_detector is None:
                import mediapipe as _mp
                _BO = _mp.tasks.BaseOptions
                _HL = _mp.tasks.vision.HandLandmarker
                _HLO = _mp.tasks.vision.HandLandmarkerOptions
                _VRM = _mp.tasks.vision.RunningMode
                _opts = _HLO(
                    base_options=_BO(model_asset_path=_get_hand_model_path()),
                    running_mode=_VRM.IMAGE, num_hands=1,
                    min_hand_detection_confidence=0.5,
                )
                hand_detector = _HL.create_from_options(_opts)

            # Front camera detects fists — it has the stable wide view
            fist_found = False
            front = get_cam_frame() if _cam_running else get_cam2_frame()
            if front is not None:
                fist_pos = _detect_fist_in_frame(hand_detector, front)
                if fist_pos is not None:
                    fist_found = True

            if fist_found:
                fist_frames += 1
                if fist_frames >= FIST_CONFIRM_FRAMES:
                    pre_bump = [current_j1, current_j2, current_j3, current_j4]
                    _execute_fist_bump(mc, pre_bump)
                    bump_cooldown = time.time()
                    fist_frames = 0
                    try:
                        actual = mc.get_angles()
                        if actual != -1 and actual is not None:
                            current_j1, current_j2, current_j3, current_j4 = actual
                    except Exception:
                        pass
                    guard.reset()
                    continue
            else:
                fist_frames = max(0, fist_frames - 1)

        if now - last_send > 0.05:
            try:
                angles = [
                    round(current_j1, 1),
                    round(current_j2, 1),
                    round(current_j3, 1),
                    round(current_j4, 1),
                ]

                angles = guard.check(angles, mc)
                if guard.is_stuck:
                    current_j1, current_j2, current_j3, current_j4 = angles

                mc.send_angles(angles, 40)
                last_send = now
            except Exception:
                pass

        time.sleep(0.033)

    detector.close()
    if hand_detector:
        hand_detector.close()


# ── Hand Tracking ────────────────────────────────────────────────

def _hand_tracking_loop():
    """Track hand position and gesture, move arm to follow the hand."""
    import cv2
    import mediapipe as mp

    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_get_hand_model_path()),
        running_mode=VisionRunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    detector = HandLandmarker.create_from_options(options)

    SMOOTHING = 0.25
    DEAD_ZONE = 0.02
    J1_RANGE = 70.0
    J2_BASE = 20.0
    J3_BASE = 25.0
    J4_BASE = 30.0

    current_j1 = float(DEFAULT_ANGLES[0])
    current_j2 = float(DEFAULT_ANGLES[1])
    current_j3 = float(DEFAULT_ANGLES[2])
    current_j4 = float(DEFAULT_ANGLES[3])
    last_move_send = 0
    last_grip_send = 0
    gesture = GestureState()
    guard = ResistanceGuard()

    global hand_tracking
    while hand_tracking:
        if mc is None or not _cam_running:
            time.sleep(0.1)
            continue

        frame = get_cam_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        results = detector.detect(mp_image)

        if results.hand_landmarks:
            landmarks = results.hand_landmarks[0]

            # Palm center for smoother tracking
            palm_ids = [0, 5, 9, 13, 17]
            hand_cx = sum(landmarks[i].x for i in palm_ids) / len(palm_ids)
            hand_cy = sum(landmarks[i].y for i in palm_ids) / len(palm_ids)

            # Gesture detection — runs independently of movement
            grip_action = gesture.update(landmarks)
            now = time.time()

            # Grip commands — separate from movement, own timing
            if grip_action != "none" and now - last_grip_send > 0.2:
                try:
                    if grip_action == "close":
                        mc.set_gripper_state(1, 80)
                    elif grip_action == "open":
                        mc.set_gripper_state(0, 80)
                    last_grip_send = now
                except Exception:
                    pass

            # Movement tracking — 3 axes mapped to arm joints
            # X: left/right in frame → J1 base rotation
            # Y: up/down in frame → J2 shoulder + J4 wrist tilt
            # Retraction: controlled by hand Y position in frame
            #   Hand high in frame (close to camera/user) → arm retracts
            #   Hand low in frame (reaching out) → arm extends

            offset_x = hand_cx - 0.5   # left/right
            offset_y = hand_cy - 0.5   # up/down — positive = lower in frame

            v_sens = tracking_v_sensitivity

            if abs(offset_x) > DEAD_ZONE or abs(offset_y) > DEAD_ZONE:
                # Horizontal: base rotation
                target_j1 = DEFAULT_ANGLES[0] - offset_x * J1_RANGE

                # Vertical maps to extension/retraction:
                # Hand low in frame (offset_y positive) → extend (j3 more negative)
                # Hand high in frame (offset_y negative) → retract (j3 toward 0)
                target_j3 = DEFAULT_ANGLES[2] - offset_y * J3_BASE * v_sens * 2.0

                # Shoulder follows slightly for reach
                target_j2 = DEFAULT_ANGLES[1] + offset_y * J2_BASE * v_sens

                # Wrist keeps orientation stable
                target_j4 = DEFAULT_ANGLES[3]

                target_j1 = max(-162, min(162, target_j1))
                target_j2 = max(-2, min(90, target_j2))
                target_j3 = max(-92, min(60, target_j3))
                target_j4 = max(-180, min(180, target_j4))

                current_j1 += SMOOTHING * (target_j1 - current_j1)
                current_j2 += SMOOTHING * (target_j2 - current_j2)
                current_j3 += SMOOTHING * (target_j3 - current_j3)
                current_j4 += SMOOTHING * (target_j4 - current_j4)

                if now - last_move_send > 0.05:
                    try:
                        angles = [
                            round(current_j1, 1),
                            round(current_j2, 1),
                            round(current_j3, 1),
                            round(current_j4, 1),
                        ]
                        angles = guard.check(angles, mc)
                        if guard.is_stuck:
                            current_j1, current_j2, current_j3, current_j4 = angles
                        mc.send_angles(angles, 40)
                        last_move_send = now
                    except Exception:
                        pass

        time.sleep(0.033)

    detector.close()


class GestureState:
    """Tracks gesture state with hysteresis to prevent flickering."""

    PINCH_CLOSE = 0.06       # thumb-index distance to trigger pinch
    PINCH_OPEN = 0.10        # distance to release pinch (higher = hysteresis)
    FULL_GRIP = 0.075        # all fingers close to thumb = fist
    FULL_OPEN = 0.15         # all fingers far from thumb = open hand
    MIN_HOLD_MS = 150        # minimum hold time before changing gripper state
    GRIP_COOLDOWN_MS = 300   # cooldown between grip state changes

    def __init__(self):
        self.current = "idle"
        self.gripper_closed = False
        self.last_change_time = 0
        self.hold_start_time = 0
        self.pending_gesture = None

    def _dist(self, a, b):
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def update(self, landmarks) -> str:
        """Update gesture from landmarks. Returns 'close', 'open', or 'none'."""
        thumb = landmarks[4]
        index = landmarks[8]
        middle = landmarks[12]
        ring = landmarks[16]
        pinky = landmarks[20]

        index_dist = self._dist(thumb, index)
        middle_dist = self._dist(thumb, middle)
        ring_dist = self._dist(thumb, ring)
        pinky_dist = self._dist(thumb, pinky)
        avg_dist = (index_dist + middle_dist + ring_dist + pinky_dist) / 4

        now = time.time() * 1000  # ms

        # Detect raw gesture
        if avg_dist < self.FULL_GRIP:
            raw = "fist"
        elif index_dist < self.PINCH_CLOSE:
            raw = "pinch"
        elif avg_dist > self.FULL_OPEN:
            raw = "open"
        elif self.gripper_closed and avg_dist > self.PINCH_OPEN:
            raw = "open"  # hysteresis release
        else:
            raw = self.current  # hold previous

        # Debounce: require hold time before acting
        if raw != self.pending_gesture:
            self.pending_gesture = raw
            self.hold_start_time = now
            return "none"

        held = now - self.hold_start_time
        if held < self.MIN_HOLD_MS:
            return "none"

        # Cooldown between grip changes
        if now - self.last_change_time < self.GRIP_COOLDOWN_MS:
            return "none"

        # State transition
        action = "none"
        if raw in ("fist", "pinch") and not self.gripper_closed:
            self.gripper_closed = True
            self.last_change_time = now
            action = "close"
        elif raw == "open" and self.gripper_closed:
            self.gripper_closed = False
            self.last_change_time = now
            action = "open"

        self.current = raw
        return action


def start_hand_tracking():
    global hand_tracking, hand_tracking_thread
    if hand_tracking:
        return
    hand_tracking = True
    hand_tracking_thread = threading.Thread(target=_hand_tracking_loop, daemon=True)
    hand_tracking_thread.start()


def stop_hand_tracking():
    global hand_tracking, hand_tracking_thread
    hand_tracking = False
    if hand_tracking_thread:
        hand_tracking_thread.join(timeout=2)
        hand_tracking_thread = None


def _get_hand_model_path():
    """Download the mediapipe hand landmarker model if not cached."""
    import urllib.request
    model_dir = Path(__file__).parent.parent / "data" / "models"
    model_path = model_dir / "hand_landmarker.task"
    if not model_path.exists():
        model_dir.mkdir(parents=True, exist_ok=True)
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        print(f"Downloading hand landmarker model...")
        urllib.request.urlretrieve(url, str(model_path))
        print(f"Saved to {model_path}")
    return str(model_path)


def _get_face_model_path():
    """Download the mediapipe face detection model if not cached."""
    import urllib.request
    model_dir = Path(__file__).parent.parent / "data" / "models"
    model_path = model_dir / "blaze_face_short_range.tflite"
    if not model_path.exists():
        model_dir.mkdir(parents=True, exist_ok=True)
        url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
        print(f"Downloading face detection model...")
        urllib.request.urlretrieve(url, str(model_path))
        print(f"Saved to {model_path}")
    return str(model_path)


# ── Resistance Detection ─────────────────────────────────────────

class ResistanceGuard:
    """Detects when the arm can't reach a target (hitting a surface/limit).

    Compares commanded angles to actual readback. If the difference
    exceeds a threshold for several consecutive frames, the arm is stuck.
    Backs off to the last safe position.
    """

    TOLERANCE_DEG = 8.0      # allowed error between command and readback
    STUCK_FRAMES = 3         # consecutive frames over tolerance = stuck
    BACKOFF_FACTOR = 0.7     # how far back toward safe position (0-1)

    def __init__(self):
        self.safe_angles = list(DEFAULT_ANGLES)
        self.stuck_counts = [0, 0, 0, 0]  # per joint
        self.is_stuck = False

    def check(self, commanded, mc_instance) -> list:
        """Check if the arm reached the commanded position.

        Args:
            commanded: [j1, j2, j3, j4] angles that were just sent.
            mc_instance: pymycobot instance to read actual angles.

        Returns:
            corrected angles — either the commanded angles (if OK)
            or backed-off angles (if stuck).
        """
        try:
            actual = mc_instance.get_angles()
        except Exception:
            return commanded

        if actual == -1 or actual is None:
            return commanded

        corrected = list(commanded)
        any_stuck = False

        for i in range(4):
            error = abs(commanded[i] - actual[i])
            if error > self.TOLERANCE_DEG:
                self.stuck_counts[i] += 1
                if self.stuck_counts[i] >= self.STUCK_FRAMES:
                    # Stuck on this joint — back off toward safe position
                    corrected[i] = (
                        self.safe_angles[i] +
                        self.BACKOFF_FACTOR * (commanded[i] - self.safe_angles[i])
                    )
                    any_stuck = True
            else:
                self.stuck_counts[i] = 0
                self.safe_angles[i] = actual[i]  # update safe position

        self.is_stuck = any_stuck
        return corrected

    def reset(self):
        self.stuck_counts = [0, 0, 0, 0]
        self.is_stuck = False


def _detect_fist_in_frame(detector, frame):
    """Check if a closed fist is visible in a frame. Returns (cx, cy) normalized or None.

    A real fist has:
    - All fingertips BELOW their PIP joints (curled into palm)
    - Fingers close together (compact hand shape)
    - NOT just fingertips near thumb (that's gripping a phone)
    """
    import cv2
    import mediapipe as mp
    if frame is None:
        return None
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    results = detector.detect(mp_img)
    if not results.hand_landmarks:
        return None
    lm = results.hand_landmarks[0]

    # Fingertips and their corresponding PIP (second knuckle) joints
    # A curled finger has its tip CLOSER to the wrist than its PIP
    tips = [lm[8], lm[12], lm[16], lm[20]]       # index, middle, ring, pinky tips
    pips = [lm[6], lm[10], lm[14], lm[18]]        # their PIP joints
    mcps = [lm[5], lm[9], lm[13], lm[17]]         # their MCP (knuckle) joints
    wrist = lm[0]

    # Check 1: Fingers must be curled — tip closer to wrist than PIP
    # Using Y because in image coords, curled fingers have tips below PIP
    fingers_curled = 0
    for tip, pip in zip(tips, pips):
        # Tip should be below PIP (larger Y = lower in frame) for a fist
        # OR tip closer to wrist than PIP is
        tip_to_wrist = ((tip.x - wrist.x)**2 + (tip.y - wrist.y)**2)**0.5
        pip_to_wrist = ((pip.x - wrist.x)**2 + (pip.y - wrist.y)**2)**0.5
        if tip_to_wrist < pip_to_wrist:
            fingers_curled += 1

    if fingers_curled < 3:  # need at least 3 of 4 fingers curled
        return None

    # Check 2: Hand should be compact — tips clustered together
    tip_xs = [t.x for t in tips]
    tip_ys = [t.y for t in tips]
    tip_spread = (max(tip_xs) - min(tip_xs)) + (max(tip_ys) - min(tip_ys))
    if tip_spread > 0.15:  # too spread out — open hand or gripping something wide
        return None

    # Check 3: Tips should be close to palm center (curled in, not extended)
    palm_cx = sum(lm[i].x for i in [0, 5, 9, 13, 17]) / 5
    palm_cy = sum(lm[i].y for i in [0, 5, 9, 13, 17]) / 5
    avg_tip_dist = sum(
        ((t.x - palm_cx)**2 + (t.y - palm_cy)**2)**0.5
        for t in tips
    ) / 4
    if avg_tip_dist > 0.12:  # tips too far from palm — not a tight fist
        return None

    return (palm_cx, palm_cy)


def _locate_fist_dual_camera():
    """Use front camera to find a fist and get direction. Returns (cx, cy) or None.

    Front camera sees the fist approaching — it has the wide stable view.
    The arm camera can't see something right in front of the gripper.
    The fist position in the front camera tells ALICE which direction to move.
    """
    import cv2
    import mediapipe as mp

    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    opts = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_get_hand_model_path()),
        running_mode=VisionRunningMode.IMAGE, num_hands=1,
        min_hand_detection_confidence=0.4,
    )
    det = HandLandmarker.create_from_options(opts)

    # Front camera for detection and direction
    frame = get_cam_frame() if _cam_running else get_cam2_frame()
    fist = None
    if frame is not None:
        fist = _detect_fist_in_frame(det, frame)

    det.close()
    return fist


def _execute_fist_bump(mc_instance, pre_bump_angles):
    """Fist bump using dual cameras.

    1. Both cameras locate the fist
    2. Close gripper
    3. Iterate: move toward fist, re-check arm camera, adjust (homing in)
    4. Hold contact
    5. Retract fast
    6. Open gripper, return
    """
    import time

    # Step 1: Front camera detects and gives direction
    fist_pos = _locate_fist_dual_camera()
    fist_offset_x = fist_pos[0] - 0.5 if fist_pos else 0.0
    fist_offset_y = fist_pos[1] - 0.5 if fist_pos else 0.0

    # Step 2: Close gripper — make a fist
    try:
        mc_instance.set_gripper_state(1, 100)
    except Exception:
        pass
    time.sleep(0.15)

    # Step 3: Get current position
    try:
        current = mc_instance.get_angles()
        if current == -1 or current is None:
            current = list(pre_bump_angles)
        else:
            current = list(current)
    except Exception:
        current = list(pre_bump_angles)

    # Step 4: Move toward fist — front camera tells us the direction
    bump_target = list(current)
    bump_target[0] -= fist_offset_x * 40   # base toward fist (wider range)
    bump_target[2] -= 15                     # extend elbow forward
    bump_target[3] -= fist_offset_y * 25    # wrist toward fist height
    bump_target[0] = max(-162, min(162, bump_target[0]))
    bump_target[2] = max(-92, min(60, bump_target[2]))
    bump_target[3] = max(-180, min(180, bump_target[3]))

    # Move — medium speed, deliberate
    try:
        mc_instance.send_angles(bump_target, 50)
    except Exception:
        pass
    time.sleep(0.6)

    # Step 5: Hold — the contact moment
    time.sleep(0.4)

    # Step 6: Retract FAST
    try:
        mc_instance.send_angles(list(pre_bump_angles), 90)
    except Exception:
        pass
    time.sleep(0.3)

    # Step 7: Open gripper
    try:
        mc_instance.set_gripper_state(0, 100)
    except Exception:
        pass
    time.sleep(0.15)


# ── Wander Mode ──────────────────────────────────────────────────

def _wander_loop():
    """ALICE scans her surroundings — curious, unhurried, alive.

    Not a mechanical sweep. She drifts between points of interest,
    pauses at some, lingers at others. Occasionally returns to center
    as if checking on you, then goes back to exploring.

    Uses sine waves with different periods on each joint so the path
    never exactly repeats — it feels organic.
    """
    import math
    import random

    global wandering

    # Base offsets from default position
    base = list(DEFAULT_ANGLES)

    # Scan parameters per joint — different periods create organic motion
    # [amplitude, period_seconds, phase_offset]
    j1_scan = [45.0, 8.0, 0.0]       # wide left-right sweep
    j2_scan = [12.0, 11.0, 1.0]      # slow vertical drift
    j3_scan = [15.0, 13.0, 2.5]      # elbow extension variation
    j4_scan = [20.0, 7.0, 0.5]       # wrist tilt — head movements

    t = 0.0
    last_send = 0
    pause_until = 0
    guard = ResistanceGuard()

    # Occasionally pause and linger — like she spotted something
    next_linger = time.time() + random.uniform(5, 12)
    linger_duration = 0

    while wandering and mc is not None:
        now = time.time()

        # Linger pause — she found something interesting
        if now < pause_until:
            time.sleep(0.05)
            continue

        # Schedule next linger
        if now > next_linger and linger_duration == 0:
            linger_duration = random.uniform(1.0, 3.0)
            pause_until = now + linger_duration
            next_linger = now + linger_duration + random.uniform(6, 15)
            linger_duration = 0
            continue

        t += 0.033

        # Organic scan — layered sine waves
        j1 = base[0] + j1_scan[0] * math.sin(2 * math.pi * t / j1_scan[1] + j1_scan[2])
        j2 = base[1] + j2_scan[0] * math.sin(2 * math.pi * t / j2_scan[1] + j2_scan[2])
        j3 = base[2] + j3_scan[0] * math.sin(2 * math.pi * t / j3_scan[1] + j3_scan[2])
        j4 = base[3] + j4_scan[0] * math.sin(2 * math.pi * t / j4_scan[1] + j4_scan[2])

        # Add micro-noise for liveliness
        j1 += random.gauss(0, 0.5)
        j4 += random.gauss(0, 0.3)

        # Clamp
        j1 = max(-162, min(162, j1))
        j2 = max(-2, min(90, j2))
        j3 = max(-92, min(60, j3))
        j4 = max(-180, min(180, j4))

        if now - last_send > 0.08:  # ~12fps — slow, deliberate
            angles = [round(j1, 1), round(j2, 1), round(j3, 1), round(j4, 1)]
            angles = guard.check(angles, mc)
            try:
                mc.send_angles(angles, 25)  # slow speed — she's browsing
                last_send = now
            except Exception:
                pass

        time.sleep(0.033)


def start_wander():
    global wandering, wander_thread
    if wandering:
        return
    stop_face_tracking()
    stop_hand_tracking()
    wandering = True
    wander_thread = threading.Thread(target=_wander_loop, daemon=True)
    wander_thread.start()


def stop_wander():
    global wandering, wander_thread
    wandering = False
    if wander_thread:
        wander_thread.join(timeout=2)
        wander_thread = None


def start_face_tracking():
    global face_tracking, face_tracking_thread
    if face_tracking:
        return
    face_tracking = True
    face_tracking_thread = threading.Thread(target=_face_tracking_loop, daemon=True)
    face_tracking_thread.start()


def stop_face_tracking():
    global face_tracking, face_tracking_thread
    face_tracking = False
    if face_tracking_thread:
        face_tracking_thread.join(timeout=2)
        face_tracking_thread = None


def gen_frames():
    import cv2
    while _cam_running:
        frame = get_cam_frame()
        if frame is None:
            time.sleep(0.05)
            continue
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)  # ~30fps


# ── Routes ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/status")
def api_status():
    return jsonify(connection_info)


@app.route("/api/ports")
def api_ports():
    return jsonify({"ports": list_serial_ports()})


@app.route("/api/connect", methods=["POST"])
def api_connect():
    data = request.json
    if data.get("type") == "wifi":
        ok = connect_wifi(data["ip"], data.get("port", 9000))
    else:
        ok = connect_serial(data["port"])
    return jsonify({"ok": ok, **connection_info})


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    disconnect()
    return jsonify({"ok": True})


@app.route("/api/angles", methods=["GET"])
def api_get_angles():
    if mc is None:
        return jsonify({"error": "not connected"})
    try:
        a = mc.get_angles()
        return jsonify({"angles": a})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/angles", methods=["POST"])
def api_set_angles():
    if mc is None:
        return jsonify({"error": "not connected"})
    data = request.json
    angles = data["angles"]
    speed = data.get("speed", 30)
    try:
        mc.send_angles(angles, speed)
        return jsonify({"ok": True, "sent": angles})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/gripper", methods=["POST"])
def api_gripper():
    if mc is None:
        return jsonify({"error": "not connected"})
    data = request.json
    try:
        if "state" in data:
            mc.set_gripper_state(data["state"], data.get("speed", 50))
        elif "value" in data:
            mc.set_gripper_value(data["value"], data.get("speed", 50))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/webcam/start", methods=["POST"])
def api_webcam_start():
    data = request.json or {}
    device_id = data.get("device_id", 0)
    if _cam2_device_id is not None and device_id == _cam2_device_id:
        return jsonify({"ok": False, "error": f"Camera {device_id} already used as secondary"})
    ok = start_webcam(device_id)
    return jsonify({"ok": ok})


@app.route("/api/webcam/stop", methods=["POST"])
def api_webcam_stop():
    stop_webcam()
    return jsonify({"ok": True})


_cached_devices = None

@app.route("/api/webcam2/start", methods=["POST"])
def api_webcam2_start():
    data = request.json or {}
    device_id = data.get("device_id", 1)

    # If the requested device is already used by primary, try the other one
    if _cam_device_id is not None and device_id == _cam_device_id:
        # Find an available device that isn't the primary
        for alt in range(3):
            if alt != _cam_device_id:
                device_id = alt
                break

    ok = start_webcam2(device_id)
    return jsonify({"ok": ok, "device_id": device_id})


@app.route("/api/webcam2/stop", methods=["POST"])
def api_webcam2_stop():
    stop_webcam2()
    return jsonify({"ok": True})


@app.route("/api/webcam/devices")
def api_webcam_devices():
    global _cached_devices
    import subprocess

    # Get camera names from macOS system_profiler (safe, no OpenCV)
    devices = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)
        for i, cam_info in enumerate(data.get("SPCameraDataType", [])):
            name = cam_info.get("_name", f"Camera {i}")
            model = cam_info.get("spcamera_model-id", "")
            devices.append({"id": i, "name": name})
    except Exception:
        devices = [{"id": i, "name": f"Camera {i}"} for i in range(3)]

    _cached_devices = devices
    return jsonify({"devices": devices})


@app.route("/video_feed")
def video_feed():
    if not _cam_running:
        return "", 204
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed2")
def video_feed2():
    if not _cam2_running:
        return "", 204

    def gen2():
        import cv2
        while _cam2_running:
            frame = get_cam2_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.033)

    return Response(gen2(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/face_tracking/start", methods=["POST"])
def api_face_tracking_start():
    if mc is None:
        return jsonify({"error": "arm not connected"})
    if cam is None or not cam.isOpened():
        return jsonify({"error": "webcam not started"})
    start_face_tracking()
    return jsonify({"ok": True})


@app.route("/api/face_tracking/stop", methods=["POST"])
def api_face_tracking_stop():
    stop_face_tracking()
    return jsonify({"ok": True})


@app.route("/api/face_tracking/status")
def api_face_tracking_status():
    return jsonify({"active": face_tracking})


@app.route("/api/hand_tracking/start", methods=["POST"])
def api_hand_tracking_start():
    if mc is None:
        return jsonify({"error": "arm not connected"})
    if not _cam_running:
        return jsonify({"error": "webcam not started"})
    stop_face_tracking()  # can't run both at once
    start_hand_tracking()
    return jsonify({"ok": True})


@app.route("/api/hand_tracking/stop", methods=["POST"])
def api_hand_tracking_stop():
    stop_hand_tracking()
    return jsonify({"ok": True})


@app.route("/api/wander/start", methods=["POST"])
def api_wander_start():
    if mc is None:
        return jsonify({"error": "not connected"})
    start_wander()
    return jsonify({"ok": True})


@app.route("/api/wander/stop", methods=["POST"])
def api_wander_stop():
    stop_wander()
    return jsonify({"ok": True})


@app.route("/api/tracking/sensitivity", methods=["POST"])
def api_tracking_sensitivity():
    global tracking_v_sensitivity
    data = request.json or {}
    tracking_v_sensitivity = max(0.5, min(5.0, float(data.get("vertical", 1.0))))
    return jsonify({"ok": True, "vertical": tracking_v_sensitivity})


@app.route("/api/dance", methods=["POST"])
def api_dance():
    if mc is None:
        return jsonify({"error": "not connected"})
    s = request.json.get("speed", 40) if request.json else 40

    def routine():
        mc.send_angles([0, 0, 0, 0], s)
        time.sleep(1.5)
        for _ in range(3):
            mc.send_angles([0, 20, 10, 0], s + 10)
            time.sleep(0.4)
            mc.send_angles([0, 5, 0, 0], s + 10)
            time.sleep(0.4)
        for _ in range(2):
            mc.send_angles([-30, 15, 5, 0], s + 10)
            time.sleep(0.5)
            mc.send_angles([30, 15, 5, 0], s + 10)
            time.sleep(0.5)
        for _ in range(3):
            mc.send_angles([0, 25, 10, 30], s + 20)
            time.sleep(0.3)
            mc.send_angles([0, 25, 10, -30], s + 20)
            time.sleep(0.3)
        mc.send_angles([0, 50, -40, 0], int(s * 0.6))
        time.sleep(1.5)
        mc.send_angles([0, 0, 0, 0], int(s * 0.5))
        time.sleep(1.5)

    threading.Thread(target=routine, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/fistbump", methods=["POST"])
def api_fistbump():
    if mc is None:
        return jsonify({"error": "not connected"})
    if not _cam_running and not _cam2_running:
        return jsonify({"error": "need at least one camera running"})

    def routine():
        # Save current position to return to
        try:
            current = mc.get_angles()
            if current == -1 or current is None:
                current = list(DEFAULT_ANGLES)
            else:
                current = list(current)
        except Exception:
            current = list(DEFAULT_ANGLES)

        _execute_fist_bump(mc, current)

    threading.Thread(target=routine, daemon=True).start()
    return jsonify({"ok": True})


# ── HTML ─────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ALICE Arm Test</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0a0a1a; color: #e0e0e0; font-family: -apple-system, sans-serif; padding: 20px; }
  h1 { color: #e94560; margin-bottom: 5px; font-size: 24px; }
  .subtitle { color: #555; font-size: 12px; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; max-width: 1000px; }
  .panel { background: #12122a; border: 1px solid #1a1a3a; border-radius: 10px; padding: 15px; }
  .panel h2 { color: #e94560; font-size: 14px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
  .panel.full { grid-column: 1 / -1; }

  /* Connection */
  .status { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .status.connected { background: #50fa7b; }
  .status.disconnected { background: #e94560; }
  .status.error { background: #f1c40f; }
  .conn-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; flex-wrap: wrap; }
  select, input[type=text], input[type=number] { background: #1a1a3a; border: 1px solid #2a2a4a; color: #e0e0e0; padding: 6px 10px; border-radius: 5px; font-size: 13px; }
  select { min-width: 220px; }
  input[type=text] { width: 140px; }
  input[type=number] { width: 70px; }

  /* Buttons */
  .btn { background: #1a1a3a; border: 1px solid #2a2a4a; color: #e0e0e0; padding: 6px 14px; border-radius: 5px; cursor: pointer; font-size: 12px; transition: all 0.15s; }
  .btn:hover { background: #2a2a5a; }
  .btn.primary { background: #e94560; border-color: #e94560; color: white; }
  .btn.primary:hover { background: #c73650; }
  .btn.green { background: #1a4a2a; border-color: #2a6a3a; color: #50fa7b; }
  .btn.green:hover { background: #2a6a3a; }
  .btn.small { padding: 4px 10px; font-size: 11px; }

  /* Sliders */
  .joint-row { display: flex; align-items: center; margin-bottom: 8px; gap: 8px; }
  .joint-label { width: 25px; font-weight: bold; color: #8888bb; font-size: 13px; }
  .joint-range { flex: 1; }
  input[type=range] { width: 100%; accent-color: #e94560; }
  .joint-val { width: 45px; text-align: right; font-family: monospace; font-size: 13px; color: #e94560; }
  .joint-input { width: 60px; background: #1a1a3a; border: 1px solid #2a2a4a; color: #e0e0e0; padding: 3px 6px; border-radius: 4px; font-size: 12px; font-family: monospace; text-align: center; }
  .joint-limits { font-size: 10px; color: #555; width: 80px; text-align: center; }

  /* Speed */
  .speed-row { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
  .speed-row label { color: #8888bb; font-size: 13px; }
  .speed-val { color: #e94560; font-weight: bold; font-size: 14px; }

  /* Gripper */
  .grip-row { display: flex; align-items: center; gap: 8px; }

  /* Presets */
  .preset-grid { display: flex; flex-wrap: wrap; gap: 6px; }

  /* Webcam */
  .cam-feed { width: 100%; border-radius: 8px; background: #000; min-height: 200px; }
  .cam-controls { display: flex; gap: 8px; margin-bottom: 10px; align-items: center; flex-wrap: wrap; }

  /* Actions */
  .action-grid { display: flex; gap: 8px; flex-wrap: wrap; }

  /* Readout */
  .readout { font-family: monospace; font-size: 12px; color: #555; margin-top: 8px; min-height: 18px; }

  /* Custom angles */
  .custom-row { display: flex; gap: 6px; align-items: center; margin-top: 10px; }
  .custom-row input { width: 55px; }

  @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<h1>A.L.I.C.E. Arm Test</h1>
<p class="subtitle">MyPalletizer 260 — Joint Control, Webcam, Choreography</p>

<div class="grid">

  <!-- Connection -->
  <div class="panel">
    <h2>Connection</h2>
    <div class="conn-row">
      <span class="status disconnected" id="statusDot"></span>
      <span id="statusText">Disconnected</span>
    </div>
    <div class="conn-row">
      <select id="connType" onchange="toggleConnType()">
        <option value="serial">USB Serial</option>
        <option value="wifi">WiFi</option>
      </select>
    </div>
    <div class="conn-row" id="serialRow">
      <select id="portSelect"><option>Scanning...</option></select>
      <button class="btn small" onclick="scanPorts()">Scan</button>
    </div>
    <div class="conn-row" id="wifiRow" style="display:none">
      <input type="text" id="wifiIp" placeholder="192.168.1.87">
      <input type="number" id="wifiPort" value="9000" placeholder="9000">
    </div>
    <div class="conn-row">
      <button class="btn green" onclick="doConnect()">Connect</button>
      <button class="btn" onclick="doDisconnect()">Disconnect</button>
    </div>
  </div>

  <!-- Webcam -->
  <div class="panel">
    <h2>Webcam</h2>
    <div class="cam-controls">
      <select id="camDevice"><option value="0">Camera 0</option></select>
      <button class="btn small green" onclick="startCam()">Start</button>
      <button class="btn small" onclick="stopCam()">Stop</button>
      <button class="btn small" onclick="scanCams()">Scan</button>
    </div>
    <div class="cam-controls">
      <button class="btn small primary" id="faceTrackBtn" onclick="toggleFaceTrack()">Face Track: OFF</button>
      <button class="btn small primary" id="handTrackBtn" onclick="toggleHandTrack()">Hand Track: OFF</button>
      <button class="btn small primary" id="wanderBtn" onclick="toggleWander()">Wander: OFF</button>
      <span id="trackStatus" style="font-size:11px;color:#555;">Requires cam + arm</span>
    </div>
    <div class="cam-controls">
      <span style="font-size:11px;color:#8888bb;">V-Sensitivity:</span>
      <input type="range" id="vSensSlider" min="50" max="500" value="100" style="width:120px" oninput="setVSens(this.value)">
      <span id="vSensVal" style="font-size:11px;color:#e94560;">1.0x</span>
    </div>
    <div style="display:flex;gap:8px;">
      <div style="flex:1;">
        <div style="font-size:10px;color:#555;margin-bottom:4px;">Primary (front)</div>
        <img id="camFeed" class="cam-feed" src="" style="display:none;width:100%">
        <div id="camPlaceholder" class="cam-feed" style="display:flex;align-items:center;justify-content:center;color:#333;font-size:11px;min-height:150px;">
          No feed
        </div>
      </div>
      <div style="flex:1;">
        <div style="font-size:10px;color:#555;margin-bottom:4px;">Secondary (arm)</div>
        <img id="cam2Feed" class="cam-feed" src="" style="display:none;width:100%">
        <div id="cam2Placeholder" class="cam-feed" style="display:flex;align-items:center;justify-content:center;color:#333;font-size:11px;min-height:150px;">
          No feed
        </div>
      </div>
    </div>
    <div style="margin-top:10px;border-top:1px solid #1a1a3a;padding-top:10px;">
      <div class="cam-controls">
        <span style="font-size:11px;color:#8888bb;">Secondary (arm cam):</span>
        <button class="btn small green" onclick="startCam2()">Start</button>
        <button class="btn small" onclick="stopCam2()">Stop</button>
        <span id="cam2Status" style="font-size:11px;color:#555;">Off</span>
      </div>
    </div>
  </div>

  <!-- Joints -->
  <div class="panel full">
    <h2>Joints</h2>
    <div id="joints"></div>
    <div class="speed-row">
      <label>Speed:</label>
      <input type="range" id="speedSlider" min="5" max="100" value="30" style="width:200px" oninput="speedVal.textContent=this.value">
      <span class="speed-val" id="speedVal">30</span>
    </div>
    <div class="custom-row">
      <span style="color:#8888bb;font-size:12px">Custom:</span>
      <input type="number" id="cj1" placeholder="j1" class="joint-input">
      <input type="number" id="cj2" placeholder="j2" class="joint-input">
      <input type="number" id="cj3" placeholder="j3" class="joint-input">
      <input type="number" id="cj4" placeholder="j4" class="joint-input">
      <button class="btn small primary" onclick="sendCustom()">Send</button>
      <button class="btn small" onclick="readAngles()">Read</button>
    </div>
    <div class="readout" id="readout"></div>
  </div>

  <!-- Gripper -->
  <div class="panel">
    <h2>Gripper</h2>
    <div class="grip-row">
      <button class="btn green" onclick="gripOpen()">Open</button>
      <button class="btn primary" onclick="gripClose()">Close</button>
      <input type="range" id="gripSlider" min="0" max="100" value="0" style="flex:1" oninput="gripVal(this.value)">
      <span id="gripValue" style="color:#e94560;font-family:monospace;width:30px">0</span>
    </div>
  </div>

  <!-- Presets & Actions -->
  <div class="panel">
    <h2>Presets</h2>
    <div class="preset-grid" id="presets"></div>
    <h2 style="margin-top:15px">Actions</h2>
    <div class="action-grid">
      <button class="btn primary" onclick="doDance()">Dance</button>
      <button class="btn primary" onclick="doFistBump()">Fist Bump</button>
      <button class="btn" onclick="sendAngles([0,0,0,0])">Home</button>
    </div>
  </div>

</div>

<script>
const JOINTS = [
  { name: "j1", label: "J1", min: -162, max: 162, desc: "Base rotation" },
  { name: "j2", label: "J2", min: -2, max: 90, desc: "Shoulder" },
  { name: "j3", label: "J3", min: -92, max: 60, desc: "Elbow" },
  { name: "j4", label: "J4", min: -180, max: 180, desc: "Wrist" },
];

const PRESETS = {
  "Home": [0,0,0,0],
  "Default": [-33,-2,-72,43],
  "Sleep": [-14,38,-31,36],
  "Reach": [0,50,-30,0],
  "Bump": [-33,10,-72,43],
  "Wave": [-33,-2,-72,80],
  "Left": [-80,-2,-72,43],
  "Right": [20,-2,-72,43],
};

// Build joint sliders
const jointsEl = document.getElementById("joints");
JOINTS.forEach((j, i) => {
  jointsEl.innerHTML += `
    <div class="joint-row">
      <span class="joint-label">${j.label}</span>
      <span class="joint-limits">${j.min}°</span>
      <div class="joint-range">
        <input type="range" id="slider_${j.name}" min="${j.min}" max="${j.max}" value="0"
               oninput="onSlider('${j.name}', this.value)">
      </div>
      <span class="joint-limits">${j.max}°</span>
      <input type="number" class="joint-input" id="input_${j.name}" value="0"
             onchange="onInput('${j.name}', this.value)">
      <span class="joint-val" id="val_${j.name}">0°</span>
    </div>`;
});

// Build presets
const presetsEl = document.getElementById("presets");
Object.entries(PRESETS).forEach(([name, angles]) => {
  presetsEl.innerHTML += `<button class="btn small" onclick='goPreset(${JSON.stringify(angles)},"${name}")'>${name}</button>`;
});

let sending = false;
let sendTimeout = null;

function onSlider(name, val) {
  val = parseInt(val);
  document.getElementById("val_" + name).textContent = val + "°";
  document.getElementById("input_" + name).value = val;
  scheduleSend();
}

function onInput(name, val) {
  val = parseInt(val) || 0;
  const j = JOINTS.find(j => j.name === name);
  val = Math.max(j.min, Math.min(j.max, val));
  document.getElementById("slider_" + name).value = val;
  document.getElementById("val_" + name).textContent = val + "°";
  scheduleSend();
}

function scheduleSend() {
  if (sendTimeout) clearTimeout(sendTimeout);
  sendTimeout = setTimeout(() => {
    const angles = JOINTS.map(j => parseInt(document.getElementById("slider_" + j.name).value));
    sendAngles(angles);
  }, 50);
}

function sendAngles(angles) {
  const speed = parseInt(document.getElementById("speedSlider").value);
  fetch("/api/angles", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({angles, speed})
  }).then(r => r.json()).then(d => {
    if (d.error) setReadout("Error: " + d.error);
    else setReadout("Sent: [" + angles.join(", ") + "] @ speed " + speed);
  });
}

function sendCustom() {
  const angles = ["cj1","cj2","cj3","cj4"].map(id => parseFloat(document.getElementById(id).value) || 0);
  const speed = parseInt(document.getElementById("speedSlider").value);
  // Update sliders
  JOINTS.forEach((j, i) => {
    document.getElementById("slider_" + j.name).value = angles[i];
    document.getElementById("val_" + j.name).textContent = angles[i] + "°";
    document.getElementById("input_" + j.name).value = angles[i];
  });
  sendAngles(angles);
}

function readAngles() {
  fetch("/api/angles").then(r => r.json()).then(d => {
    if (d.angles && d.angles !== -1) {
      JOINTS.forEach((j, i) => {
        const v = Math.round(d.angles[i]);
        document.getElementById("slider_" + j.name).value = v;
        document.getElementById("val_" + j.name).textContent = v + "°";
        document.getElementById("input_" + j.name).value = v;
      });
      setReadout("Read: [" + d.angles.map(v => v.toFixed(1)).join(", ") + "]");
    } else {
      setReadout("Read: -1 (no response)");
    }
  });
}

function goPreset(angles, name) {
  JOINTS.forEach((j, i) => {
    document.getElementById("slider_" + j.name).value = angles[i];
    document.getElementById("val_" + j.name).textContent = angles[i] + "°";
    document.getElementById("input_" + j.name).value = angles[i];
  });
  sendAngles(angles);
  setReadout("Preset: " + name);
}

// Gripper
function gripOpen() { fetch("/api/gripper", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:0})}); document.getElementById("gripSlider").value=0; document.getElementById("gripValue").textContent="0"; }
function gripClose() { fetch("/api/gripper", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state:1})}); document.getElementById("gripSlider").value=100; document.getElementById("gripValue").textContent="100"; }
function gripVal(v) { document.getElementById("gripValue").textContent=v; fetch("/api/gripper", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:parseInt(v)})}); }

// Connection
function toggleConnType() {
  const t = document.getElementById("connType").value;
  document.getElementById("serialRow").style.display = t === "serial" ? "flex" : "none";
  document.getElementById("wifiRow").style.display = t === "wifi" ? "flex" : "none";
}

function scanPorts() {
  fetch("/api/ports").then(r => r.json()).then(d => {
    const sel = document.getElementById("portSelect");
    sel.innerHTML = "";
    if (d.ports.length === 0) {
      sel.innerHTML = "<option>No ports found</option>";
    } else {
      d.ports.forEach(p => { sel.innerHTML += `<option value="${p}">${p.split("/").pop()}</option>`; });
    }
  });
}

function doConnect() {
  const t = document.getElementById("connType").value;
  let body;
  if (t === "wifi") {
    body = {type:"wifi", ip: document.getElementById("wifiIp").value, port: parseInt(document.getElementById("wifiPort").value)};
  } else {
    body = {type:"serial", port: document.getElementById("portSelect").value};
  }
  fetch("/api/connect", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
    .then(r => r.json()).then(updateStatus);
}

function doDisconnect() {
  fetch("/api/disconnect", {method:"POST"}).then(() => updateStatus({status:"disconnected"}));
}

function updateStatus(d) {
  const dot = document.getElementById("statusDot");
  const txt = document.getElementById("statusText");
  const s = d.status || "disconnected";
  dot.className = "status " + (s === "connected" ? "connected" : s.startsWith("error") ? "error" : "disconnected");
  txt.textContent = s === "connected" ? `Connected (${d.port || ""})` : s;
  if (d.angles) {
    JOINTS.forEach((j, i) => {
      const v = Math.round(d.angles[i]);
      document.getElementById("slider_" + j.name).value = v;
      document.getElementById("val_" + j.name).textContent = v + "°";
      document.getElementById("input_" + j.name).value = v;
    });
  }
}

// Webcam
function scanCams() {
  fetch("/api/webcam/devices").then(r=>r.json()).then(d => {
    const sel = document.getElementById("camDevice");
    sel.innerHTML = "";
    d.devices.forEach(c => {
      sel.innerHTML += `<option value="${c.id}">${c.name} (${c.id})</option>`;
    });
    if (d.devices.length === 0) {
      sel.innerHTML = "<option>No cameras</option>";
    }
  });
}

function startCam() {
  const dev = parseInt(document.getElementById("camDevice").value) || 0;
  fetch("/api/webcam/start", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:dev})})
    .then(r=>r.json()).then(d => {
      if (d.ok) {
        document.getElementById("camFeed").src = "/video_feed?" + Date.now();
        document.getElementById("camFeed").style.display = "block";
        document.getElementById("camPlaceholder").style.display = "none";
      } else {
        document.getElementById("camPlaceholder").textContent = d.error || "Failed";
      }
    });
}

function stopCam() {
  fetch("/api/webcam/stop", {method:"POST"});
  document.getElementById("camFeed").style.display = "none";
  document.getElementById("camPlaceholder").style.display = "flex";
}

function startCam2() {
  // Just request — server will pick whichever device isn't primary
  fetch("/api/webcam2/start", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:0})})
    .then(r=>r.json()).then(d => {
      if (d.ok) {
        document.getElementById("cam2Status").textContent = "Running";
        document.getElementById("cam2Status").style.color = "#50fa7b";
        document.getElementById("cam2Feed").src = "/video_feed2?" + Date.now();
        document.getElementById("cam2Feed").style.display = "block";
        document.getElementById("cam2Placeholder").style.display = "none";
      } else {
        document.getElementById("cam2Status").textContent = d.error || "Failed";
        document.getElementById("cam2Status").style.color = "#e94560";
      }
    });
}

function stopCam2() {
  fetch("/api/webcam2/stop", {method:"POST"});
  document.getElementById("cam2Status").textContent = "Off";
  document.getElementById("cam2Status").style.color = "#555";
  document.getElementById("cam2Feed").style.display = "none";
  document.getElementById("cam2Placeholder").style.display = "flex";
}

// Actions
// Face tracking
let faceTrackActive = false;
let handTrackActive = false;

function setTrackStatus(msg) { document.getElementById("trackStatus").textContent = msg; }

function toggleFaceTrack() {
  if (faceTrackActive) {
    fetch("/api/face_tracking/stop", {method:"POST"}).then(() => {
      faceTrackActive = false;
      document.getElementById("faceTrackBtn").textContent = "Face Track: OFF";
      document.getElementById("faceTrackBtn").classList.remove("green");
      document.getElementById("faceTrackBtn").classList.add("primary");
      setTrackStatus("Stopped");
    });
  } else {
    if (handTrackActive) toggleHandTrack();
    if (wanderActive) toggleWander();
    fetch("/api/face_tracking/start", {method:"POST"}).then(r=>r.json()).then(d => {
      if (d.ok) {
        faceTrackActive = true;
        document.getElementById("faceTrackBtn").textContent = "Face Track: ON";
        document.getElementById("faceTrackBtn").classList.remove("primary");
        document.getElementById("faceTrackBtn").classList.add("green");
        setTrackStatus("Tracking face");
      } else {
        setTrackStatus(d.error || "Failed");
      }
    });
  }
}

function toggleHandTrack() {
  if (handTrackActive) {
    fetch("/api/hand_tracking/stop", {method:"POST"}).then(() => {
      handTrackActive = false;
      document.getElementById("handTrackBtn").textContent = "Hand Track: OFF";
      document.getElementById("handTrackBtn").classList.remove("green");
      document.getElementById("handTrackBtn").classList.add("primary");
      setTrackStatus("Stopped");
    });
  } else {
    if (faceTrackActive) toggleFaceTrack();
    if (wanderActive) toggleWander();
    fetch("/api/hand_tracking/start", {method:"POST"}).then(r=>r.json()).then(d => {
      if (d.ok) {
        handTrackActive = true;
        document.getElementById("handTrackBtn").textContent = "Hand Track: ON";
        document.getElementById("handTrackBtn").classList.remove("primary");
        document.getElementById("handTrackBtn").classList.add("green");
        setTrackStatus("Tracking hand — fist to close gripper, open to release");
      } else {
        setTrackStatus(d.error || "Failed");
      }
    });
  }
}

// Wander
let wanderActive = false;
function toggleWander() {
  if (wanderActive) {
    fetch("/api/wander/stop", {method:"POST"}).then(() => {
      wanderActive = false;
      document.getElementById("wanderBtn").textContent = "Wander: OFF";
      document.getElementById("wanderBtn").classList.remove("green");
      document.getElementById("wanderBtn").classList.add("primary");
      setTrackStatus("Stopped");
    });
  } else {
    if (faceTrackActive) toggleFaceTrack();
    if (handTrackActive) toggleHandTrack();
    fetch("/api/wander/start", {method:"POST"}).then(r=>r.json()).then(d => {
      if (d.ok) {
        wanderActive = true;
        document.getElementById("wanderBtn").textContent = "Wander: ON";
        document.getElementById("wanderBtn").classList.remove("primary");
        document.getElementById("wanderBtn").classList.add("green");
        setTrackStatus("Scanning surroundings");
      } else {
        setTrackStatus(d.error || "Failed");
      }
    });
  }
}

function setVSens(val) {
  const v = parseInt(val) / 100;
  document.getElementById("vSensVal").textContent = v.toFixed(1) + "x";
  fetch("/api/tracking/sensitivity", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({vertical:v})});
}

function doDance() { fetch("/api/dance", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({speed:parseInt(document.getElementById("speedSlider").value)})}); setReadout("Dancing..."); }
function doFistBump() { fetch("/api/fistbump", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({speed:parseInt(document.getElementById("speedSlider").value)})}); setReadout("Fist bump..."); }

function setReadout(msg) { document.getElementById("readout").textContent = msg; }

// Init — scan ports only, cameras scanned on demand to avoid OpenCV segfault
scanPorts();
fetch("/api/status").then(r=>r.json()).then(updateStatus);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=str)
    parser.add_argument("--wifi", type=str)
    parser.add_argument("--wifi-port", type=int, default=9000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--web-port", type=int, default=5050)
    args = parser.parse_args()

    # Auto-connect if args provided
    if args.wifi:
        connect_wifi(args.wifi, args.wifi_port)
    elif args.port:
        connect_serial(args.port)
    else:
        ports = list_serial_ports()
        if ports:
            connect_serial(ports[0])

    print(f"\n  ALICE Arm Test UI: http://localhost:{args.web_port}\n")
    app.run(host=args.host, port=args.web_port, debug=False, threaded=True)
