import asyncio
import websockets
import json
import torch
import numpy as np
from brain.inference import InferenceEngine

# Initialize core systems
engine = InferenceEngine()

async def handler(websocket):
    print("Client connected (Taptic)")
    try:
        async for message in websocket:
            data = json.loads(message)
            
            # Handle incoming gestures/commands from Taptic
            if 'gesture' in data:
                print(f"Received gesture: {data['gesture']}")
                # Future: Map gestures to actions (e.g., Pause Brain, Rotate)

            # --- EMIT LOOP ---
            # In a real app, this might be triggered by a camera frame event
            # For now, we simulate a frame processing step and send back data
            
            # 1. Run inference (using dummy data for now)
            dummy_frame = torch.randn(1, 1, 28, 28)
            pred, raw_activations = engine.process_frame(dummy_frame)
            
            # 2. Serialize activations for the frontend
            serialized_activations = {}
            for name, tensor in raw_activations.items():
                # Convert to list for JSON
                serialized_activations[name] = tensor.cpu().numpy().tolist()
            
            response = {
                "type": "brain_state",
                "prediction": pred,
                "activations": serialized_activations
            }
            
            await websocket.send(json.dumps(response))
            
            # Sleep briefly to not flood the client
            await asyncio.sleep(0.1) 

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

async def main():
    print("Starting A.L.I.C.E. WebSocket Server on ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.ensure_future(asyncio.Future()) # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping Server")
