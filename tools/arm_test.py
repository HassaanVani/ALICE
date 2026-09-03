"""ALICE Arm Test UI — interactive joint control and choreography testing.

Usage:
    python tools/arm_test.py                    # USB serial (auto-detect)
    python tools/arm_test.py --wifi 192.168.1.87  # WiFi socket
    python tools/arm_test.py --port /dev/tty.usbserial-XXXXX  # specific port

Controls:
    Sliders:  j1 (base), j2 (shoulder), j3 (elbow), j4 (wrist)
    Gripper:  open / close / slider
    Presets:  home, reach, bump, bow
    Speed:    global speed slider
    Dance:    run the dance routine
"""

import sys
import time
import threading
import tkinter as tk
from tkinter import ttk


def connect(args):
    """Connect to the arm via serial or WiFi."""
    if args.wifi:
        from pymycobot.mypalletizersocket import MyPalletizerSocket
        mc = MyPalletizerSocket(args.wifi, args.wifi_port)
        time.sleep(1)
        print(f"Connected via WiFi: {args.wifi}:{args.wifi_port}")
    else:
        from pymycobot.mypalletizer260 import MyPalletizer260
        port = args.port
        if port is None:
            import glob
            ports = glob.glob("/dev/tty.usbserial-*")
            if not ports:
                print("No USB serial port found. Use --wifi or --port.")
                sys.exit(1)
            port = ports[0]
        mc = MyPalletizer260(port, 115200)
        time.sleep(2)
        print(f"Connected via serial: {port}")

    a = mc.get_angles()
    print(f"Initial angles: {a}")
    return mc


