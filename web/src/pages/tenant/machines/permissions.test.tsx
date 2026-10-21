import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { machineService } from '../../../api/services/machineService';
import type { staffService } from '../../../api/services/staffService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { StaffPage } from '../staff/StaffPage';
import { makeMachine } from './machineFixtures';
import { MachinesPage } from './MachinesPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof machineService.list>(),
  listCategories: vi.fn<typeof machineService.listCategories>(),
  listStaff: vi.fn<typeof staffService.list>(),
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: mocks.list, listCategories: mocks.listCategories },
}));
vi.mock('../../../api/services/staffService', () => ({
  staffService: { list: mocks.listStaff },
}));

beforeEach(() => {
  mocks.list.mockResolvedValue({ items: [makeMachine()], total: 1, page: 1, page_size: 25 });
  mocks.listCategories.mockResolvedValue([]);
  mocks.listStaff.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
});

describe('permission-gated tenant registry actions', () => {
  it('hides New machine and Enroll without write/enroll permissions', async () => {
    renderWithProviders(<MachinesPage />, { tenantPermissions: ['tenant.machine.read'] });
    expect(await screen.findByText('EX-01')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New machine' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Enroll/ })).not.toBeInTheDocument();
  });

  it('shows New machine with tenant.machine.write and Enroll with tenant.billing.enroll', async () => {
    renderWithProviders(<MachinesPage />, {
      tenantPermissions: ['tenant.machine.read', 'tenant.machine.write', 'tenant.billing.enroll'],
    });
    expect(await screen.findByText('EX-01')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New machine' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Enroll EX-01/ })).toBeInTheDocument();
  });

  it('hides mutating actions while the tenant is READ_ONLY', async () => {
    renderWithProviders(<MachinesPage />, {
      tenantPermissions: ['tenant.machine.read', 'tenant.machine.write', 'tenant.billing.enroll'],
      accessState: 'READ_ONLY',
    });
    expect(await screen.findByText('EX-01')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New machine' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Enroll/ })).not.toBeInTheDocument();
  });

  it('shows New staff member only with tenant.staff.write', async () => {
    const { unmount } = renderWithProviders(<StaffPage />, {
      tenantPermissions: ['tenant.staff.read'],
    });
    expect(await screen.findByText('No staff members found')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New staff member' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<StaffPage />, {
      tenantPermissions: ['tenant.staff.read', 'tenant.staff.write'],
    });
    expect(await screen.findByRole('button', { name: 'New staff member' })).toBeInTheDocument();
  });
});
