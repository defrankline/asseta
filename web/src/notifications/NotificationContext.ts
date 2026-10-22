import { createContext } from 'react';

export type NotificationSeverity = 'success' | 'info' | 'warning' | 'error';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastOptions {
  /** e.g. "View" on a real-time notification toast. */
  action?: ToastAction;
}

export interface Notifier {
  notify: (message: string, severity?: NotificationSeverity, options?: ToastOptions) => void;
  success: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
  /** Shows an error toast; ApiErrors include their correlation id. */
  error: (error: unknown, fallback?: string) => void;
}

export const NotificationContext = createContext<Notifier | null>(null);
