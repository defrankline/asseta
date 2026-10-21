import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { geofenceService } from '../../../api/services/geofenceService';
import type { policyService } from '../../../api/services/policyService';
import type { PolicyType } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PoliciesPage } from './PoliciesPage';

const mocks = vi.hoisted(() => ({
  effective: vi.fn<typeof policyService.effective>(),
  versions: vi.fn<typeof policyService.versions>(),
  listJobSites: vi.fn<typeof geofenceService.listJobSites>(),
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective, versions: mocks.versions },
}));
vi.mock('../../../api/services/geofenceService', () => ({
  geofenceService: { listJobSites: mocks.listJobSites },
}));
vi.mock('../../../api/services/machineService', () => ({ machineService: { list: vi.fn() } }));

beforeEach(() => {
  mocks.effective.mockImplementation((ptype: PolicyType) =>
    Promise.resolve({
      policy_type: ptype,
      version_stamp: `${ptype}:P1`,
      values:
        ptype === 'METER_CAPTURE'
          ? { opening_mode: 'AUTOMATIC', closing_mode: 'MANUAL' }
          : { billable_hours_increment: '0.1', rounding: 'HALF_UP' },
    }),
  );
  mocks.versions.mockResolvedValue([]);
  mocks.listJobSites.mockResolvedValue([]);
});

describe('PoliciesPage policy types', () => {
  it('switches between policy types and limits HIRE_BILLING to the tenant scope', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PoliciesPage />, {
      tenantPermissions: ['tenant.policy.read', 'tenant.geofence.read'],
    });
    await user.click(screen.getByRole('combobox', { name: 'Policy type' }));
    await user.click(await screen.findByRole('option', { name: 'Meter capture' }));
    await waitFor(() => {
      expect(mocks.effective).toHaveBeenLastCalledWith(
        'METER_CAPTURE',
        expect.anything(),
        expect.anything(),
      );
    });
    const table = await screen.findByRole('table', { name: 'Effective policy values' });
    expect(within(table).getByText('Opening reading mode')).toBeInTheDocument();
    expect(within(table).getByText('Manual (numeric entry)')).toBeInTheDocument();
    const scopes = screen.getByRole('group', { name: 'Policy scope' });
    expect(
      within(scopes)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Tenant', 'Machine', 'Site']);

    await user.click(screen.getByRole('combobox', { name: 'Policy type' }));
    await user.click(await screen.findByRole('option', { name: 'Hire billing' }));
    await waitFor(() => {
      expect(mocks.versions).toHaveBeenLastCalledWith('HIRE_BILLING', expect.anything());
    });
    expect(
      within(screen.getByRole('group', { name: 'Policy scope' }))
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Tenant']);
  });
});
