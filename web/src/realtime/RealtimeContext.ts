import { createContext } from 'react';
import type { RealtimeClient } from './RealtimeClient';

/** The session's realtime client (stopped while signed out; subscriptions survive restarts). */
export const RealtimeContext = createContext<RealtimeClient | null>(null);
