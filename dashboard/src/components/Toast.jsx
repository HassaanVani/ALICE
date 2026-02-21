import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

const ToastContext = createContext(null);

const TYPE_COLORS = {
  success: 'var(--success)',
  error: 'var(--danger)',
  info: 'var(--accent)',
};

function ToastItem({ toast }) {
  const color = TYPE_COLORS[toast.type] || TYPE_COLORS.info;
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '8px 14px',
      background: 'var(--bg-panel)',
      border: `1px solid ${color}`,
      borderRadius: 6,
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--text-primary)',
      boxShadow: `0 4px 12px rgba(0,0,0,0.4), 0 0 8px ${color}33`,
      animation: 'toastSlideIn 0.25s ease forwards',
      minWidth: 200,
      maxWidth: 320,
    }}>
      <span style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
      }} />
      {toast.message}
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const addToast = useCallback((message, type = 'info') => {
    const id = ++idRef.current;
    setToasts((prev) => {
      const next = [...prev, { id, message, type }];
      // Max 3 visible, dismiss oldest first
      return next.length > 3 ? next.slice(next.length - 3) : next;
    });
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      {toasts.length > 0 && (
        <div style={{
          position: 'fixed',
          top: 12,
          right: 12,
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          pointerEvents: 'none',
        }}>
          {toasts.map((t) => <ToastItem key={t.id} toast={t} />)}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
