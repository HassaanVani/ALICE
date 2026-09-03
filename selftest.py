"""Startup self-test for A.L.I.C.E. — verifies cameras, hardware, models, ports."""

import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

logger = logging.getLogger("SelfTest")


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    duration_ms: float


class SelfTest:
    def __init__(self, simulate: bool = True):
        self.simulate = simulate
        self.results: List[CheckResult] = []

    def _run_check(self, name: str, check_fn) -> CheckResult:
        start = time.perf_counter()
        try:
            passed, message = check_fn()
        except Exception as e:
            passed, message = False, str(e)
        duration_ms = (time.perf_counter() - start) * 1000
        result = CheckResult(name=name, passed=passed, message=message, duration_ms=duration_ms)
        self.results.append(result)
        return result

    def check_cameras(self) -> CheckResult:
        def _check():
            if self.simulate:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                return frame is not None, "Synthetic frame OK"
            try:
                import cv2
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    return False, "Camera 0 failed to open"
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    return True, f"Camera 0 OK ({frame.shape[1]}x{frame.shape[0]})"
                return False, "Camera 0 read failed"
            except Exception as e:
                return False, f"Camera error: {e}"
        return self._run_check("Cameras", _check)

    def check_arm_connection(self) -> CheckResult:
        def _check():
            if self.simulate:
                return True, "Simulated arm OK"
            try:
                from hardware import ArmController
                arm = ArmController(simulate=False)
                connected = arm.connect()
                arm.disconnect()
                return connected, "Arm connected" if connected else "Arm connection failed"
            except Exception as e:
                return False, f"Arm error: {e}"
        return self._run_check("Arm Connection", _check)

    def check_magnet(self) -> CheckResult:
        def _check():
            if self.simulate:
                return True, "Simulated magnet OK"
            try:
                from hardware import MagnetDriver
                mag = MagnetDriver(simulate=False)
                connected = mag.connect()
                mag.disconnect()
                return connected, "Magnet OK" if connected else "Magnet connection failed"
            except Exception as e:
                return False, f"Magnet error: {e}"
        return self._run_check("Magnet", _check)

    def check_calibration_file(self) -> CheckResult:
        def _check():
            path = Path("calibration_data.json")
            if path.exists():
                return True, f"Calibration file found ({path.stat().st_size} bytes)"
            return False, "calibration_data.json not found (will use default mapping)"
        return self._run_check("Calibration File", _check)

    def check_cnn_weights(self) -> CheckResult:
        def _check():
            path = Path(__file__).parent / "brain" / "weights" / "block_recognizer.pth"
            if path.exists():
                size_kb = path.stat().st_size / 1024
                return True, f"CNN weights found ({size_kb:.0f} KB)"
            return False, "block_recognizer.pth not found (run brain.train first)"
        return self._run_check("CNN Weights", _check)

    def check_aruco_detection(self) -> CheckResult:
        def _check():
            import cv2
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            marker = cv2.aruco.generateImageMarker(dictionary, 0, 200)
            canvas = np.full((300, 300), 200, dtype=np.uint8)
            canvas[50:250, 50:250] = marker

            detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
            corners, ids, _ = detector.detectMarkers(canvas)
            if ids is not None and len(ids) > 0:
                return True, f"ArUco detection OK (found marker {ids[0][0]})"
            return False, "ArUco detection failed on synthetic marker"
        return self._run_check("ArUco Detection", _check)

    def check_websocket_port(self, port: int, name: str = "WebSocket") -> CheckResult:
        def _check():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            try:
                result = sock.connect_ex(("localhost", port))
                if result != 0:
                    return True, f"Port {port} available"
                return False, f"Port {port} already in use"
            finally:
                sock.close()
        return self._run_check(f"{name} Port ({port})", _check)

    def check_yolo(self) -> CheckResult:
        def _check():
            try:
                import ultralytics
                return True, f"Ultralytics YOLOv8 OK (v{ultralytics.__version__})"
            except ImportError:
                return False, "ultralytics not installed ('pip install ultralytics' for desk object detection)"
        return self._run_check("YOLO Detector", _check)

    def check_ollama(self) -> CheckResult:
        def _check():
            import urllib.request
            import json
            try:
                req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                data = json.loads(req.read().decode())
                models = [m.get("name") for m in data.get("models", [])]
                if "llama3.2:3b" in models or any("llama3.2" in m for m in models):
                    return True, f"Ollama running with llama3.2 ({len(models)} models available)"
                elif models:
                    return True, f"Ollama running ({', '.join(models[:3])})"
                return False, "Ollama running but no models found ('ollama pull llama3.2:3b')"
            except Exception as e:
                return False, f"Ollama not running on http://localhost:11434 ({e})"
        return self._run_check("Local LLM (Ollama)", _check)

    def run_all(self, ws_ports: List[int] = None) -> List[CheckResult]:
        """Run all self-test checks."""
        self.results.clear()

        self.check_cameras()
        self.check_arm_connection()
        self.check_magnet()
        self.check_calibration_file()
        self.check_cnn_weights()
        self.check_yolo()
        self.check_ollama()

        for port in (ws_ports or [8765, 8766, 8767]):
            self.check_websocket_port(port)

        self._print_report()
        return self.results

    def _print_report(self) -> None:
        """Print formatted pass/fail table."""
        width = 65
        print("\n" + "=" * width)
        print("  A.L.I.C.E. Self-Test Report")
        print("=" * width)

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        for r in self.results:
            status = "PASS" if r.passed else "WARN"
            icon = "+" if r.passed else "!"
            name_padded = r.name.ljust(22)
            dur = f"{r.duration_ms:.0f}ms".rjust(6)
            print(f"  [{icon}] {name_padded} {status}  {dur}  {r.message}")

        print("-" * width)
        print(f"  Result: {passed}/{total} checks passed")
        if passed < total:
            print("  (Warnings only — system will gracefully continue with fallbacks)")
        print("=" * width + "\n")

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ALICE Self-Test Diagnostic")
    parser.add_argument("--hardware", action="store_true", help="Test real hardware instead of simulated")
    args = parser.parse_args()

    st = SelfTest(simulate=not args.hardware)
    st.run_all()