class ArmTestUI:
    # Joint limits for MyPalletizer 260
    JOINT_LIMITS = {
        "j1": (-162, 162),
        "j2": (-2, 90),
        "j3": (-92, 60),
        "j4": (-180, 180),
    }

    PRESETS = {
        "Home":     [0, 0, 0, 0],
        "Reach":    [0, 50, -30, 0],
        "Bump":     [0, 60, -40, 0],
        "Bow":      [0, 60, -50, 0],
        "Wave Hi":  [0, 40, -20, 30],
        "Look Up":  [0, 90, 60, 0],
        "Left":     [-60, 30, -15, 0],
        "Right":    [60, 30, -15, 0],
    }

    def __init__(self, mc):
        self.mc = mc
        self.speed = 30
        self.sending = False

        self.root = tk.Tk()
        self.root.title("ALICE Arm Test")
        self.root.geometry("500x700")
        self.root.configure(bg="#1a1a2e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TScale", background="#1a1a2e")
        style.configure("TButton", padding=6)
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0")
        style.configure("TLabelframe", background="#1a1a2e", foreground="#e0e0e0")
        style.configure("TLabelframe.Label", background="#1a1a2e", foreground="#e0e0e0")

        self._build_ui()
        self._read_angles()

    def _build_ui(self):
        # Title
        title = tk.Label(self.root, text="A.L.I.C.E. Arm Test",
                         font=("Helvetica", 18, "bold"),
                         bg="#1a1a2e", fg="#e94560")
        title.pack(pady=10)

        # Status
        self.status_var = tk.StringVar(value="Connected")
        status = tk.Label(self.root, textvariable=self.status_var,
                         font=("Helvetica", 10), bg="#1a1a2e", fg="#50fa7b")
        status.pack()

        # Joint sliders
        joint_frame = ttk.LabelFrame(self.root, text="Joints", padding=10)
        joint_frame.pack(fill="x", padx=15, pady=10)

        self.sliders = {}
        self.labels = {}
        for name, (lo, hi) in self.JOINT_LIMITS.items():
            row = tk.Frame(joint_frame, bg="#1a1a2e")
            row.pack(fill="x", pady=2)

            lbl = tk.Label(row, text=f"{name}:", width=4,
                          font=("Helvetica", 11), bg="#1a1a2e", fg="#e0e0e0")
            lbl.pack(side="left")

            val_lbl = tk.Label(row, text="0°", width=6,
                              font=("Helvetica", 11, "bold"),
                              bg="#1a1a2e", fg="#e94560")
            val_lbl.pack(side="right")
            self.labels[name] = val_lbl

            slider = tk.Scale(row, from_=lo, to=hi, orient="horizontal",
                            bg="#16213e", fg="#e0e0e0", troughcolor="#0f3460",
                            highlightthickness=0, length=300,
                            command=lambda v, n=name: self._on_slider(n, v))
            slider.pack(side="left", fill="x", expand=True, padx=5)
            self.sliders[name] = slider

        # Speed slider
        speed_frame = ttk.LabelFrame(self.root, text="Speed", padding=10)
        speed_frame.pack(fill="x", padx=15, pady=5)

        self.speed_label = tk.Label(speed_frame, text="30",
                                    font=("Helvetica", 11, "bold"),
                                    bg="#1a1a2e", fg="#e94560")
        self.speed_label.pack(side="right")

        self.speed_slider = tk.Scale(speed_frame, from_=5, to=100,
                                    orient="horizontal",
                                    bg="#16213e", fg="#e0e0e0",
                                    troughcolor="#0f3460",
                                    highlightthickness=0,
                                    command=self._on_speed)
        self.speed_slider.set(30)
        self.speed_slider.pack(fill="x", padx=5)

        # Gripper
        grip_frame = ttk.LabelFrame(self.root, text="Gripper", padding=10)
        grip_frame.pack(fill="x", padx=15, pady=5)

        grip_row = tk.Frame(grip_frame, bg="#1a1a2e")
        grip_row.pack(fill="x")

        tk.Button(grip_row, text="Open", bg="#16213e", fg="#50fa7b",
                 font=("Helvetica", 10), width=8,
                 command=self._gripper_open).pack(side="left", padx=5)
        tk.Button(grip_row, text="Close", bg="#16213e", fg="#e94560",
                 font=("Helvetica", 10), width=8,
                 command=self._gripper_close).pack(side="left", padx=5)

        self.grip_slider = tk.Scale(grip_row, from_=0, to=100,
                                   orient="horizontal",
                                   bg="#16213e", fg="#e0e0e0",
                                   troughcolor="#0f3460",
                                   highlightthickness=0,
                                   command=self._on_grip)
        self.grip_slider.pack(side="left", fill="x", expand=True, padx=5)

        # Presets
        preset_frame = ttk.LabelFrame(self.root, text="Presets", padding=10)
        preset_frame.pack(fill="x", padx=15, pady=5)

        preset_row1 = tk.Frame(preset_frame, bg="#1a1a2e")
        preset_row1.pack(fill="x", pady=2)
        preset_row2 = tk.Frame(preset_frame, bg="#1a1a2e")
        preset_row2.pack(fill="x", pady=2)

        for i, (name, angles) in enumerate(self.PRESETS.items()):
            row = preset_row1 if i < 4 else preset_row2
            tk.Button(row, text=name, bg="#0f3460", fg="#e0e0e0",
                     font=("Helvetica", 9), width=8,
                     command=lambda a=angles, n=name: self._go_preset(n, a)
                     ).pack(side="left", padx=3)

        # Actions
        action_frame = ttk.LabelFrame(self.root, text="Actions", padding=10)
        action_frame.pack(fill="x", padx=15, pady=5)

        action_row = tk.Frame(action_frame, bg="#1a1a2e")
        action_row.pack(fill="x")

        tk.Button(action_row, text="Dance", bg="#e94560", fg="white",
                 font=("Helvetica", 11, "bold"), width=8,
                 command=self._dance).pack(side="left", padx=3)
        tk.Button(action_row, text="Fist Bump", bg="#e94560", fg="white",
                 font=("Helvetica", 11, "bold"), width=8,
                 command=self._fist_bump).pack(side="left", padx=3)
        tk.Button(action_row, text="Wave Cam", bg="#50fa7b", fg="#0a0a1a",
                 font=("Helvetica", 11, "bold"), width=9,
                 command=self._wave_to_camera).pack(side="left", padx=3)
        tk.Button(action_row, text="Read", bg="#0f3460", fg="#e0e0e0",
                 font=("Helvetica", 10), width=6,
                 command=self._read_angles).pack(side="left", padx=3)

        # Angles readout
        self.readout_var = tk.StringVar(value="")
        readout = tk.Label(self.root, textvariable=self.readout_var,
                          font=("Courier", 10), bg="#1a1a2e", fg="#8888aa")
        readout.pack(pady=5)

    def _send_angles(self):
        """Send current slider values to the arm."""
        if self.sending:
            return
        angles = [self.sliders[j].get() for j in ["j1", "j2", "j3", "j4"]]
        try:
            self.mc.send_angles(angles, self.speed)
            self.status_var.set(f"Sent: {angles}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    def _on_slider(self, name, value):
        self.labels[name].config(text=f"{int(float(value))}°")
        self._send_angles()

    def _on_speed(self, value):
        self.speed = int(float(value))
        self.speed_label.config(text=str(self.speed))

    def _on_grip(self, value):
        try:
            self.mc.set_gripper_value(int(float(value)), 50)
        except Exception as e:
            self.status_var.set(f"Gripper error: {e}")

    def _gripper_open(self):
        try:
            self.mc.set_gripper_state(0, 50)
            self.grip_slider.set(0)
        except Exception as e:
            self.status_var.set(f"Gripper error: {e}")

    def _gripper_close(self):
        try:
            self.mc.set_gripper_state(1, 50)
            self.grip_slider.set(100)
        except Exception as e:
            self.status_var.set(f"Gripper error: {e}")

    def _go_preset(self, name, angles):
        for j, val in zip(["j1", "j2", "j3", "j4"], angles):
            self.sliders[j].set(val)
        self.status_var.set(f"Preset: {name}")
        self._send_angles()

    def _read_angles(self):
        try:
            a = self.mc.get_angles()
            if a != -1 and a is not None:
                self.readout_var.set(f"Read: j1={a[0]:.1f} j2={a[1]:.1f} j3={a[2]:.1f} j4={a[3]:.1f}")
                for j, val in zip(["j1", "j2", "j3", "j4"], a):
                    self.sliders[j].set(val)
            else:
                self.readout_var.set("Read: -1 (no response)")
        except Exception as e:
            self.readout_var.set(f"Read error: {e}")

    def _run_in_thread(self, func):
        """Run a choreography in a background thread."""
        self.sending = True
        self.status_var.set("Running...")

        def wrapper():
            try:
                func()
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))
            finally:
                self.sending = False
                self.root.after(0, lambda: self.status_var.set("Ready"))
                self.root.after(0, self._read_angles)

        threading.Thread(target=wrapper, daemon=True).start()

    def _dance(self):
        def routine():
            mc = self.mc
            mc.send_angles([0, 0, 0, 0], 25)
            time.sleep(1.5)

            # Bounce
            for _ in range(3):
                mc.send_angles([0, 20, 10, 0], 50)
                time.sleep(0.4)
                mc.send_angles([0, 5, 0, 0], 50)
                time.sleep(0.4)

            # Sway
            for _ in range(2):
                mc.send_angles([-30, 15, 5, 0], 50)
                time.sleep(0.5)
                mc.send_angles([30, 15, 5, 0], 50)
                time.sleep(0.5)

            # Wrist wiggle
            for _ in range(3):
                mc.send_angles([0, 25, 10, 30], 60)
                time.sleep(0.3)
                mc.send_angles([0, 25, 10, -30], 60)
                time.sleep(0.3)

            # Bow
            mc.send_angles([0, 50, -40, 0], 25)
            time.sleep(1.5)

            mc.send_angles([0, 0, 0, 0], 20)
            time.sleep(1.5)

        self._run_in_thread(routine)

    def _fist_bump(self):
        def routine():
            mc = self.mc

            mc.set_gripper_state(1, 80)
            time.sleep(0.5)

            mc.send_angles([0, 0, 0, 0], 25)
            time.sleep(1.5)

            # Notice
            mc.send_angles([0, 20, 5, 0], 20)
            time.sleep(1)

            # Curious tilt
            mc.send_angles([0, 30, -10, 12], 25)
            time.sleep(0.8)

            # Reach
            mc.send_angles([0, 55, -35, 0], 40)
            time.sleep(1.2)

            # Hold
            time.sleep(2)

            # Recoil
            mc.send_angles([0, 50, -30, 5], 60)
            time.sleep(0.2)
            mc.send_angles([0, 55, -35, 0], 50)
            time.sleep(0.4)

            # Retract
            mc.send_angles([0, 25, -5, 0], 15)
            time.sleep(1.5)

            mc.send_angles([0, 5, 0, 0], 15)
            time.sleep(1)

            mc.send_angles([0, 0, 0, 0], 15)
            time.sleep(1)

            mc.set_gripper_state(0, 50)

        self._run_in_thread(routine)

    def _wave_to_camera(self):
        def routine():
            mc = self.mc
            # Home / default neutral pose
            neutral = [-9.0, 45.0, -57.0, 43.0]

            # Step 0: Ensure gripper is closed and at neutral
            try:
                mc.set_gripper_state(1, 80)
            except Exception:
                pass

            mc.send_angles(neutral, 35)
            time.sleep(1.2)

            # Step 1: Move J2 to -2 and J3 to -92
            mc.send_angles([neutral[0], -2.0, -92.0, neutral[3]], 40)
            time.sleep(1.2)

            # Step 2: Move J1 to 162
            mc.send_angles([162.0, -2.0, -92.0, neutral[3]], 40)
            time.sleep(1.4)

            # Step 3: Move J2 up and down 15-20 degrees (wave)
            for _ in range(4):
                mc.send_angles([162.0, 16.0, -92.0, neutral[3]], 55)
                time.sleep(0.35)
                mc.send_angles([162.0, -2.0, -92.0, neutral[3]], 55)
                time.sleep(0.35)

            # Step 4: Return to neutral
            mc.send_angles([neutral[0], -2.0, -92.0, neutral[3]], 40)
            time.sleep(1.2)

            mc.send_angles(neutral, 35)
            time.sleep(1.2)

            try:
                mc.set_gripper_state(1, 80)
            except Exception:
                pass

        self._run_in_thread(routine)

        self._run_in_thread(routine)

    def run(self):
        self.root.mainloop()
        self.mc.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ALICE Arm Test UI")
    parser.add_argument("--wifi", type=str, help="WiFi IP address")
    parser.add_argument("--wifi-port", type=int, default=9000, help="WiFi port")
    parser.add_argument("--port", type=str, help="Serial port path")
    args = parser.parse_args()

    mc = connect(args)
    ui = ArmTestUI(mc)
    ui.run()
