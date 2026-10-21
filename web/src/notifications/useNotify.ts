import { useContext } from 'react';
import { NotificationContext, type Notifier } from './NotificationContext';

export function useNotify(): Notifier {
  const ctx = useContext(NotificationContext);
  if (ctx === null) throw new Error('useNotify must be used inside <NotificationProvider>.');
  return ctx;
}
