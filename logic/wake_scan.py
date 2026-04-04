"""Wake-up scan — ALICE looks around the desk to see what's there.

A slow, deliberate sweep of the workspace using the arm-mounted camera.
For each position in the sweep, ALICE captures a frame, runs YOLO detection,
estimates depth, and integrates into the 3D spatial map.

This is Act 2's personality beat: "She Knows This Desk." ALICE wakes up
and perceives her environment.

The scan also populates object memory with what's on the desk, so ALICE
can notice what changed since last session.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("WakeScan")


@dataclass
class ScanWaypoint:
    """A position ALICE moves to during the wake-up scan."""
    angles: Tuple[float, ...]   # joint angles (degrees)
    dwell_time: float = 0.5     # seconds to hold and observe
    label: str = ""             # human-readable description


# Default scan path: sweep left → center → right, with a slight tilt variation
DEFAULT_SCAN_WAYPOINTS = [
    ScanWaypoint((130, 80, 80, 90), dwell_time=0.8, label="far left"),
    ScanWaypoint((115, 75, 85, 90), dwell_time=0.5, label="left"),
    ScanWaypoint((90, 70, 90, 90), dwell_time=0.8, label="center"),
    ScanWaypoint((65, 75, 85, 90), dwell_time=0.5, label="right"),
    ScanWaypoint((50, 80, 80, 90), dwell_time=0.8, label="far right"),
    # Return to center, slightly higher for overview
    ScanWaypoint((90, 85, 75, 90), dwell_time=1.0, label="overview"),
]


@dataclass
class ScanResult:
    """Results from a wake-up scan."""
    objects_found: List[dict]       # detection dicts from YOLO
    objects_moved: List[str]        # object IDs that moved since last session
    objects_new: List[str]          # object IDs seen for the first time
    frames_captured: int = 0
    duration_s: float = 0.0
    waypoints_completed: int = 0


class WakeScanRoutine:
    """Executes a wake-up desk scan.

    Coordinates arm movement, camera capture, YOLO detection, depth
    estimation, and spatial map integration.

    All subsystems are injected — this routine doesn't own any hardware.
    """

    def __init__(
        self,
        waypoints: Optional[List[ScanWaypoint]] = None,
        scan_speed: float = 30.0,
    ):
        self._waypoints = waypoints or list(DEFAULT_SCAN_WAYPOINTS)
        self._scan_speed = scan_speed

    async def execute(
        self,
        arm,
        camera_getter: Callable,
        yolo_detector=None,
        depth_estimator=None,
        spatial_map=None,
        object_memory=None,
        fk=None,
        state_manager=None,
        running_check: Optional[Callable[[], bool]] = None,
    ) -> ScanResult:
        """Run the full wake-up scan sequence.

        Args:
            arm: ArmController or MovementDynamics for positioning.
            camera_getter: Callable returning BGR frame (or None).
            yolo_detector: YoloDetector for object detection.
            depth_estimator: MonocularDepthEstimator for depth maps.
            spatial_map: SpatialMap for 3D integration.
            object_memory: ObjectMemory for cross-session comparison.
            fk: ForwardKinematics for camera pose computation.
            state_manager: AliceStateManager for broadcasting progress.
            running_check: Callable returning False to abort early.

        Returns:
            ScanResult with all findings.
        """
        start_time = time.time()
        all_detections = []
        objects_moved = []
        objects_new = []
        frames = 0
        waypoints_done = 0

        logger.info(f"Wake-up scan starting ({len(self._waypoints)} waypoints)")

        for wp in self._waypoints:
            if running_check and not running_check():
                break

            # Move to waypoint
            if hasattr(arm, 'move_to'):
                arm.move_to(wp.angles, speed=self._scan_speed)
            await asyncio.sleep(0.3)  # settle time

            # Dwell and observe
            dwell_end = time.time() + wp.dwell_time
            while time.time() < dwell_end:
                if running_check and not running_check():
                    break

                frame = camera_getter()
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue

                frames += 1

                # YOLO detection
                detections = []
                if yolo_detector is not None:
                    detections = yolo_detector.detect(frame)
                    all_detections.extend(detections)

                # Depth estimation + spatial map integration
                if depth_estimator is not None and spatial_map is not None and fk is not None:
                    depth_result = depth_estimator.estimate(frame)
                    camera_pose = fk.camera_pose(wp.angles)
                    spatial_map.integrate_frame(
                        frame, depth_result.depth_map, camera_pose,
                    )

                    # Place detected objects in 3D
                    for det in detections:
                        depth_at = depth_result.median_depth_in_bbox(*det.bbox)
                        if depth_at > 0:
                            spatial_map.place_object_in_3d(
                                label=det.label,
                                pixel_x=det.center_x,
                                pixel_y=det.center_y,
                                depth_m=depth_at,
                                camera_pose=camera_pose,
                                confidence=det.confidence,
                            )

                # Object memory: observe and check for changes
                if object_memory is not None:
                    for det in detections:
                        obj_id = f"{det.label}_{det.center_x}_{det.center_y}"
                        # Use a simpler stable ID based on label + rough position
                        stable_id = f"{det.label}_0"
                        existing = object_memory.get_object(stable_id)
                        if existing is None:
                            objects_new.append(stable_id)
                        elif existing.has_moved:
                            objects_moved.append(stable_id)

                        # Convert pixel position to rough cm (placeholder)
                        pos_cm = (
                            float(det.center_x) * 0.05,
                            float(det.center_y) * 0.05,
                            0.0,
                        )
                        object_memory.observe(stable_id, det.label, pos_cm)

                await asyncio.sleep(0.05)

            waypoints_done += 1

            # Broadcast progress
            if state_manager is not None:
                progress = waypoints_done / len(self._waypoints)
                logger.debug(f"Scan progress: {progress:.0%} ({wp.label})")

        duration = time.time() - start_time

        # Deduplicate detections by label
        seen_labels = set()
        unique_dets = []
        for det in all_detections:
            if hasattr(det, 'as_dict'):
                d = det.as_dict()
            else:
                d = {"label": str(det), "confidence": 0.0}
            key = d.get("label", "")
            if key not in seen_labels:
                seen_labels.add(key)
                unique_dets.append(d)

        result = ScanResult(
            objects_found=unique_dets,
            objects_moved=list(set(objects_moved)),
            objects_new=list(set(objects_new)),
            frames_captured=frames,
            duration_s=duration,
            waypoints_completed=waypoints_done,
        )

        logger.info(
            f"Wake-up scan complete: {len(unique_dets)} objects, "
            f"{frames} frames, {duration:.1f}s"
        )

        # Save memory
        if object_memory is not None and object_memory.needs_save:
            object_memory.save()

        return result
