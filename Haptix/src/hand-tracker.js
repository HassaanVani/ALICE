export class HandTracker {
    constructor(videoElement, canvasElement, onResults) {
        this.video = videoElement;
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.onResults = onResults;
        this.hands = null;
        this.camera = null;
        this.isRunning = false;
    }

    async initialize() {
        const Hands = window.Hands;
        const Camera = window.Camera;

        if (!Hands || !Camera) {
            throw new Error('MediaPipe not loaded');
        }

        this.hands = new Hands({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
        });

        this.hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.7,
            minTrackingConfidence: 0.5
        });

        this.hands.onResults((results) => this.processResults(results));

        this.camera = new Camera(this.video, {
            onFrame: async () => {
                if (this.isRunning) {
                    await this.hands.send({ image: this.video });
                }
            },
            width: 640,
            height: 480
        });
    }

    async start() {
        this.isRunning = true;
        await this.camera.start();
    }

    stop() {
        this.isRunning = false;
        this.camera?.stop();
    }

    processResults(results) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            const landmarks = results.multiHandLandmarks[0];
            this.drawHand(landmarks);
            this.onResults(landmarks);
        } else {
            this.onResults(null);
        }
    }

    drawHand(landmarks) {
        const w = this.canvas.width;
        const h = this.canvas.height;

        this.ctx.strokeStyle = 'rgba(99, 102, 241, 0.8)';
        this.ctx.lineWidth = 2;

        const connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],
            [0, 5], [5, 6], [6, 7], [7, 8],
            [5, 9], [9, 10], [10, 11], [11, 12],
            [9, 13], [13, 14], [14, 15], [15, 16],
            [13, 17], [17, 18], [18, 19], [19, 20],
            [0, 17]
        ];

        connections.forEach(([i, j]) => {
            const start = landmarks[i];
            const end = landmarks[j];
            this.ctx.beginPath();
            this.ctx.moveTo(start.x * w, start.y * h);
            this.ctx.lineTo(end.x * w, end.y * h);
            this.ctx.stroke();
        });

        landmarks.forEach((lm, i) => {
            const isFingertip = [4, 8, 12, 16, 20].includes(i);
            this.ctx.beginPath();
            this.ctx.arc(lm.x * w, lm.y * h, isFingertip ? 6 : 4, 0, Math.PI * 2);
            this.ctx.fillStyle = isFingertip ? '#8b5cf6' : '#6366f1';
            this.ctx.fill();
        });
    }
}
