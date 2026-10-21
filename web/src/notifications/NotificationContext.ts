import { createContext } from 'react';

export type NotificationSeverity = 'success' | 'info' | 'warning' | 'error';

export interface Notifier {
  notify: (message: string, severity?: NotificationSeverity) => void;
  success: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
  /** Shows an error toast; ApiErrors include their correlation id. */
  error: (error: unknown, fallback?: string) => void;
}

export const NotificationContext = createContext<Notifier | null>(null);
