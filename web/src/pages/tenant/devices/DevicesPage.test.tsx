import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { TenantDeviceDto, deviceService } from '../../../api/services/deviceService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { DevicesPage } from './DevicesPage';

const m = vi.hoisted(() => ({
  list: vi.fn<typeof deviceService.list>(),
  revoke: vi.fn<typeof deviceService.revoke>(),
}));
vi.mock('../../../api/services/deviceService', () => ({ deviceService: m }));

const active: TenantDeviceDto = {
  id: 'd1',
  device_id: 'phone-0001',
  platform: 'ANDROID',
  app_version: '1.4.2',
  status: 'ACTIVE',
  registered_at: '2026-11-01T08:00:00Z',
  last_sync_at: '2026-11-08T08:00:00Z',
  offline_grant_until: '2026-11-11T08:00:00Z',
  last_clock_offset_s: 0,
  revoked_at: null,
  revoke_reason: null,
  user_id: 'u1',
  user_name: 'Asha Mwinyi',
  device_model: 'Samsung SM-A155',
  revoked_by: null,
  revoked_by_name: null,
};
const revoked: TenantDeviceDto = {
  ...active,
  id: 'd2',
  status: 'REVOKED',
  user_name: 'Juma Said',
  device_model: null,
  last_sync_at: null,
  revoked_at: '2026-11-08T09:00:00Z',
  revoked_by: 'u2',
  revoked_by_name: 'Neema Owner',
  revoke_reason: 'Phone lost',
};

const page = (items: TenantDeviceDto[]) => ({ items, total: items.length, page: 1, page_size: 25 });

describe('Devices page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    m.list.mockResolvedValue(page([active, revoked]));
  });

  it('shows the person, app, model, last seen and how a phone was revoked', async () => {
    renderWithProviders(<DevicesPage />, { tenantPermissions: [P.tenantDeviceManage] });
    expect(await screen.findByText('Asha Mwinyi')).toBeInTheDocument();
    expect(screen.getByText('Samsung SM-A155')).toBeInTheDocument();
    expect(screen.getAllByText('Supervisor app · Android · version 1.4.2')).toHaveLength(2);
    expect(screen.getByText('Model not known')).toBeInTheDocument();
    expect(screen.getByText('Never synced')).toBeInTheDocument();
    expect(screen.getByText(/by Neema Owner: Phone lost/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Revoke' })).toHaveLength(1);
  });

  it('searches on the server', async () => {
    renderWithProviders(<DevicesPage />, { tenantPermissions: [P.tenantDeviceManage] });
    await screen.findByText('Asha Mwinyi');
    await userEvent.type(screen.getByLabelText('Search person, phone or version'), 'Asha');
    await waitFor(() => {
      expect(m.list.mock.lastCall?.[0].q).toBe('Asha');
    });
  });

  it('warns that unsent work is erased, requires a reason, then revokes', async () => {
    m.revoke.mockResolvedValue({ ...active, status: 'REVOKED' });
    renderWithProviders(<DevicesPage />, { tenantPermissions: [P.tenantDeviceManage] });
    await userEvent.click(await screen.findByRole('button', { name: 'Revoke' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Any unsent work on this phone will be erased/)).toBeVisible();
    expect(within(dialog).queryByText(/Nothing is deleted/)).toBeNull();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Revoke phone' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    expect(m.revoke).not.toHaveBeenCalled();

    await userEvent.type(
      within(dialog).getByLabelText(/Reason for revoking/),
      'Phone reported lost',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Revoke phone' }));
    await waitFor(() => {
      expect(m.revoke).toHaveBeenCalledWith('d1', 'Phone reported lost', expect.any(String));
    });
    await waitFor(() => {
      expect(m.list).toHaveBeenCalledTimes(2);
    });
  });

  it('keeps the list but hides revoke while the company is read-only', async () => {
    renderWithProviders(<DevicesPage />, {
      tenantPermissions: [P.tenantDeviceManage],
      accessState: 'READ_ONLY',
    });
    expect(await screen.findByText('Asha Mwinyi')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Revoke' })).toBeNull();
  });
});
