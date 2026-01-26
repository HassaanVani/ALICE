import serial
import time
import math

class ArmController:
    def __init__(self, port='COM3', baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.connection = None
        self.magnet_state = False
        
        try:
            self.connection = serial.Serial(self.port, self.baud_rate, timeout=1)
            time.sleep(2) # Wait for connection to settle
            print(f"Connected to robotic arm on {self.port}")
        except serial.SerialException as e:
            print(f"Failed to connect to arm on {self.port}: {e}")
            print("Running in simulation mode.")

    def send_command(self, command):
        """Send a G-code style or custom string command to the arm."""
        if self.connection and self.connection.is_open:
            self.connection.write(f"{command}\n".encode())
            print(f"Sent: {command}")
        else:
            print(f"[SIM] Arm Command: {command}")

    def move_to(self, x, y, z, pitch=0, roll=0):
        """
        Move end effector to coordinates (x, y, z).
        This would typically involve Inverse Kinematics (IK).
        For now, we'll send a placeholder command.
        """
        # Placeholder for IK calculation
        cmd = f"MOVE X{x} Y{y} Z{z} P{pitch} R{roll}"
        self.send_command(cmd)

    def toggle_magnet(self, state):
        """
        Control the electromagnet.
        True = ON (Pick), False = OFF (Drop)
        """
        self.magnet_state = state
        cmd = "MAGNET_ON" if state else "MAGNET_OFF"
        self.send_command(cmd)
        print(f"Magnet is now {'ON' if state else 'OFF'}")

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()

if __name__ == "__main__":
    # Test stub
    arm = ArmController()
    arm.toggle_magnet(True)
    time.sleep(1)
    arm.move_to(100, 50, 20)
    time.sleep(1)
    arm.toggle_magnet(False)
    arm.close()
