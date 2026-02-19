// Arm link dimensions (mm) — matching hardware/calibration.py ArmDimensions
export const ARM_DIMS = {
  baseHeight: 50,
  shoulderLength: 100,
  elbowLength: 100,
  wristLength: 80,
};

// Scale factor: mm to Three.js units
export const SCALE = 0.03;

// Default servo angles (degrees, centered at 90)
export const DEFAULT_ANGLES = [90, 90, 90, 90, 90];

// Visual sizes (Three.js units)
export const LINK_RADIUS = 0.08;
export const JOINT_RADIUS = 0.15;
export const BASE_RADIUS = 0.5;
export const BASE_PLATFORM_HEIGHT = 0.15;
export const GRIPPER_LENGTH = 0.5;
export const GRIPPER_WIDTH = 0.04;
export const GRIPPER_SPREAD_OPEN = 0.15;
export const GRIPPER_SPREAD_CLOSED = 0.035;

// Colors (hex for Three.js)
export const COLORS = {
  base: 0x3f3f46,
  baseTop: 0x52525b,
  upperArm: 0x3b82f6,
  forearm: 0x6366f1,
  hand: 0x8b5cf6,
  joint: 0xe4e4e7,
  jointEmissive: 0x3b82f6,
  gripperOpen: 0x22c55e,
  gripperClosed: 0xeab308,
  ground: 0x111113,
  grid: 0x27272a,
  reachCircle: 0x3b82f6,
};
