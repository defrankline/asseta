import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { PERMISSIONS as P } from '../../access/permissionCodes';
import { ApiError } from '../../api/ApiError';
import {
  fakeNotificationService,
  makeDelivery,
  makeNotification,
  makePreference,
  type FakeNotificationService,
} from '../../test/fakeNotificationService';
import { fakeSocketServer } from '../../test/fakeWebSocket';
import { LiveProviders } from '../../test/realtimeHarness';
import { renderWithProviders } from '../../test/renderWithProviders';
import { NotificationPreferencesPage } from './NotificationPreferencesPage';
import { NotificationsPage } from './NotificationsPage';
import { preferenceChanges } from './preferences';
import { SmsDeliveriesPage } from './SmsDeliveriesPage';

let service: FakeNotificationService;

type Opts = Parameters<typeof renderWithProviders>[1];

function renderPage(
  ui: React.ReactNode,
  opts: Opts = { permissions: [P.platformNotificationRead] },
) {
  return renderWithProviders(
    <LiveProviders server={fakeSocketServer()} notifications={service}>
      {ui}
    </LiveProviders>,
    opts,
  );
}

const OVERDUE = makePreference({
  type: 'INVOICE_OVERDUE',
  label: 'Overdue invoices',
  category: 'REMINDER',
  mandatory: true,
  mandatory_channels: ['IN_APP'],
  in_app: true,
  sms: true,
});

beforeEach(() => {
  service = fakeNotificationService(
    [
      makeNotification({ title: 'Fuel anomaly on EX-01', severity: 'CRITICAL' }),
      makeNotification({ title: 'Handover due today', severity: 'WARNING' }),
      makeNotification({ title: 'Subscription renewed', severity: 'INFO', read_at: 'x' }),
    ],
    [
      makePreference(),
      OVERDUE,
      makePreference({ type: 'REPORT_READY', label: 'Reports ready', sms_available: false }),
      makePreference({ type: 'JOB_UPDATE', label: 'Job updates', low_priority: true }),
    ],
  );
});

describe('NotificationsPage', () => {
  it('sends the severity, unread and search filters to the server', async () => {
    const user = userEvent.setup();
    renderPage(<NotificationsPage />);
    const list = await screen.findByRole('list', { name: 'Notifications' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);

    await user.click(screen.getByRole('combobox', { name: 'Severity' }));
    await user.click(screen.getByRole('option', { name: 'Critical' }));
    await waitFor(() => {
      expect(service.list).toHaveBeenLastCalledWith(
        { page: 1, page_size: 20, severity: 'CRITICAL' },
        expect.any(AbortSignal),
      );
    });
    expect(await screen.findByText('Fuel anomaly on EX-01')).toBeInTheDocument();

    await user.click(screen.getByRole('combobox', { name: 'Severity' }));
    await user.click(screen.getByRole('option', { name: 'All' }));
    await user.click(screen.getByRole('combobox', { name: 'Status' }));
    await user.click(screen.getByRole('option', { name: 'Unread' }));
    await user.type(screen.getByRole('textbox', { name: 'Search notifications' }), 'handover');
    await waitFor(() => {
      expect(service.list).toHaveBeenLastCalledWith(
        { page: 1, page_size: 20, unread_only: true, q: 'handover' },
        expect.any(AbortSignal),
      );
    });
    expect(await screen.findByText('Handover due today')).toBeInTheDocument();
    // The delivery log link needs *.notification.manage.
    expect(screen.queryByRole('link', { name: 'SMS delivery log' })).not.toBeInTheDocument();
  });

  it('marks everything read and offers the SMS log to managers', async () => {
    const user = userEvent.setup();
    renderPage(<NotificationsPage />, {
      permissions: [P.platformNotificationRead, P.platformNotificationManage],
    });
    await screen.findByRole('list', { name: 'Notifications' });
    expect(screen.getByRole('link', { name: 'SMS delivery log' })).toBeInTheDocument();
    const button = screen.getByRole('button', { name: 'Mark all read' });
    await waitFor(() => {
      expect(button).toBeEnabled();
    });
    await user.click(button);
    expect(await screen.findByText('All notifications marked as read.')).toBeInTheDocument();
    expect(service.markAllRead).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Mark all read' })).toBeDisabled();
    });
  });
});

