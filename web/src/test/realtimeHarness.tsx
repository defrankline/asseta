import { act } from '@testing-library/react';
import type { ReactNode } from 'react';
import type { NotificationService } from '../api/services/notificationService';
import { NotificationCenterProvider } from '../notifications/center/NotificationCenterProvider';
import { RealtimeProvider } from '../realtime/RealtimeProvider';
import type { FakeSocketServer } from './fakeWebSocket';

interface LiveProvidersProps {
  server: FakeSocketServer;
  /** When given, also mounts the notification center with this service. */
  notifications?: NotificationService;
  scopeKey?: string;
  /** Notification read permission in the current console (default true). */
  notificationsEnabled?: boolean;
  children: ReactNode;
}

/** Realtime connection over a fake socket (+ optional notification center) for page tests. */
export function LiveProviders({
  server,
  notifications,
  scopeKey = 'platform',
  notificationsEnabled = true,
  children,
}: LiveProvidersProps) {
  const content =
    notifications === undefined ? (
      children
    ) : (
      <NotificationCenterProvider
        service={notifications}
        scopeKey={scopeKey}
        enabled={notificationsEnabled}
      >
        {children}
      </NotificationCenterProvider>
    );
  return (
    <RealtimeProvider
      enabled
      url="ws://test/realtime"
      getAccessToken={() => Promise.resolve('tok')}
      scope={{ kind: 'platform' }}
      createSocket={server.factory}
      tuning={{ random: () => 0, heartbeatIntervalMs: 600_000 }}
    >
      {content}
    </RealtimeProvider>
  );
}

/** Opens and authenticates the latest fake socket (after the async token lookup). */
export async function acceptSocket(server: FakeSocketServer): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
  for (let i = 0; i < 20 && server.sockets.length === 0; i++) {
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
  }
  act(() => {
    server.last().accept();
  });
}

/** Server pushes one message on the open socket. */
export function push(server: FakeSocketServer, type: string, data: unknown): void {
  act(() => {
    server.last().receive({ type, payload: data });
  });
}
