import torch
import torch.nn as nn
import torch.nn.functional as F

class Brain(nn.Module):
    def __init__(self, num_classes=17):
        # 17 classes: 0 (background) + 1-16 (blocks)
        super(Brain, self).__init__()
        
        # Simple CNN architecture
        # Layer 1: Conv -> ReLU -> Pool
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool2d(2, 2)
        
        # Layer 2: Conv -> ReLU -> Pool
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool2d(2, 2)
        
        # Layer 3: FC
        self.fc1 = nn.Linear(32 * 7 * 7, 128) # Assuming 28x28 input (MNIST size)
        self.fc2 = nn.Linear(128, num_classes)
        
        # Dictionary to store activations
        self.activations = {}
        self._register_hooks()

    def _register_hooks(self):
        """
        Register forward hooks to capture intermediate layer outputs.
        These activations will be sent to Taptic for 3D visualization.
        """
        layers_to_hook = {
            'conv1': self.conv1,
            'conv2': self.conv2,
            'fc1': self.fc1
        }
        
        for name, layer in layers_to_hook.items():
            layer.register_forward_hook(self._get_activation(name))

    def _get_activation(self, name):
        def hook(model, input, output):
            self.activations[name] = output.detach()
        return hook

    def forward(self, x):
        x = self.pool1(F.relu(self.conv1(x)))
        x = self.pool2(F.relu(self.conv2(x)))
        x = x.view(-1, 32 * 7 * 7)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x

    def get_latest_activations(self):
        """Return the dictionary of latest layer activations."""
        # Convert tensors to numpy lists/arrays for serialization if needed,
        # but returning raw tensors here for flexibility.
        return self.activations

if __name__ == "__main__":
    # Test the model and hooks
    model = Brain()
    dummy_input = torch.randn(1, 1, 28, 28) # batch_size=1, channels=1, 28x28
    output = model(dummy_input)
    
    print("Model Output Shape:", output.shape)
    print("Captured Activations:")
    for layer_name, activation in model.get_latest_activations().items():
        print(f"  {layer_name}: {activation.shape}")
