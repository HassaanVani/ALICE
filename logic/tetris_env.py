class TetrisEnv:
    def __init__(self):
        self.state = "idle"
        self.score = 0

    def start_game(self):
        self.state = "playing"
        print("Tetris Game Started")

    def get_state(self):
        """
        Returns the current game grid and piece.
        Used for the AI to make decisions.
        """
        # Placeholder 10x20 grid
        return [[0]*10 for _ in range(20)]

    def action(self, action_id):
        """
        0: Left, 1: Right, 2: Rotate, 3: Drop
        """
        print(f"Tetris Action: {action_id}")

if __name__ == "__main__":
    game = TetrisEnv()
    game.start_game()
    game.action(2)