describe('NotificationPreferencesPage', () => {
  it('locks mandatory channels per channel and SMS where it is not offered', async () => {
    renderPage(<NotificationPreferencesPage />);
    const overdueInApp = await screen.findByRole('switch', { name: 'Overdue invoices: in-app' });
    expect(overdueInApp).toBeDisabled();
    expect(overdueInApp).toBeChecked();
    // Only IN_APP is mandatory: SMS stays switchable.
    expect(screen.getByRole('switch', { name: 'Overdue invoices: SMS' })).toBeEnabled();
    expect(screen.getByText('Required')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Reports ready: SMS' })).toBeDisabled();
    expect(screen.getByText('Low priority')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Reminders' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save preferences' })).toBeDisabled();
    expect(screen.queryByRole('tab', { name: 'Tenant defaults' })).not.toBeInTheDocument();
  });

  it('saves only the changed channels as {changes, tenant_default}', async () => {
    const user = userEvent.setup();
    renderPage(<NotificationPreferencesPage />);
    await user.click(await screen.findByRole('switch', { name: 'Tracking alerts: SMS' }));
    await user.click(screen.getByRole('switch', { name: 'Overdue invoices: SMS' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));
    await waitFor(() => {
      expect(service.updatePreferences).toHaveBeenCalledTimes(1);
    });
    expect(service.updatePreferences.mock.calls[0]?.[0]).toEqual({
      changes: [
        { type: 'ALERT_RAISED', in_app: true, sms: true },
        { type: 'INVOICE_OVERDUE', in_app: true, sms: false },
      ],
      tenant_default: false,
    });
    expect(await screen.findByText('Notification preferences saved.')).toBeInTheDocument();
    expect(await screen.findByRole('switch', { name: 'Tracking alerts: SMS' })).toBeChecked();
  });

  it('shows MANDATORY_CHANNEL refusals from the server', async () => {
    const user = userEvent.setup();
    service.updatePreferences.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'MANDATORY_CHANNEL',
        message: 'Tracking alerts: mandatory channels cannot be disabled',
        correlationId: 'm1',
      }),
    );
    renderPage(<NotificationPreferencesPage />);
    await user.click(await screen.findByRole('switch', { name: 'Tracking alerts: in-app' }));
    await user.click(screen.getByRole('button', { name: 'Save preferences' }));
    expect(
      await screen.findByText(
        'Tracking alerts: mandatory channels cannot be disabled (MANDATORY_CHANNEL)',
      ),
    ).toBeInTheDocument();
  });

  it('lets tenant owners edit tenant-wide defaults', async () => {
    const user = userEvent.setup();
    renderPage(<NotificationPreferencesPage />, {
      tenantPermissions: [P.tenantNotificationRead, P.tenantNotificationManage],
    });
    await user.click(await screen.findByRole('tab', { name: 'Tenant defaults' }));
    expect(await screen.findByText(/Defaults for everyone in this tenant/)).toBeInTheDocument();
    expect(service.getPreferences).toHaveBeenLastCalledWith(true, expect.any(AbortSignal));
    await user.click(await screen.findByRole('switch', { name: 'Job updates: SMS' }));
    await user.click(screen.getByRole('button', { name: 'Save tenant defaults' }));
    await waitFor(() => {
      expect(service.updatePreferences).toHaveBeenCalledWith(
        { changes: [{ type: 'JOB_UPDATE', in_app: true, sms: true }], tenant_default: true },
        expect.any(String),
      );
    });
  });

  it('saves the SMS number and shows INVALID_MSISDN', async () => {
    const user = userEvent.setup();
    renderPage(<NotificationPreferencesPage />);
    const field = await screen.findByRole('textbox', { name: 'Mobile number' });
    await user.type(field, 'abc');
    await user.click(screen.getByRole('button', { name: 'Save number' }));
    expect(
      await screen.findByText('Not a valid mobile number (INVALID_MSISDN)'),
    ).toBeInTheDocument();
    await user.clear(field);
    await user.type(field, '+255 712 345 678');
    await user.click(screen.getByRole('button', { name: 'Save number' }));
    expect(await screen.findByText('SMS number saved: +255712345678.')).toBeInTheDocument();
  });

  it('never submits a change to a locked channel', () => {
    const prefs = [OVERDUE];
    expect(preferenceChanges(prefs, { INVOICE_OVERDUE: { in_app: false, sms: true } })).toEqual([]);
  });
});

describe('SmsDeliveriesPage', () => {
  it('lists deliveries with a server status filter and sends a platform test', async () => {
    const user = userEvent.setup();
    service.store.deliveries = [
      makeDelivery(),
      makeDelivery({ id: 'd-2', status: 'REFUSED_NO_CREDIT', last_error: 'Wallet empty' }),
    ];
    renderPage(<SmsDeliveriesPage />, {
      permissions: [P.platformNotificationRead, P.platformNotificationManage],
    });
    expect(await screen.findByText('Wallet empty')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Status' }));
    await user.click(screen.getByRole('option', { name: 'Refused no credit' }));
    await waitFor(() => {
      expect(service.listDeliveries).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'REFUSED_NO_CREDIT' }),
        expect.any(AbortSignal),
      );
    });
    await user.click(screen.getByRole('button', { name: 'Send test' }));
    const dialog = screen.getByRole('dialog');
    await user.type(
      within(dialog).getByRole('textbox', { name: /Also send an SMS/ }),
      '+255700000001',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Send test' }));
    await waitFor(() => {
      expect(service.testSend).toHaveBeenCalledWith(
        {
          title: 'Asseta test notification',
          body: 'If you can read this, notifications reach you.',
          msisdn: '+255700000001',
        },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Test notification sent; SMS sent.')).toBeInTheDocument();
  });

  it('hides test-send in the tenant console', async () => {
    service = fakeNotificationService([], [], 'tenant');
    renderPage(<SmsDeliveriesPage />, {
      tenantPermissions: [P.tenantNotificationRead, P.tenantNotificationManage],
    });
    expect(await screen.findByText('+255712345678')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send test' })).not.toBeInTheDocument();
  });
});
