import { ARM_DIMS, SCALE } from './armConstants';

const DEG2RAD = Math.PI / 180;

/**
 * Compute 3D joint positions from 5 servo angles.
 *
 * Angles are in degrees, centered at 90 (servo convention):
 *   [0] base rotation:   90 = forward
 *   [1] shoulder:        90 = horizontal
 *   [2] elbow:           90 = 90-degree bend (180 = straight)
 *   [3] wrist pitch:     90 = continues forearm direction
 *   [4] wrist roll:      90 = no roll
 *
 * Returns positions in Three.js coordinates (Y up).
 */
export function computeJointPositions(angles) {
  const a = angles && angles.length >= 5 ? angles : [90, 90, 90, 90, 90];

  const baseRot = (a[0] - 90) * DEG2RAD;
  const shoulderElev = (a[1] - 90) * DEG2RAD;
  const elbowActual = (180 - a[2]) * DEG2RAD;
  const wristPitchOffset = (a[3] - 90) * DEG2RAD;
  const wristRoll = (a[4] - 90) * DEG2RAD;

  // Link angles from horizontal in the arm's plane
  const link1Angle = shoulderElev;
  const link2Angle = link1Angle - (Math.PI - elbowActual);
  const link3Angle = link2Angle + wristPitchOffset;

  const { baseHeight, shoulderLength, elbowLength, wristLength } = ARM_DIMS;
  const s = SCALE;

  // Positions in (r, h) plane: r = horizontal reach, h = height
  const shoulderH = baseHeight * s;

  const elbowR = shoulderLength * s * Math.cos(link1Angle);
  const elbowH = shoulderH + shoulderLength * s * Math.sin(link1Angle);

  const wristR = elbowR + elbowLength * s * Math.cos(link2Angle);
  const wristH = elbowH + elbowLength * s * Math.sin(link2Angle);

  const eeR = wristR + wristLength * s * Math.cos(link3Angle);
  const eeH = wristH + wristLength * s * Math.sin(link3Angle);

  // Convert to 3D: base rotation maps r into XZ plane, h maps to Y
  const toXYZ = (r, h) => ({
    x: r * Math.cos(baseRot),
    y: h,
    z: r * Math.sin(baseRot),
  });

  return {
    base: { x: 0, y: 0, z: 0 },
    shoulder: { x: 0, y: shoulderH, z: 0 },
    elbow: toXYZ(elbowR, elbowH),
    wrist: toXYZ(wristR, wristH),
    endEffector: toXYZ(eeR, eeH),
    baseRotation: baseRot,
    wristRoll,
    endEffectorDirection: link3Angle,
  };
}

/**
 * Top-down (bird's-eye) projection for the camera overlay.
 * Returns { x, y } positions in the XZ plane (arm units).
 */
export function computeTopDownPositions(angles) {
  const pos = computeJointPositions(angles);
  return {
    base: { x: pos.base.x, y: pos.base.z },
    shoulder: { x: pos.shoulder.x, y: pos.shoulder.z },
    elbow: { x: pos.elbow.x, y: pos.elbow.z },
    wrist: { x: pos.wrist.x, y: pos.wrist.z },
    endEffector: { x: pos.endEffector.x, y: pos.endEffector.z },
  };
}
