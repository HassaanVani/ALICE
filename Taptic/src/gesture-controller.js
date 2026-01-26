export class GestureController {
    constructor() {
        this.prevLandmarks = null;
        this.prevHandCenter = { x: 0, y: 0 };
        this.isRotating = false;
        this.rotationAnchor = null;

        this.wasIndexPinch = false;
        this.pinchStartTime = 0;
        this.pinchStartCenter = null;
        this.didPan = false;
        this.didZoomOut = false;
        this.lastZoomTime = 0;

        this.interactiveMode = false;
        this.cursorPosition = { x: 0, y: 0 };
        this.isCursorVisible = false;
        this.isClicking = false;

        this.callbacks = {
            onZoom: null,
            onRotate: null,
            onPan: null,
            onRecenter: null,
            onGestureChange: null,
            onCursor: null
        };

        this.PINCH_CLOSE = 0.06;
        this.CURSOR_THRESHOLD = 0.10;
        this.FULL_PINCH = 0.075;
        this.RELOAD_DIST = 0.12;
        this.HOLD_TIME = 180;
        this.ZOOM_COOLDOWN = 150;
        this.PAN_THRESHOLD = 0.02;

        this.zoomSensitivity = 1.0;
        this.rotationSensitivity = 1.0;
        this.panSensitivity = 1.0;

        this.recenterFrames = 0;
        this.RECENTER_FRAMES = 30;
    }

    setInteractiveMode(enabled) {
        this.interactiveMode = enabled;
        if (!enabled) {
            this.isCursorVisible = false;
            this.isClicking = false;
        }
    }

    setZoomSensitivity(value) { this.zoomSensitivity = value; }
    setRotationSensitivity(value) { this.rotationSensitivity = value; }
    setPanSensitivity(value) { this.panSensitivity = value; }

    onZoom(callback) { this.callbacks.onZoom = callback; return this; }
    onRotate(callback) { this.callbacks.onRotate = callback; return this; }
    onPan(callback) { this.callbacks.onPan = callback; return this; }
    onRecenter(callback) { this.callbacks.onRecenter = callback; return this; }
    onGestureChange(callback) { this.callbacks.onGestureChange = callback; return this; }
    onCursor(callback) { this.callbacks.onCursor = callback; return this; }

    processLandmarks(landmarks) {
        if (!landmarks) {
            this.reset();
            this.callbacks.onGestureChange?.('none');
            this.callbacks.onCursor?.({ visible: false, clicking: false, x: 0, y: 0 });
            return;
        }

        const thumb = landmarks[4];
        const index = landmarks[8];
        const middle = landmarks[12];
        const ring = landmarks[16];
        const pinky = landmarks[20];

        const indexDist = this.dist(thumb, index);
        const middleDist = this.dist(thumb, middle);
        const ringDist = this.dist(thumb, ring);
        const pinkyDist = this.dist(thumb, pinky);

        const allDist = (indexDist + middleDist + ringDist + pinkyDist) / 4;
        const otherDist = (middleDist + ringDist + pinkyDist) / 3;

        const handCenter = this.palmCenter(landmarks);
        const now = Date.now();

        if (!this.prevLandmarks) {
            this.prevLandmarks = landmarks;
            this.prevHandCenter = handCenter;
            return;
        }

        if (this.interactiveMode) {
            this.processInteractiveMode(landmarks, index, thumb, indexDist);
            this.prevLandmarks = landmarks;
            this.prevHandCenter = handCenter;
            return;
        }

        const isIndexPinch = indexDist < this.PINCH_CLOSE && otherDist > 0.1;
        const isFullPinch = allDist < this.FULL_PINCH;
        const isQuietCoyote = middleDist < 0.06 && ringDist < 0.06 && indexDist > 0.1 && pinkyDist > 0.1;

        if (isQuietCoyote) {
            this.recenterFrames++;
            if (this.recenterFrames >= this.RECENTER_FRAMES) {
                this.callbacks.onRecenter?.();
                this.recenterFrames = 0;
                this.callbacks.onGestureChange?.('recentered');
            } else {
                const pct = Math.round((this.recenterFrames / this.RECENTER_FRAMES) * 100);
                this.callbacks.onGestureChange?.(`recenter ${pct}%`);
            }
            this.resetPinch();
            this.prevLandmarks = landmarks;
            this.prevHandCenter = handCenter;
            return;
        }
        this.recenterFrames = 0;

        if (isFullPinch) {
            this.resetPinch();

            if (!this.isRotating) {
                this.isRotating = true;
                this.rotationAnchor = { ...handCenter };
            }

            const moved = this.dist(handCenter, this.rotationAnchor);
            if (moved > this.RELOAD_DIST) {
                this.rotationAnchor = { ...handCenter };
            } else {
                const dx = (handCenter.x - this.prevHandCenter.x) * 3.5 * this.rotationSensitivity;
                const dy = (handCenter.y - this.prevHandCenter.y) * 3.5 * this.rotationSensitivity;
                if (Math.abs(dx) > 0.0005 || Math.abs(dy) > 0.0005) {
                    this.callbacks.onRotate?.(dx, dy);
                }
            }
            this.callbacks.onGestureChange?.('rotating');
        }
        else if (isIndexPinch) {
            this.isRotating = false;
            this.rotationAnchor = null;

            if (!this.wasIndexPinch) {
                this.wasIndexPinch = true;
                this.pinchStartTime = now;
                this.pinchStartCenter = { ...handCenter };
                this.didPan = false;
                this.didZoomOut = false;
            }

            const movedSinceStart = this.dist(handCenter, this.pinchStartCenter);
            const heldLongEnough = (now - this.pinchStartTime) > this.HOLD_TIME;

            if (movedSinceStart > this.PAN_THRESHOLD && !this.didZoomOut) {
                this.didPan = true;
                const dx = (handCenter.x - this.prevHandCenter.x) * 2 * this.panSensitivity;
                const dy = (handCenter.y - this.prevHandCenter.y) * 2 * this.panSensitivity;
                if (Math.abs(dx) > 0.001 || Math.abs(dy) > 0.001) {
                    this.callbacks.onPan?.(-dx, dy);
                }
                this.callbacks.onGestureChange?.('panning');
            }
            else if (heldLongEnough && !this.didPan && !this.didZoomOut) {
                if ((now - this.lastZoomTime) > this.ZOOM_COOLDOWN) {
                    this.callbacks.onZoom?.(-1.0 * this.zoomSensitivity);
                    this.lastZoomTime = now;
                    this.didZoomOut = true;
                    this.callbacks.onGestureChange?.('zoom-out');
                }
            }
            else if (!this.didPan && !this.didZoomOut) {
                this.callbacks.onGestureChange?.('pinch-hold');
            }
        }
        else {
            this.isRotating = false;
            this.rotationAnchor = null;

            if (this.wasIndexPinch && !this.didPan && !this.didZoomOut) {
                if ((now - this.lastZoomTime) > this.ZOOM_COOLDOWN) {
                    this.callbacks.onZoom?.(1.0 * this.zoomSensitivity);
                    this.lastZoomTime = now;
                    this.callbacks.onGestureChange?.('zoom-in');
                }
            }

            this.resetPinch();
            this.callbacks.onGestureChange?.('tracking');
        }

        this.prevLandmarks = landmarks;
        this.prevHandCenter = handCenter;
    }

    processInteractiveMode(landmarks, index, thumb, indexDist) {
        const screenX = (1 - index.x) * window.innerWidth;
        const screenY = index.y * window.innerHeight;

        this.cursorPosition = { x: screenX, y: screenY };

        const isCursorActive = indexDist < this.CURSOR_THRESHOLD;
        const isClicking = indexDist < this.PINCH_CLOSE;

        this.isCursorVisible = true;
        this.isClicking = isClicking;

        this.callbacks.onCursor?.({
            visible: this.isCursorVisible,
            clicking: isClicking,
            x: screenX,
            y: screenY
        });

        if (isClicking) {
            this.callbacks.onGestureChange?.('clicking');
        } else if (isCursorActive) {
            this.callbacks.onGestureChange?.('cursor');
        } else {
            this.callbacks.onGestureChange?.('tracking');
        }
    }

    resetPinch() {
        this.wasIndexPinch = false;
        this.pinchStartTime = 0;
        this.pinchStartCenter = null;
        this.didPan = false;
        this.didZoomOut = false;
    }

    reset() {
        this.prevLandmarks = null;
        this.isRotating = false;
        this.rotationAnchor = null;
        this.recenterFrames = 0;
        this.isCursorVisible = false;
        this.isClicking = false;
        this.resetPinch();
    }

    palmCenter(lm) {
        const ids = [0, 5, 9, 13, 17];
        let x = 0, y = 0;
        ids.forEach(i => { x += lm[i].x; y += lm[i].y; });
        return { x: x / 5, y: y / 5 };
    }

    dist(a, b) {
        return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
    }
}
