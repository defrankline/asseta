import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { policyService } from '../../../api/services/policyService';
import type { JobSiteDto, MachineDto, PolicyVersionDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PolicyOverrideDialog } from './PolicyOverrideDialog';
import type { OverrideScope } from './policyFields';

const mocks = vi.hoisted(() => ({ create: vi.fn<typeof policyService.create>() }));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { create: mocks.create },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: vi.fn() },
}));

const MACHINE: MachineDto = {
  id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  asset_code: 'EX-01',
  name: 'Excavator',
  category_id: null,
  operating_area_id: null,
  manufacturer: null,
  model: null,
  serial_number: null,
  year_of_manufacture: null,
  capacity_value: null,
  capacity_unit: null,
  meter_decimal_places: 1,
  ownership: 'OWNED',
  status: 'ACTIVE',
  version: 1,
  created_at: '2026-10-01T00:00:00Z',
};
const SITE: JobSiteDto = {
  id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  code: 'S1',
  name: 'Site One',
  address: null,
  center: { type: 'Point', coordinates: [39.2, -6.8] },
  is_active: true,
  version: 1,
};
const CURRENT = { stale_after_seconds: 1800, geofence_tolerance_m: 30 };

function open(scope: OverrideScope) {
  renderWithProviders(
    <PolicyOverrideDialog
      policyType="TRACKING"
      initialScope={scope}
      initialMachine={scope === 'MACHINE' ? MACHINE : null}
      initialSiteId={scope === 'SITE' ? SITE.id : ''}
      current={CURRENT}
      sites={[SITE]}
      timeZone="UTC"
      onClose={vi.fn()}
      onCreated={vi.fn()}
    />,
    { tenantPermissions: ['tenant.policy.read', 'tenant.policy.manage'] },
  );
}

async function toValues(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^Reason/), 'Night shift tuning');
  await user.click(screen.getByRole('button', { name: 'Next' }));
}

describe('PolicyOverrideDialog', () => {
  it('offers only machine-overridable fields for a MACHINE override', async () => {
    const user = userEvent.setup();
    open('MACHINE');
    await toValues(user);
    expect(await screen.findByLabelText('Override Live max age')).toBeInTheDocument();
    expect(screen.getByLabelText('Override Operating weekdays')).toBeInTheDocument();
    expect(screen.getByLabelText('Override Low power voltage')).toBeInTheDocument();
    expect(screen.queryByLabelText('Override Geofence tolerance')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Override Moving speed threshold')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Override Max replay age')).not.toBeInTheDocument();
    expect(screen.getAllByRole('switch')).toHaveLength(9);
  });

  it('offers only geofence tolerance for a SITE override', async () => {
    const user = userEvent.setup();
    open('SITE');
    await toValues(user);
    expect(await screen.findByLabelText('Override Geofence tolerance')).toBeInTheDocument();
    expect(screen.getAllByRole('switch')).toHaveLength(1);
  });

  it('offers every field for the tenant default', async () => {
    const user = userEvent.setup();
    open('TENANT');
    await toValues(user);
    await screen.findByLabelText('Override Live max age');
    expect(screen.getAllByRole('switch')).toHaveLength(14);
  });

  it('sends only the enabled allowed fields, prefilled from the effective policy', async () => {
    const user = userEvent.setup();
    const created: PolicyVersionDto = {
      id: 'v1',
      policy_type: 'TRACKING',
      scope: 'MACHINE',
      scope_ref_id: MACHINE.id,
      version: 2,
      effective_from: '2026-10-21T00:00:00Z',
      values: { stale_after_seconds: 900 },
      reason: 'Night shift tuning',
      created_at: '2026-10-21T00:00:00Z',
    };
    mocks.create.mockResolvedValue(created);
    open('MACHINE');
    await toValues(user);
    await user.click(await screen.findByLabelText('Override Stale after'));
    const input = screen.getByLabelText('Stale after (s)');
    expect(input).toHaveValue('1800');
    await user.clear(input);
    await user.type(input, '900');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create version' }));
    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith(
        'TRACKING',
        {
          scope: 'MACHINE',
          scope_ref_id: MACHINE.id,
          values: { stale_after_seconds: 900 },
          reason: 'Night shift tuning',
          effective_from: null,
        },
        expect.any(String),
      );
    });
  });

  it('requires at least one override and surfaces backend error codes', async () => {
    const user = userEvent.setup();
    mocks.create.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'POLICY_INVALID',
        message: 'require live_max_age <= stale_after <= offline_after',
        correlationId: 'corr-1',
      }),
    );
    open('MACHINE');
    await toValues(user);
    await user.click(await screen.findByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Override at least one field')).toBeInTheDocument();
    await user.click(screen.getByLabelText('Override Stale after'));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Create version' }));
    expect(await screen.findByText(/POLICY_INVALID: require live_max_age/)).toBeInTheDocument();
  });
});
