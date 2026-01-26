import torch
import time
from .model import Brain

class InferenceEngine:
    def __init__(self):
        self.model = Brain()
        self.model.eval() # Set to evaluation mode
        self.running = False

    def process_frame(self, frame_tensor):
        """
        Run inference on a single frame (tensor).
        Returns predicted class and latest activations.
        """
        with torch.no_grad():
            output = self.model(frame_tensor)
            prediction = torch.argmax(output, dim=1).item()
            activations = self.model.get_latest_activations()
        
        return prediction, activations

    def loop(self):
        """
        Main inference loop (placeholder).
        In a real app, this would grab frames from Vision pipeline.
        """
        self.running = True
        print("Inference Engine Started...")
        
        while self.running:
            # Dummy frame
            dummy_frame = torch.randn(1, 1, 28, 28)
            pred, acts = self.process_frame(dummy_frame)
            
            # Here we would send 'acts' to Taptic via WebSocket
            # print(f"Pred: {pred}")
            
            time.sleep(0.1) # Simulate 10 FPS

    def stop(self):
        self.running = False

if __name__ == "__main__":
    engine = InferenceEngine()
    # engine.loop() # Uncomment to run loop
    print("Inference Engine Initialized.")
