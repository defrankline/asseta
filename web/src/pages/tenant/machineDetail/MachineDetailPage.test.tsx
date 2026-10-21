import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { machineService } from '../../../api/services/machineService';
import type { staffService } from '../../../api/services/staffService';
import type { MachineDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MachineDetailPage } from './MachineDetailPage';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof machineService.get>(),
  listCategories: vi.fn<typeof machineService.listCategories>(),
  listAreas: vi.fn<typeof machineService.listAreas>(),
  listAssignments: vi.fn<typeof machineService.listAssignments>(),
  listStaff: vi.fn<typeof staffService.list>(),
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    get: mocks.get,
    listCategories: mocks.listCategories,
    listAreas: mocks.listAreas,
    listAssignments: mocks.listAssignments,
  },
}));
vi.mock('../../../api/services/staffService', () => ({
  staffService: { list: mocks.listStaff },
}));

const MACHINE: MachineDto = {
  id: 'aaaaaaaa-0000-4000-8000-000000000001',
  asset_code: 'EX-01',
  name: 'Excavator',
  category_id: 'cccccccc-0000-4000-8000-000000000001',
  operating_area_id: null,
  manufacturer: 'CAT',
  model: '320',
  serial_number: 'SN1',
  year_of_manufacture: 2020,
  capacity_value: '20.0000',
  capacity_unit: 't',
  meter_decimal_places: 1,
  ownership: 'OWNED',
  status: 'ACTIVE',
  version: 3,
  created_at: '2026-09-01T00:00:00Z',
};

function setup() {
  mocks.get.mockResolvedValue(MACHINE);
  mocks.listCategories.mockResolvedValue([
    { id: 'cccccccc-0000-4000-8000-000000000001', name: 'Excavators', description: null },
  ]);
  mocks.listAreas.mockResolvedValue([]);
  mocks.listAssignments.mockResolvedValue([
    {
      id: 'as1',
      machine_id: MACHINE.id,
      staff_member_id: 'st1',
      role: 'OPERATOR',
      effective_from: '2026-10-01T06:00:00Z',
      effective_to: null,
    },
  ]);
  mocks.listStaff.mockResolvedValue({
    items: [
      {
        id: 'st1',
        full_name: 'Juma Operator',
        kind: 'OPERATOR',
        employee_code: null,
        phone: null,
        keycloak_subject: null,
        is_active: true,
      },
    ],
    total: 1,
    page: 1,
    page_size: 200,
  });
}

describe('MachineDetailPage permissions', () => {
  it('hides Edit and staff mutations without write permissions', async () => {
    setup();
    renderWithProviders(<MachineDetailPage />, {
      tenantPermissions: ['tenant.machine.read', 'tenant.staff.read'],
    });
    expect(await screen.findByText('Excavators')).toBeInTheDocument();
    expect(await screen.findByText('Juma Operator')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Assign staff' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'End' })).not.toBeInTheDocument();
    // Tabs the user cannot read are not offered.
    expect(screen.queryByRole('tab', { name: 'History' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Tracker history' })).not.toBeInTheDocument();
  });

  it('shows Edit and staff actions with write permissions', async () => {
    setup();
    renderWithProviders(<MachineDetailPage />, {
      tenantPermissions: [
        'tenant.machine.read',
        'tenant.machine.write',
        'tenant.staff.read',
        'tenant.staff.write',
      ],
    });
    expect(await screen.findByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Assign staff' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'End' })).toBeInTheDocument();
  });

  it('hides mutations while the tenant is read-only', async () => {
    setup();
    renderWithProviders(<MachineDetailPage />, {
      tenantPermissions: ['tenant.machine.read', 'tenant.machine.write', 'tenant.staff.read'],
      accessState: 'READ_ONLY',
    });
    expect(await screen.findByText('Excavators')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });
});
