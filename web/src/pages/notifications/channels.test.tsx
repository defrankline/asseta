import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../access/permissionCodes';
import { ApiError } from '../../api/ApiError';
import type { notificationChannelService } from '../../api/services/notificationChannelService';
import type {
  NotificationCategory,
  NotificationChannelDeliveryDto,
  NotificationRoutingDto,
  NotificationSeverity,
  PushDeviceDto,
} from '../../api/types';
import { renderWithProviders } from '../../test/renderWithProviders';
import { ChannelDeliveriesTable } from './ChannelDeliveriesTable';
import { PushDevicesSection } from './PushDevicesSection';
import { routingChanges } from './routing';
import { RoutingEditor } from './RoutingEditor';

type Svc = typeof notificationChannelService;
const mocks = vi.hoisted(() => ({
  getRouting: vi.fn<Svc['getRouting']>(),
  updateRouting: vi.fn<Svc['updateRouting']>(),
  listDevices: vi.fn<Svc['listDevices']>(),
  deactivateDevice: vi.fn<Svc['deactivateDevice']>(),
  listDeliveries: vi.fn<Svc['listDeliveries']>(),
}));
vi.mock('../../api/services/notificationChannelService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/services/notificationChannelService')>()),
  notificationChannelService: mocks,
}));

const CATEGORIES: NotificationCategory[] = ['ACTION', 'REMINDER', 'ANOMALY', 'BILLING', 'INFO'];
const SEVERITIES: NotificationSeverity[] = ['INFO', 'WARNING', 'CRITICAL'];

function routing(): NotificationRoutingDto[] {
  return CATEGORIES.flatMap((category) =>
    SEVERITIES.map((severity) => ({
      category,
      severity,
      in_app: true,
      push: severity !== 'INFO',
      email: severity === 'CRITICAL',
      mandatory_channels:
        category === 'BILLING' && severity === 'WARNING' ? (['EMAIL'] as const) : [],
      source: 'BUILT_IN',
    })),
  ).map((r) => ({ ...r, mandatory_channels: [...r.mandatory_channels] }));
}

function device(overrides: Partial<PushDeviceDto> = {}): PushDeviceDto {
  return {
    id: 'd1',
    tenant_id: null,
    platform: 'ANDROID',
    app: 'OWNER',
    token_hint: '…a1b2',
    app_version: '1.0.0',
    device_label: 'Pixel 8',
    active: true,
    created_at: '2026-10-01T08:00:00Z',
    last_registered_at: '2026-10-20T08:00:00Z',
    deactivated_at: null,
    deactivation_reason: null,
    ...overrides,
  };
}

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

beforeEach(() => {
  mocks.getRouting.mockResolvedValue(routing());
  mocks.updateRouting.mockResolvedValue(routing());
});

const TENANT = { tenantPermissions: [P.tenantNotificationRead, P.tenantNotificationManage] };

