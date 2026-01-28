import asyncio
import argparse
import logging
from enum import Enum
from typing import Optional

from hardware import ArmController, MagnetDriver, CalibrationManager
from vision import CameraManager, CameraConfig, CameraRole, ArucoDetector
from brain import InferencePipeline
from logic import ChimpSortFSM, SortState, TetrisAgent


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ALICE")


class Mode(Enum):
    CHIMP_SORT = "chimp"
    TETRIS = "tetris"
    CALIBRATE = "calibrate"


class ALICE:
    def __init__(self, mode: Mode, simulate: bool = True):
        self.mode = mode
        self.simulate = simulate
        
        self.arm: Optional[ArmController] = None
        self.magnet: Optional[MagnetDriver] = None
        self.calibration: Optional[CalibrationManager] = None
        self.cameras: Optional[CameraManager] = None
        self.detector: Optional[ArucoDetector] = None
        self.inference: Optional[InferencePipeline] = None
        self.sort_fsm: Optional[ChimpSortFSM] = None
        self.tetris: Optional[TetrisAgent] = None
        
        self._running = False
        self._ws_server = None
        self._clients = set()
    
    async def initialize(self) -> bool:
        logger.info(f"Initializing A.L.I.C.E. in {self.mode.value} mode (simulate={self.simulate})")
        
        try:
            self.arm = ArmController(simulate=self.simulate)
            self.magnet = MagnetDriver(simulate=self.simulate)
            self.calibration = CalibrationManager()
            
            if not self.arm.connect():
                logger.warning("Arm connection failed, running in simulation")
            
            self.calibration.load()
            
            self.cameras = CameraManager()
            overhead = CameraConfig(device_id=0, width=1920, height=1080, fps=60, role=CameraRole.OVERHEAD)
            front = CameraConfig(device_id=1, width=1280, height=720, fps=30, role=CameraRole.FRONT_FACING)
            
            self.cameras.add_camera(overhead)
            self.cameras.add_camera(front)
            
            self.detector = ArucoDetector()
            self.inference = InferencePipeline()
            
            if self.mode == Mode.CHIMP_SORT:
                self.sort_fsm = ChimpSortFSM()
                self.sort_fsm.on_state_change(self._on_sort_state_change)
                self.sort_fsm.on_move(self._on_block_move)
            
            elif self.mode == Mode.TETRIS:
                self.tetris = TetrisAgent()
                self.tetris.on_action(self._on_tetris_action)
            
            logger.info("Initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    def _on_sort_state_change(self, state: SortState) -> None:
        logger.info(f"Sort state: {state.value}")
    
    def _on_block_move(self, move) -> None:
        logger.debug(f"Block {move.block_id}: {move.from_pos} -> {move.to_pos}")
    
    def _on_tetris_action(self, action) -> None:
        logger.debug(f"Tetris action: {action.name}")
    
    async def run(self) -> None:
        self._running = True
        logger.info("Starting main loop")
        
        self.cameras.start_all()
        
        if self.mode == Mode.CHIMP_SORT:
            await self._run_chimp_sort()
        elif self.mode == Mode.TETRIS:
            await self._run_tetris()
        elif self.mode == Mode.CALIBRATE:
            await self._run_calibration()
    
    async def _run_chimp_sort(self) -> None:
        self.sort_fsm.start_human_benchmark()
        
        while self._running:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is None:
                await asyncio.sleep(0.01)
                continue
            
            blocks = self.detector.detect_blocks(frame)
            self.sort_fsm.update(blocks)
            
            if self.sort_fsm.state == SortState.COMPLETE:
                logger.info(f"Sorting complete! Duration: {self.sort_fsm.session.duration:.2f}s")
                break
            
            if self.sort_fsm.state == SortState.CYBORG_COOP:
                target = self.sort_fsm.get_next_robot_target()
                if target:
                    block_id, (tx, ty) = target
                    angles = self.calibration.pixel_to_arm(tx, ty)
                    self.arm.move_to(angles)
                    self.magnet.on()
                    await asyncio.sleep(0.3)
                    self.magnet.off()
            
            await asyncio.sleep(0.016)
    
    async def _run_tetris(self) -> None:
        self.tetris.reset()
        
        while self._running and self.tetris.state and not self.tetris.state.game_over:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is not None and not self.inference.is_frozen:
                _, _, activations = self.inference.predict(frame)
                await self._broadcast_activations()
            
            action = self.tetris.step()
            
            await asyncio.sleep(0.1)
        
        logger.info(f"Game over! Score: {self.tetris.state.score if self.tetris.state else 0}")
    
    async def _run_calibration(self) -> None:
        logger.info("Calibration mode - press 'q' to quit")
        
        import cv2
        
        while self._running:
            frame = self.cameras.get_frame(CameraRole.OVERHEAD)
            if frame is None:
                await asyncio.sleep(0.01)
                continue
            
            blocks = self.detector.detect_blocks(frame)
            display = self.detector.draw_detections(frame, blocks)
            
            cv2.imshow("Calibration", display)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('c') and blocks:
                block = blocks[0]
                angles = self.arm.position.as_tuple()
                self.calibration.add_calibration_point(block.center_x, block.center_y, angles)
                logger.info(f"Added calibration point: ({block.center_x}, {block.center_y})")
            elif key == ord('s'):
                self.calibration.save()
                logger.info("Calibration saved")
        
        cv2.destroyAllWindows()
    
    async def _broadcast_activations(self) -> None:
        if not self._clients:
            return
        
        data = self.inference.get_websocket_payload()
        for client in self._clients.copy():
            try:
                await client.send(data)
            except Exception:
                self._clients.discard(client)
    
    async def shutdown(self) -> None:
        logger.info("Shutting down")
        self._running = False
        
        if self.cameras:
            self.cameras.close_all()
        
        if self.magnet:
            self.magnet.off()
        
        if self.arm:
            self.arm.home()
            self.arm.disconnect()


async def main():
    parser = argparse.ArgumentParser(description="A.L.I.C.E. - Adaptive Learning Interface for Cognitive Exploration")
    parser.add_argument("--mode", type=str, choices=["chimp", "tetris", "calibrate"], default="tetris")
    parser.add_argument("--simulate", action="store_true", default=True)
    parser.add_argument("--ws-port", type=int, default=8765)
    args = parser.parse_args()
    
    mode = Mode(args.mode)
    alice = ALICE(mode, simulate=args.simulate)
    
    if not await alice.initialize():
        return
    
    try:
        await alice.run()
    except KeyboardInterrupt:
        pass
    finally:
        await alice.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
