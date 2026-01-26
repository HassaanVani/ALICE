import time

class ChimpSorter:
    def __init__(self, arm_controller):
        self.arm = arm_controller

    def bubble_sort(self, blocks):
        """
        Sorts blocks physically using Bubble Sort logic.
        blocks: List of objects with {'id': int, 'pos': (x,y)}
        """
        n = len(blocks)
        for i in range(n):
            for j in range(0, n - i - 1):
                if blocks[j]['id'] > blocks[j + 1]['id']:
                    # Virtual Swap
                    blocks[j], blocks[j + 1] = blocks[j + 1], blocks[j]
                    
                    # Physical Swap Operation
                    self._physical_swap(blocks[j], blocks[j+1])
                    
    def _physical_swap(self, block_a, block_b):
        """
        Execute the Pick-Place sequence to swap two blocks.
        This is a complex operation involving a temp buffer zone.
        """
        print(f"Swapping Block {block_a['id']} <-> Block {block_b['id']}")
        
        # 1. Pick A -> Move to Temp
        self.arm.move_to(block_a['pos'][0], block_a['pos'][1], 10)
        self.arm.toggle_magnet(True)
        self.arm.move_to(0, 0, 10) # Dummy Temp Zone
        self.arm.toggle_magnet(False)
        
        # 2. Pick B -> Move to A's old pos
        self.arm.move_to(block_b['pos'][0], block_b['pos'][1], 10)
        self.arm.toggle_magnet(True)
        self.arm.move_to(block_a['pos'][0], block_a['pos'][1], 10)
        self.arm.toggle_magnet(False)
        
        # 3. Pick A (from Temp) -> Move to B's old pos
        self.arm.move_to(0, 0, 10) # From Temp
        self.arm.toggle_magnet(True)
        self.arm.move_to(block_b['pos'][0], block_b['pos'][1], 10)
        self.arm.toggle_magnet(False)

if __name__ == "__main__":
    # Test Stub
    class MockArm:
        def move_to(self, x, y, z): pass
        def toggle_magnet(self, s): pass
    
    sorter = ChimpSorter(MockArm())
    
    test_blocks = [
        {'id': 2, 'pos': (10, 10)},
        {'id': 1, 'pos': (20, 10)}
    ]
    
    print("Before:", [b['id'] for b in test_blocks])
    sorter.bubble_sort(test_blocks)
    print("After:", [b['id'] for b in test_blocks])
