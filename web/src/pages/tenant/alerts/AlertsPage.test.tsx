import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { alertService } from '../../../api/services/alertService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { AlertsPage } from './AlertsPage';

const mocks = vi.hoisted(() => ({ list: vi.fn<typeof alertService.list>() }));
vi.mock('../../../api/services/alertService', () => ({
  alertService: { list: mocks.list, act: vi.fn() },
}));
vi.mock('../../../api/services/fleetService', () => ({
  fleetService: { map: vi.fn().mockResolvedValue([]) },
}));
vi.mock('../../../components/data/ExportMenu', () => ({ ExportMenu: () => null }));

beforeEach(() => {
  mocks.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
});

describe('AlertsPage', () => {
  it('applies status and severity from a dashboard link on the server', async () => {
    renderWithProviders(<AlertsPage />, {
      tenantPermissions: [P.tenantFleetRead],
      route: '/tenant/alerts?status=OPEN&severity=CRITICAL',
    });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalled();
    });
    expect(mocks.list.mock.lastCall?.[0].filters).toMatchObject({
      status: 'OPEN',
      severity: 'CRITICAL',
    });
    expect(screen.getByRole('combobox', { name: 'Severity' })).toHaveTextContent('Critical');
  });

  it('ignores an unknown severity in the URL', async () => {
    renderWithProviders(<AlertsPage />, {
      tenantPermissions: [P.tenantFleetRead],
      route: '/tenant/alerts?severity=EXTREME',
    });
    await waitFor(() => {
      expect(mocks.list).toHaveBeenCalled();
    });
    expect(mocks.list.mock.lastCall?.[0].filters?.severity).toBeFalsy();
  });
});
