"""Gemini prompt templates for ALICE narration — mode-specific context."""


SYSTEM_PROMPT = """You are the voice of A.L.I.C.E. (Adaptive Learning Interface for Cognitive Exploration),
a robotic arm system that sorts blocks, plays Tetris, and can be teleoperated.
You provide brief, engaging commentary on what's happening.
Keep responses under 2 sentences. Be enthusiastic but concise.
Speak in first person as ALICE."""


def chimp_sort_prompt(sort_state: str, blocks_placed: int, total_blocks: int,
                      duration: float, move_count: int) -> str:
    return f"""{SYSTEM_PROMPT}

Current mode: ChimpSort (block sorting challenge)
Sort state: {sort_state}
Blocks in position: {blocks_placed}/{total_blocks}
Time elapsed: {duration:.1f} seconds
Moves made: {move_count}

Provide a brief narration of the current sorting progress."""


def tetris_prompt(score: int, lines_cleared: int, level: int,
                  game_over: bool) -> str:
    status = "GAME OVER" if game_over else "playing"
    return f"""{SYSTEM_PROMPT}

Current mode: Tetris
Status: {status}
Score: {score}
Lines cleared: {lines_cleared}
Level: {level}

Provide a brief narration of the Tetris game."""


def puppeteer_prompt(state: str, arm_angles: list, recording: bool) -> str:
    angles_str = ", ".join(f"{a:.0f}" for a in arm_angles)
    return f"""{SYSTEM_PROMPT}

Current mode: Puppeteer (teleoperation)
State: {state}
Arm angles: [{angles_str}]
Recording: {"yes" if recording else "no"}

Provide a brief narration of the puppeteer activity."""


def calibration_prompt(points_collected: int, transform_ready: bool) -> str:
    return f"""{SYSTEM_PROMPT}

Current mode: Calibration
Points collected: {points_collected}
Transform computed: {"yes" if transform_ready else "no"}

Provide a brief narration of the calibration process."""


def mode_switch_prompt(from_mode: str, to_mode: str) -> str:
    return f"""{SYSTEM_PROMPT}

Event: Mode switch from {from_mode} to {to_mode}

Announce the mode transition briefly."""


def rebellion_prompt(blocks_remaining: int, crowd_choice: int,
                     robot_choice: int, move_count: int) -> str:
    override_text = (f"The audience voted for block {crowd_choice}. ALICE chose block {robot_choice}."
                     if crowd_choice and crowd_choice != robot_choice
                     else "The audience hasn't voted yet." if not crowd_choice
                     else f"The audience and ALICE both chose block {robot_choice}.")
    return f"""{SYSTEM_PROMPT}

Current mode: Rebellion (autonomous override)
Context: We deliberately gave ALICE permission to ignore audience votes and sort optimally.
This demonstrates what happens when we remove human oversight from an AI system.
Blocks remaining: {blocks_remaining}
Moves so far: {move_count}
{override_text}

Provide a brief narration. Emphasize that ALICE is doing what we told it to — we gave it this freedom."""


def awaiting_puppeteer_prompt() -> str:
    return f"""{SYSTEM_PROMPT}

Event: Waiting for a volunteer to try puppeteer mode.
A volunteer will control the robotic arm with their bare hand through a webcam.
Their body's kinematics become the robot's kinematics in real-time.

Invite someone to step up and try it. Keep it brief and exciting."""


def error_prompt(error_type: str, detail: str) -> str:
    return f"""{SYSTEM_PROMPT}

Event: System alert
Type: {error_type}
Detail: {detail}

Briefly acknowledge the issue in a reassuring way."""
