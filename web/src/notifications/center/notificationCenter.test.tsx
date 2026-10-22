import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router';
import { beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from '../../api/ApiError';
import type { NotificationService } from '../../api/services/notificationService';
import { AppHeaderTestBar } from '../../test/headerHarness';
import {
  fakeNotificationService,
  makeNotification,
  type FakeNotificationService,
} from '../../test/fakeNotificationService';
import { fakeSocketServer, type FakeSocketServer } from '../../test/fakeWebSocket';
import { acceptSocket, LiveProviders, push } from '../../test/realtimeHarness';
import { renderWithProviders } from '../../test/renderWithProviders';
import { notificationTargetPath } from './display';

let server: FakeSocketServer;
let service: FakeNotificationService;

function Where() {
  const { pathname } = useLocation();
  return <p data-testid="where">{pathname}</p>;
}

function renderShell(svc: NotificationService | null = service) {
  return renderWithProviders(
    <LiveProviders server={server} {...(svc !== null ? { notifications: svc } : {})}>
      <AppHeaderTestBar />
      <Routes>
        <Route path="*" element={<Where />} />
      </Routes>
    </LiveProviders>,
    { route: '/platform' },
  );
}

const bell = (count?: number) =>
  screen.findByRole('button', {
    name: count === undefined ? 'Notifications' : `Notifications (${String(count)} unread)`,
    // The drawer is modal: the header is aria-hidden behind it.
    hidden: true,
  });

beforeEach(() => {
  server = fakeSocketServer();
  service = fakeNotificationService([
    makeNotification({ title: 'Older info', read_at: '2026-10-21T09:00:00Z' }),
    makeNotification({
      title: 'Expense awaiting approval',
      severity: 'WARNING',
      target: { entity: 'approval', id: 'ap1', path: null },
    }),
    makeNotification({ title: 'Invoice overdue', severity: 'CRITICAL' }),
  ]);
});

describe('header bell and unread badge', () => {
  it('shows the unread count and raises it on a pushed notification', async () => {
    renderShell();
    expect(await bell(2)).toBeInTheDocument();
    await acceptSocket(server);
    push(server, 'notification', makeNotification({ title: 'Machine idle too long' }));
    expect(await bell(3)).toBeInTheDocument();
    // Normal priority: no toast.
    expect(screen.queryByText('Machine idle too long')).not.toBeInTheDocument();
  });

  it('follows the server unread_count, including the count in auth_ok after a reconnect', async () => {
    renderShell();
    await bell(2);
    await acceptSocket(server);
    push(server, 'unread_count', { count: 7 });
    expect(await bell(7)).toBeInTheDocument();
    act(() => {
      server.last().serverClose(4408, 'IDLE_TIMEOUT');
    });
    await act(() => new Promise((r) => setTimeout(r, 1_100)));
    act(() => {
      server.last().accept(0);
    });
    expect(await bell()).toBeInTheDocument();
  });

  it('toasts high-priority pushes with a View link to the target screen', async () => {
    const user = userEvent.setup();
    renderShell();
    await bell(2);
    await acceptSocket(server);
    push(
      server,
      'notification',
      makeNotification({
        id: 'hot',
        title: 'EX-01 left the geofence',
        severity: 'CRITICAL',
        priority: 'HIGH',
        target: { entity: 'alert', id: 'a1', path: null },
      }),
    );
    const toast = await screen.findByRole('alert');
    expect(within(toast).getByText('EX-01 left the geofence')).toBeInTheDocument();
    await user.click(within(toast).getByRole('button', { name: 'View' }));
    expect(screen.getByTestId('where')).toHaveTextContent('/tenant/alerts');
    await waitFor(() => {
      expect(service.markRead).toHaveBeenCalledWith(['hot'], expect.any(String));
    });
  });

  it('is hidden without a center or without notification read permission', async () => {
    const view = renderShell(null);
    expect(screen.queryByRole('button', { name: /^Notifications/ })).not.toBeInTheDocument();
    view.unmount();
    renderWithProviders(
      <LiveProviders server={server} notifications={service} notificationsEnabled={false}>
        <AppHeaderTestBar />
      </LiveProviders>,
    );
    await acceptSocket(server);
    push(server, 'notification', makeNotification({ priority: 'HIGH', title: 'Hidden' }));
    expect(screen.queryByRole('button', { name: /^Notifications/ })).not.toBeInTheDocument();
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
    expect(service.unreadCount).not.toHaveBeenCalled();
  });

  it('shows API failures in the drawer with the correlation id', async () => {
    const user = userEvent.setup();
    service.list.mockRejectedValue(
      new ApiError({ status: 503, code: 'X', message: 'Inbox down', correlationId: 'c1' }),
    );
    renderShell();
    await user.click(await bell(2));
    expect(await screen.findByText('Could not load notifications')).toBeInTheDocument();
    expect(screen.getByText('Inbox down')).toBeInTheDocument();
  });
});

describe('notifications drawer', () => {
  it('lists notifications with severity and read state, and marks one read', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(await bell(2));
    const list = await screen.findByRole('list', { name: 'Notifications' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Invoice overdue');
    expect(items[0]).toHaveTextContent('Critical');
    expect(items[0]).toHaveAttribute('data-unread', 'true');
    expect(items[2]).toHaveAttribute('data-unread', 'false');
    await user.click(screen.getByRole('button', { name: 'Mark "Invoice overdue" as read' }));
    expect(service.markRead).toHaveBeenCalledWith([expect.any(String)], expect.any(String));
    expect(await bell(1)).toBeInTheDocument();
    expect(within(list).getAllByRole('listitem')[0]).toHaveAttribute('data-unread', 'false');
  });

  it('restores the unread state and reports the error when marking read fails', async () => {
    const user = userEvent.setup();
    service.markRead.mockRejectedValueOnce(
      new ApiError({ status: 500, code: 'X', message: 'Server down', correlationId: 'c9' }),
    );
    renderShell();
    await user.click(await bell(2));
    await user.click(await screen.findByRole('button', { name: 'Mark "Invoice overdue" as read' }));
    expect(await screen.findByText('Server down (ref c9)')).toBeInTheDocument();
    const list = screen.getByRole('list', { name: 'Notifications' });
    expect(within(list).getAllByRole('listitem')[0]).toHaveAttribute('data-unread', 'true');
    expect(await bell(2)).toBeInTheDocument();
  });

  it('marks all read, opens a target screen and merges pushed notifications', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(await bell(2));
    await acceptSocket(server);
    await screen.findByRole('list', { name: 'Notifications' });
    push(server, 'notification', makeNotification({ title: 'Fresh push' }));
    const list = screen.getByRole('list', { name: 'Notifications' });
    expect(within(list).getAllByRole('listitem')[0]).toHaveTextContent('Fresh push');
    await user.click(screen.getByRole('button', { name: 'Mark all read' }));
    expect(service.markAllRead).toHaveBeenCalledTimes(1);
    expect(await bell()).toBeInTheDocument();
    for (const item of within(list).getAllByRole('listitem')) {
      expect(item).toHaveAttribute('data-unread', 'false');
    }
    await user.click(screen.getByRole('button', { name: 'Open: Expense awaiting approval' }));
    expect(screen.getByTestId('where')).toHaveTextContent('/tenant/approvals');
    expect(screen.queryByRole('list', { name: 'Notifications' })).not.toBeInTheDocument();
  });

  it('loads more pages on demand', async () => {
    const user = userEvent.setup();
    service.store.items = Array.from({ length: 20 }, (_v, i) =>
      makeNotification({ title: `Reminder ${String(i + 1)}` }),
    );
    renderShell();
    await user.click(await bell(20));
    const list = await screen.findByRole('list', { name: 'Notifications' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(15);
    await user.click(screen.getByRole('button', { name: 'Load more' }));
    await waitFor(() => {
      expect(within(list).getAllByRole('listitem')).toHaveLength(20);
    });
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
    expect(service.list).toHaveBeenLastCalledWith(
      { page: 2, page_size: 15 },
      expect.any(AbortSignal),
    );
  });
});

describe('notification targets', () => {
  it('only follows internal console paths and maps known entities', () => {
    expect(notificationTargetPath(null)).toBeNull();
    expect(notificationTargetPath({ entity: 'x', id: null, path: '/tenant/jobs/j1' })).toBe(
      '/tenant/jobs/j1',
    );
    expect(notificationTargetPath({ entity: 'job', id: 'j1', path: 'https://evil.test' })).toBe(
      '/tenant/jobs/j1',
    );
    expect(notificationTargetPath({ entity: 'job', id: null, path: '//evil.test' })).toBe(
      '/tenant/jobs',
    );
    expect(notificationTargetPath({ entity: 'platform_invoice', id: 'i 1', path: null })).toBe(
      '/platform/invoices/i%201',
    );
    expect(notificationTargetPath({ entity: 'unknown', id: 'x', path: null })).toBeNull();
  });
});
