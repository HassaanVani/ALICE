import React, { useRef, useEffect } from 'react';

const styles = {
  container: {
    width: '100%',
    height: '100%',
    background: '#000',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  canvas: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },
  placeholder: {
    color: '#52525b',
    fontSize: 12,
    fontFamily: 'var(--font-mono)',
    textAlign: 'center',
  },
  fpsOverlay: {
    position: 'absolute',
    top: 8,
    right: 8,
    background: 'rgba(0,0,0,0.7)',
    color: '#22c55e',
    padding: '2px 6px',
    borderRadius: 3,
    fontSize: 10,
    fontFamily: 'var(--font-mono)',
  },
};

export default function CameraPanel({ frameRef }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(new Image());
  const rafRef = useRef(null);
  const lastUrlRef = useRef(null);
  const fpsRef = useRef({ count: 0, last: performance.now(), display: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const render = () => {
      const url = frameRef.current;

      if (url && url !== lastUrlRef.current) {
        lastUrlRef.current = url;
        const img = imgRef.current;
        img.onload = () => {
          // Resize canvas to match frame aspect ratio
          canvas.width = img.naturalWidth || 640;
          canvas.height = img.naturalHeight || 480;
          ctx.drawImage(img, 0, 0);

          // FPS counter
          fpsRef.current.count++;
          const now = performance.now();
          if (now - fpsRef.current.last >= 1000) {
            fpsRef.current.display = fpsRef.current.count;
            fpsRef.current.count = 0;
            fpsRef.current.last = now;
          }
        };
        img.src = url;
      }

      rafRef.current = requestAnimationFrame(render);
    };

    rafRef.current = requestAnimationFrame(render);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [frameRef]);

  return (
    <div style={styles.container}>
      <canvas ref={canvasRef} style={styles.canvas} />
      {!frameRef.current && (
        <div style={{ ...styles.placeholder, position: 'absolute' }}>
          <div style={{ marginBottom: 4 }}>NO SIGNAL</div>
          <div style={{ fontSize: 10, color: '#3f3f46' }}>Waiting for camera feed...</div>
        </div>
      )}
    </div>
  );
}
