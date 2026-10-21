import { useContext } from 'react';
import { SessionContext, type SessionContextValue } from './SessionContext';

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (ctx === null) throw new Error('useSession must be used inside <SessionProvider>.');
  return ctx;
}
