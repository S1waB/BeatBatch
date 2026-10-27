import React, { useCallback, useState } from 'react';
import { ToastContext, type ToastMessage, type ToastType } from '../context/ToastContext';
import { AlertIcon, CheckIcon, SpinnerIcon } from './Icons';

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (type: ToastType, title: string, description?: string, duration: number = 4500) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const newToast: ToastMessage = { id, type, title, description, duration };

      setToasts((prev) => [...prev.slice(-4), newToast]);

      if (duration > 0) {
        setTimeout(() => {
          dismissToast(id);
        }, duration);
      }
    },
    [dismissToast]
  );

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}
      <div className="bb-toast-container" aria-live="polite" role="region" aria-label="Notifications">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`bb-toast bb-toast-${toast.type}`}
            role="status"
          >
            <div className="bb-toast-icon">
              {toast.type === 'success' && <CheckIcon size={18} />}
              {toast.type === 'error' && <AlertIcon size={18} />}
              {toast.type === 'info' && <SpinnerIcon size={18} />}
            </div>
            <div className="bb-toast-body">
              <strong className="bb-toast-title">{toast.title}</strong>
              {toast.description && <p className="bb-toast-desc">{toast.description}</p>}
            </div>
            <button
              type="button"
              className="bb-toast-close"
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};
