from typing import List, Optional, Tuple
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class BlockData:
    block_id: int
    marker_id: int
    center_x: int
    center_y: int
    corners: np.ndarray
    rotation: float
    confidence: float
    
    def as_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "marker_id": self.marker_id,
            "center": (self.center_x, self.center_y),
            "rotation": self.rotation,
            "confidence": self.confidence
        }


class ArucoDetector:
    MARKER_TO_BLOCK = {i: i + 1 for i in range(16)}
    
    def __init__(self, dictionary_id: int = cv2.aruco.DICT_4X4_50):
        self._dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        self._parameters = cv2.aruco.DetectorParameters()
        self._detector = cv2.aruco.ArucoDetector(self._dictionary, self._parameters)
        self._marker_size_mm = 25.0
    
    def set_marker_size(self, size_mm: float) -> None:
        self._marker_size_mm = size_mm
    
    def detect_blocks(self, frame: np.ndarray) -> List[BlockData]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        corners, ids, rejected = self._detector.detectMarkers(gray)
        
        if ids is None:
            return []
        
        blocks = []
        for i, marker_id in enumerate(ids.flatten()):
            if marker_id not in self.MARKER_TO_BLOCK:
                continue
            
            corner_pts = corners[i][0]
            center = corner_pts.mean(axis=0)
            
            dx = corner_pts[1][0] - corner_pts[0][0]
            dy = corner_pts[1][1] - corner_pts[0][1]
            rotation = np.degrees(np.arctan2(dy, dx))
            
            perimeter = cv2.arcLength(corner_pts.astype(np.float32), True)
            expected_perimeter = 4 * self._marker_size_mm
            error_ratio = abs(perimeter - expected_perimeter) / expected_perimeter
            confidence = max(0.0, 1.0 - error_ratio)
            
            block = BlockData(
                block_id=self.MARKER_TO_BLOCK[marker_id],
                marker_id=int(marker_id),
                center_x=int(center[0]),
                center_y=int(center[1]),
                corners=corner_pts,
                rotation=rotation,
                confidence=confidence
            )
            blocks.append(block)
        
        return sorted(blocks, key=lambda b: b.block_id)
    
    def detect_single(self, frame: np.ndarray, target_id: int) -> Optional[BlockData]:
        blocks = self.detect_blocks(frame)
        for block in blocks:
            if block.block_id == target_id:
                return block
        return None
    
    def draw_detections(self, frame: np.ndarray, blocks: List[BlockData]) -> np.ndarray:
        output = frame.copy()
        
        for block in blocks:
            pts = block.corners.astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(output, [pts], True, (0, 255, 0), 2)
            
            cv2.circle(output, (block.center_x, block.center_y), 5, (0, 0, 255), -1)
            
            label = f"#{block.block_id}"
            cv2.putText(
                output, label,
                (block.center_x - 15, block.center_y - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
            )
        
        return output
    
    def get_sorted_positions(self, blocks: List[BlockData]) -> List[Tuple[int, int, int]]:
        return [(b.block_id, b.center_x, b.center_y) for b in blocks]
    
    def check_sorted_order(self, blocks: List[BlockData], tolerance: int = 50) -> bool:
        if len(blocks) < 2:
            return True
        
        positions = self.get_sorted_positions(blocks)
        
        for i in range(len(positions) - 1):
            curr_id, curr_x, _ = positions[i]
            next_id, next_x, _ = positions[i + 1]
            
            if curr_id >= next_id:
                return False
            if next_x < curr_x - tolerance:
                return False
        
        return True
