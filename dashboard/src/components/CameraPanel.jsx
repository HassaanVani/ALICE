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
};

export default function CameraPanel({ frameRef }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(new Image());
  const rafRef = useRef(null);
  const lastUrlRef = useRef(null);

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