describe('RoutingEditor', () => {
  it('shows the category x severity matrix with mandatory channels locked and explained', async () => {
    renderWithProviders(<RoutingEditor console="tenant" tenantDefault={false} />, TENANT);
    const locked = await screen.findByRole('checkbox', {
      name: 'E-mail for Billing, Warning (required)',
    });
    expect(locked).toBeChecked();
    expect(locked).toBeDisabled();
    expect(screen.getByText(/Locked channels are required/)).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: 'Push for Action needed, Info' }),
    ).not.toBeChecked();
    expect(mocks.getRouting).toHaveBeenCalledWith('tenant', false, expect.any(AbortSignal));
  });

  it('saves only the changed cells', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoutingEditor console="tenant" tenantDefault={false} />, TENANT);
    await user.click(await screen.findByRole('checkbox', { name: 'Push for Action needed, Info' }));
    await user.click(screen.getByRole('checkbox', { name: 'E-mail for Anomalies, Warning' }));
    await user.click(screen.getByRole('button', { name: 'Save routing' }));
    await waitFor(() => {
      expect(mocks.updateRouting).toHaveBeenCalledWith(
        'tenant',
        {
          changes: [
            { category: 'ACTION', severity: 'INFO', push: true, email: false },
            { category: 'ANOMALY', severity: 'WARNING', push: true, email: true },
          ],
          tenant_default: false,
        },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Push and e-mail routing saved.')).toBeInTheDocument();
  });

  it('saves tenant defaults with the tenant_default flag and shows MANDATORY_CHANNEL', async () => {
    const user = userEvent.setup();
    mocks.updateRouting.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'MANDATORY_CHANNEL',
        message: 'E-mail is required for this notification',
        correlationId: 'c',
      }),
    );
    renderWithProviders(<RoutingEditor console="tenant" tenantDefault />, TENANT);
    await user.click(await screen.findByRole('checkbox', { name: 'Push for Billing, Critical' }));
    await user.click(screen.getByRole('button', { name: 'Save routing defaults' }));
    expect(
      await screen.findByText('E-mail is required for this notification (MANDATORY_CHANNEL)'),
    ).toBeInTheDocument();
    expect(mocks.getRouting).toHaveBeenCalledWith('tenant', true, expect.any(AbortSignal));
    expect(mocks.updateRouting.mock.calls[0]?.[1]).toMatchObject({ tenant_default: true });
  });

  it('never proposes switching a locked channel off', () => {
    const rows = routing();
    const draft = { 'BILLING:WARNING': { push: true, email: false } };
    expect(routingChanges(rows, draft)).toEqual([
      { category: 'BILLING', severity: 'WARNING', push: true, email: true },
    ]);
  });
});

describe('PushDevicesSection', () => {
  it('lists my devices and deactivates one after confirmation', async () => {
    const user = userEvent.setup();
    mocks.listDevices.mockResolvedValue(page([device()]));
    mocks.deactivateDevice.mockResolvedValue(device({ active: false }));
    renderWithProviders(<PushDevicesSection />, TENANT);
    const table = await screen.findByRole('table', { name: 'My devices' });
    expect(within(table).getByText('Pixel 8 · Owner app')).toBeInTheDocument();
    expect(within(table).getByText(/Token ending …a1b2/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate Pixel 8 · Owner app' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Deactivate device' }));
    await waitFor(() => {
      expect(mocks.deactivateDevice).toHaveBeenCalledWith('d1', expect.any(String));
    });
    expect(
      await screen.findByText('Pixel 8 · Owner app will no longer receive push notifications.'),
    ).toBeInTheDocument();
    expect(mocks.listDevices).toHaveBeenCalledTimes(2);
  });

  it('includes deactivated devices on request', async () => {
    const user = userEvent.setup();
    mocks.listDevices.mockResolvedValue(page([]));
    renderWithProviders(<PushDevicesSection />, TENANT);
    expect(await screen.findByText('No registered devices')).toBeInTheDocument();
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(mocks.listDevices).toHaveBeenLastCalledWith(true, expect.any(AbortSignal));
    });
  });
});

describe('ChannelDeliveriesTable', () => {
  it('filters the push / e-mail delivery log by channel and status', async () => {
    const user = userEvent.setup();
    const delivery: NotificationChannelDeliveryDto = {
      id: 'x1',
      notification_id: 'n1',
      tenant_id: 't',
      recipient_user_id: 'u',
      channel: 'EMAIL',
      push_device_id: null,
      notification_type: 'INVOICE_OVERDUE',
      severity: 'WARNING',
      status: 'FAILED',
      attempts: 3,
      next_attempt_at: '2026-10-21T10:00:00Z',
      last_error: 'SMTP timeout',
      provider: 'smtp',
      created_at: '2026-10-21T09:00:00Z',
      sent_at: null,
    };
    mocks.listDeliveries.mockResolvedValue(page([delivery]));
    renderWithProviders(<ChannelDeliveriesTable console="tenant" />, TENANT);
    expect(await screen.findByText('SMTP timeout')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Channel' }));
    await user.click(screen.getByRole('option', { name: 'E-mail' }));
    await user.click(screen.getByRole('combobox', { name: 'Delivery status' }));
    await user.click(screen.getByRole('option', { name: 'Failed' }));
    await waitFor(() => {
      expect(mocks.listDeliveries).toHaveBeenLastCalledWith(
        'tenant',
        { page: 1, page_size: 25, channel: 'EMAIL', status: 'FAILED' },
        expect.any(AbortSignal),
      );
    });
  });
});
